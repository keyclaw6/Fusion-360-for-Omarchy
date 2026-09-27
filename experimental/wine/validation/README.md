# Fusion's native MCP server

This installation uses Autodesk Fusion's built-in MCP server. The machine's
Codex registration already points to `http://127.0.0.1:27182/mcp` and is enabled.
The registration is personal machine configuration; no credentials or copy of
that file belong in this repository. Only one tested Fusion instance should own
the endpoint at a time.

The standalone helper is copied from Test 1 and uses the same protocol. It
discovers Fusion's actual tool schema, keeps the MCP session header in memory,
checks script completion, and closes the session. It does not log credentials.

```sh
python3 validation/fusion_mcp.py --list-tools
python3 validation/fusion_mcp.py --inspect
python3 validation/fusion_mcp.py --script /private/path/to/script.py
```

Scripts use Fusion's normal `def run(_context)` entry point. `--read-only` asks
Fusion to enforce a read-only design operation; it is not a Python sandbox.
Only connect once the application has finished startup and no modal dialog is
open. A pending Save/Open/login/recovery dialog can prevent Fusion's UI thread
from processing script requests. Finish the dialog first.

Live reads and guarded export/reopen operations have worked under Test 2. That
does not establish correct native rendering or replace the reviewer's GUI
tests. Evidence screenshots and test F3D files remain in private state outside
Git.
