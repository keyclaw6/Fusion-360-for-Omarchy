# Native Fusion automation

Checked on 2026-09-26 against installed Fusion 2705.1.25 and Codex CLI 0.155.1.
Live modeling and rendering still require the application acceptance checks.

## Supported local MCP server

Autodesk documents a native desktop MCP server. With Fusion running, open
**Preferences → General → API** and enable **Fusion MCP Server (runs locally
on this device)**. Apply the preference, then use the exact URL displayed
there. The documented default is `http://127.0.0.1:27182/mcp`, using Streamable
HTTP. Keep Fusion running and a document open. A separate MCP sign-in or a
third-party Fusion add-in is not required.

Source: [Autodesk's connection instructions](https://help.autodesk.com/view/fusion360/ENU/?guid=ADSKMCP_FusionDesktopMcp_connecting_to_the_fusion_mcp_server_html).
The [MCP overview](https://help.autodesk.com/view/fusion360/ENU/?guid=FMCP-OVERVIEW)
distinguishes this local modeling server from Autodesk's cloud data server.

The first listener check found the server disabled. It was subsequently
enabled explicitly in Fusion and its displayed endpoint was verified at
`http://127.0.0.1:27182/mcp`. The local client's `--inspect` request succeeded
against that endpoint. Check the preference's displayed address before
connecting; an arbitrary Wine listener is not evidence of an MCP server.

After connecting with a standard MCP client, initialize the session and
discover the live tools. Use the Execute tool and schema returned by
`tools/list`, rather than hard-coding a name. First run an inspection-only
script, then the prepared modeling fixture. The included client can test this
endpoint independently of agent configuration.

The repository's small client keeps the session in memory, ignores HTTP proxy
environment settings, rejects redirects, and deletes its session on normal exit
or failed initialization. It checks JSON-RPC response IDs and handles this
Fusion build's JSON responses; it is not a general-purpose streaming MCP client.

```sh
python3 validation/fusion_mcp.py --inspect
python3 validation/fusion_mcp.py --script validation/FusionValidation/FusionValidation.py
```

`--inspect` only reads the application version, open-document count, and configured
graphics preference. The second command creates a new fixture document and local
artifacts. A failed script produces a nonzero client exit status. This Fusion
build reports script errors in a JSON text envelope with `success: false`, even
when MCP's top-level `isError` is absent; the client checks that envelope
explicitly. The fixture writes and prints its report before propagating an
exception. Live read-only inspection and a deliberately raising read-only probe
verified exit codes 0 and 1 respectively on this build. Neither command
establishes independent application acceptance.

## Persistent Codex connection

The user configuration can register Fusion for future local Codex tasks in any
project. Codex's desktop app, CLI and IDE extension share this configuration on
the same host. Start Fusion and wait for its document UI before opening the
Codex session that will use it. After changing the configuration, restart the
Codex client's MCP connection or start a new session; an already-running task
does not automatically gain tools merely because this file changed.

From this repository, install the narrow registration and check it without
sending any requests to Fusion:

```sh
python3 configure-codex-mcp.py --install
python3 configure-codex-mcp.py --check
codex mcp get fusion360 --json
```

The helper adds only the stanza from [config/codex-mcp.toml](../config/codex-mcp.toml)
to `$CODEX_HOME/config.toml` (normally `~/.codex/config.toml`). It preserves all
existing configuration bytes and permissions, saves a private backup under
`~/.local/state/fusion360-for-omarchy/codex-config-backups/` (or `$XDG_STATE_HOME`),
and refuses symlinked files, shared hard links, conflicting registrations and
paths inside `agent-dot-files`. It does not edit credential files or agent
instructions, launch Fusion, or probe the server. Re-running it with the same
entry makes no changes.

```toml
[mcp_servers.fusion360]
url = "http://127.0.0.1:27182/mcp"
enabled = true
required = false
startup_timeout_sec = 10
tool_timeout_sec = 120
```

Fusion is optional at Codex startup: `required = false` allows unrelated tasks
to start while Fusion is closed. A closed Fusion instance still means its tools
are unavailable. The local endpoint uses the current Fusion session; this
configuration adds no authentication headers or separate sign-in.

With Fusion open and no other agent operating it, verify discovery using
`python3 validation/fusion_mcp.py --list-tools`, followed by the inspection-only
`--inspect` command. In a fresh Codex CLI session, `/mcp` shows the connected
servers. Discover the current tools before modeling; finish or dismiss native
modal dialogs first. The repository client remains a fallback for an existing
task whose tool catalog does not include Fusion.

To remove only this registration, use `codex mcp remove fusion360`. Avoid
restoring the whole backup over newer unrelated settings. Keep the private
backup outside this repository: it contains the previous user configuration.

On this machine, the stanza was installed on 2026-09-26 and
`codex mcp get fusion360 --json` confirmed an enabled Streamable HTTP server
with the configured URL and timeouts, without authentication headers. The
original configuration bytes were preserved; both the current config and its
backup remain mode `0600`.

A subsequent live session read the endpoint from this saved registration,
initialized successfully, and discovered four tools: `fusion_mcp_electronics_read`,
`fusion_mcp_execute`, `fusion_mcp_read`, and `fusion_mcp_update`. Its single
inspection-only script returned Fusion `2705.1.25`, three open documents, and
graphics preference enum value `1`, with `success: true`. The session was then
closed without changing a design or issuing UI commands. The host listener was
verified as `127.0.0.1:27182`, rather than a wildcard network binding. This proves
the saved endpoint supports discovery and execution; it does not prove that an
already-running Codex task has refreshed its tool catalog.

Source: [OpenAI's MCP configuration documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

The subsequent installed GE v3 review session exposed all four Fusion tools
directly in Codex's active tool catalog. A native `fusion_mcp_read` call listed
the two open validation documents; a read-only `fusion_mcp_execute` call
returned Fusion `2705.1.25`, 64 occurrences and 69 timeline features from the
active assembly. Both returned `success: true`. This verifies the direct
registered connection in addition to the fallback client's earlier checks.

The same registered `fusion_mcp_read` connection also succeeded after two true
cold launches through the Omarchy Apps menu. It returned the saved, unmodified
version 2 validation document after native Browser keyboard checks. No Codex
configuration rewrite or manual MCP reconnection was needed for those restarts.
After the final palette-hook review's third cold launch, another direct native
read succeeded against the new Fusion process and returned the same saved,
unmodified validation document. The active Codex connection survived that restart
as well.

## Installed Python execution contract

This build ships its API descriptions and schemas in
`Fusion/Server/Fusion/Resources/MCP/` under the registered deployment.
`ExecuteDescription.markdown` and `Schema/ExecuteSchema.json` describe the
following Execute arguments:

```json
{
  "featureType": "script",
  "object": {
    "readOnly": true,
    "script": "import adsk.core\n\ndef run(_context: str):\n    print(adsk.core.Application.get().version)\n"
  }
}
```

The Python source must define `run` with one argument. It can use the
normal `adsk.core` and `adsk.fusion` APIs. Printed text becomes tool output;
an unhandled exception becomes a tool error. For the modeling fixture,
provide its complete source as `object.script` and omit `readOnly` or set
it to false. Close active command dialogs before modifying the design.
The documented read-only option enforces that scripts do not change the
design and allows inspection while a command dialog is open. It is not a Python
filesystem/network sandbox, and Autodesk's bundled description specifically
excludes `Application.executeTextCommand` from its enforcement. Read-only
inspection scripts must avoid that method and any other side effects.

A live read-only inspection waited while the native Save dialog was open and
succeeded immediately after it closed. Native modal dialogs can therefore delay
requests even though Fusion permits read-only inspection during modeling command
dialogs. Finish or dismiss native modal dialogs and wait for document loading to
finish before using this client or the registered MCP tools. An inspection sent
while opening an interrupted test's recovery item coincided with an unresponsive
recovery dialog; the cause was not isolated, and that owned test session needed
restarting. Read-only design protection does not establish that a busy native
dialog can safely accept an API request. Preserve recovery files before any
forced restart; the test entry was backed up intact.

For acceptance, inspect the resulting bodies/features and capture the
actual rendered viewport after executing the fixture. A successful
JSON-RPC response alone does not demonstrate smooth rendering or input.
Keep save/reopen and restart checks in the live reviewer gate.

## Normal Scripts and Add-Ins route

The same fixture can run through Fusion's supported UI without MCP.
Open **Utilities → Add-Ins → Scripts and Add-Ins**. In the new dialog,
use the **+** menu's **Script or add-in from device** option to link the
fixture's folder, select it, and run it. The script folder, Python file,
and manifest should have the same base name. The file picker sees this
machine's repository through Wine's verified `Z:` mapping, for example
`Z:\home\YOUR_USER\Fusion-360-for-Omarchy\validation`.

Sources: [Managing scripts and add-ins](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-MANAGE-SCRIPTS-ADD-INS.htm),
[Creating and linking scripts](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/WritingDebugging_UM.htm).

Use the fixture's actual containing folder below `validation`, not the
parent folder if it holds several scripts or other validation material.
Running a script this way uses Fusion's bundled Python and API, rather
than the host machine's Python interpreter.
