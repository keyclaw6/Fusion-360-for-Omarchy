# Local widget acceptance

**Verdict: accepted for the tested scope, 27 September 2026.**

The `kab.fusion360` widget is installed and enabled in the right bar section on
Omarchy 4.0.4-1. Review followed the independent application acceptance on the
installed GE v3 runtime. Only `manifest.json`, `Main.qml`, and the widget's bar
entry were installed; Fusion's runtime and core integration were unchanged.

| Check | Observed result |
| --- | --- |
| Mouse interaction | The Fusion bar button opens the themed panel. Refresh, Diagnostics, and Open Fusion respond to clicks. |
| Status | Shows “Fusion is running” and version 2705.1.25; technical runtime details remain in requested diagnostics. |
| Keyboard | R refreshes, D collects diagnostics, arrows and Enter activate actions, Escape closes, and Tab/Shift+Tab switch to the neighboring panel and back. |
| Long diagnostics | The complete report can be scrolled to its final errors row. |
| Reopening | After scrolling and closing, reopening shows the compact status and action buttons. |
| Request cancellation | Closing during collection and immediately reopening leaves diagnostics collapsed. A new request then completes normally. |
| Missing launcher | Only the installed widget's status command was temporarily replaced with a nonexistent executable. The eight-second timeout showed a useful error; Open Fusion stayed disabled and Enter left the panel open. Exact production bytes were restored afterward. |
| Launch independence | Open Fusion closes the panel and hands off through the detached launcher. Fusion remained running when the widget was disabled and the shell restarted. |
| Enablement lifecycle | Disable/re-enable and a fresh shell start retained normal widget operation. |
| Removal | The supported remove command backed up the two-file copy and removed discovery/layout entries. The resulting shell configuration matched the pre-install JSON semantically. |
| Ordinary launcher | With the widget removed, `gtk-launch fusion360-for-omarchy` opened the existing saved Fusion session. Desktop entry and launcher hashes were unchanged. |
| Final state | The verified copy was reinstalled and enabled; final mouse and keyboard checks passed. |

The Open action was tested against the already-running Fusion application. Cold
application starts were covered by the separate application review; this widget
review does not claim a separate widget-triggered cold-start test. No design was
edited. A final enforced read-only MCP check confirmed the saved cloud document
at version 2, `isModified=false`, an 8 mm extrusion, and zero selected entities.

The live test found one source issue: a reopened panel retained its diagnostic
scroll position. The fix clears the report and scroll position on open, cancels
diagnostics on close, and invalidates canceled results before applying output.
The fixed behavior passed normal and immediate close/reopen checks.

Both source and installed manifest validation pass, as does the system QML syntax
checker. Qt 6.11.2 resolves the shell imports and reports only the same seven
documented dynamic `QObject` property warnings; it reports no additional errors.

| Deployed file | SHA256, identical in source and installed copy |
| --- | --- |
| `manifest.json` | `19b4c3364ff96f67d01cbb2dd6a0d22cc481ba6c56562703280ba7a037bf61dd` |
| `Main.qml` | `2c0d6ccb1344b53a435cec7a65e0cb64d9da369f9d0c758fd6565ddeef7498e0` |

Private configuration backups, screenshots, and the live receipt are under
`~/.local/state/fusion360-for-omarchy/plugin-acceptance/20260926T220446.342924Z/`.
The removal test retained its local copy at
`~/.config/omarchy/plugins/.kab.fusion360.bak.20260926230815/`.
No `agent-dot-files` paths or symlinked configuration files were modified. Idle
settings were preserved for the coordinating agent to restore after testing.
