#!/usr/bin/env python3
"""Use Fusion's local MCP server directly, independently of Codex's saved registration.

The current Fusion server returns JSON over Streamable HTTP. The session stays
in this process; no authentication information or session IDs are written out.
"""

import argparse
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        # Keep script contents and session headers on the selected local endpoint.
        return None


class FusionClient:
    def __init__(self, url="http://127.0.0.1:27182/mcp"):
        parsed = urlsplit(url)
        if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "::1", "localhost")
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Use the local HTTP URL displayed in Fusion Preferences → General → API")
        self.url = url
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        self.headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        self.sequence = 0

    def call(self, method, params=None, notification=False):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        if not notification:
            self.sequence += 1
            message["id"] = self.sequence
        request = Request(self.url, data=json.dumps(message).encode(), headers=self.headers)
        try:
            with self.opener.open(request, timeout=120) as response:
                if session := response.headers.get("Mcp-Session-Id"):
                    self.headers["Mcp-Session-Id"] = session
                raw = response.read()
        except HTTPError as error:
            error.close()
            raise
        if not raw:
            if notification:
                return None
            raise RuntimeError("Fusion returned no JSON-RPC response")
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("jsonrpc") != "2.0":
            raise RuntimeError("Fusion returned an invalid JSON-RPC response")
        if not notification and data.get("id") != message["id"]:
            raise RuntimeError("Fusion returned a response for a different request")
        if "error" in data:
            raise RuntimeError(data["error"])
        return data.get("result")

    def __enter__(self):
        try:
            result = self.call("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                "clientInfo": {"name": "fusion-omarchy-validation", "version": "0.1.0"}})
            self.headers["MCP-Protocol-Version"] = result["protocolVersion"]
            self.call("notifications/initialized", notification=True)
            self.tools = self.call("tools/list", {})["tools"]
            return self
        except BaseException:
            # A failed __enter__ is never followed by Python's __exit__.
            self.close()
            raise

    def execute(self, source, read_only=False):
        matches = [tool for tool in self.tools if "script" in tool.get("inputSchema", {})
                   .get("properties", {}).get("featureType", {}).get("enum", [])
                   and "script" in tool.get("inputSchema", {}).get("properties", {})
                   .get("object", {}).get("properties", {})]
        if len(matches) != 1:
            raise RuntimeError("Could not uniquely discover Fusion's script execution tool")
        return self.call("tools/call", {"name": matches[0]["name"], "arguments": {
            "featureType": "script", "object": {"readOnly": read_only, "script": source}}})

    def close(self):
        if not self.headers.get("Mcp-Session-Id"):
            return
        try:
            with self.opener.open(Request(self.url, method="DELETE", headers=self.headers), timeout=5):
                pass
        except HTTPError as error:
            error.close()
        except OSError:
            pass
        finally:
            self.headers.pop("Mcp-Session-Id", None)

    def __exit__(self, *_):
        self.close()


INSPECT = """import adsk.core
import json
def run(_context):
    app = adsk.core.Application.get()
    print(json.dumps({'version': app.version, 'open_documents': app.documents.count,
        'configured_graphics_driver': str(app.preferences.generalPreferences.graphicsDriver)}))
"""


def script_succeeded(result):
    if not isinstance(result, dict):
        raise RuntimeError("Fusion returned an invalid script result")
    if result.get("isError"):
        return False
    # This Fusion build reports script failures inside its JSON text envelope,
    # without setting MCP's top-level isError. Do not mistake transport success
    # for a completed script, or interpret the script's printed message itself.
    payloads = [result.get("structuredContent")]
    for content in result.get("content", []):
        if isinstance(content, dict) and content.get("type") == "text":
            try:
                payloads.append(json.loads(content["text"]))
            except (KeyError, TypeError, ValueError):
                pass
    states = [payload["success"] for payload in payloads
              if isinstance(payload, dict) and isinstance(payload.get("success"), bool)]
    if not states:
        raise RuntimeError("Fusion returned no script completion status")
    return all(states)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:27182/mcp")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--list-tools", action="store_true")
    mode.add_argument("--script", type=Path)
    parser.add_argument("--read-only", action="store_true", help="Ask Fusion to enforce design read-only mode; not a Python sandbox")
    args = parser.parse_args()
    with FusionClient(args.url) as client:
        if args.list_tools:
            print("\n".join(tool["name"] for tool in client.tools))
            return
        source = INSPECT if args.inspect else args.script.read_text(encoding="utf-8")
        result = client.execute(source, args.inspect or args.read_only)
        print(json.dumps(result, indent=2))
        if not script_succeeded(result):
            raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print("Fusion MCP request failed: " + str(error), file=sys.stderr)
        raise SystemExit(1) from None
