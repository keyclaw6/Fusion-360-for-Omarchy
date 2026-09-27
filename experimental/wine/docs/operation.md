# Operating this local experiment

This is a test installation awaiting full acceptance. The original selection
rejection was narrowed by the [critical audit](reviewer-audit.md). It does not
replace the original experiment's repository or prefix.

```sh
fusion360-for-omarchy-wine launch
fusion360-for-omarchy-wine status --json
```

The application menu entry is **Fusion 360 for Omarchy — Wine Test 2**. The
ordinary launch uses the exact runtime and Qt environment in the lock, starts
Identity Manager, waits for fresh SSO readiness and then starts Fusion in a
detached systemd user service. It does not require Steam, umu or a terminal
window to remain open. A repeated launch reuses the running session; explicit
window focusing is not yet implemented by this test launcher.

The current final-round candidate uses DirectX 11 for both the modeling canvas
and Qt UI, the Microsoft compiler shipped by Autodesk (including a private
system32 copy for Qt), and the source-matched Wine 11.17 transparency module.
The lock requires both alpha opt-ins and verifies both compiler copies before
launch. The independent reviewer rejected Simple-mode face highlights; the
later audit demonstrated working Normal-mode selection through native feature
edits and a cold restart. The local profile now retains Normal. The launcher
does not itself enforce that preference. See [review.md](review.md) for history
and [reviewer-audit.md](reviewer-audit.md) for the correction.

| Item | Path |
| --- | --- |
| Prefix | `~/.local/share/fusion360-for-omarchy-wine/prefix` |
| Runner | `~/.local/share/fusion360-for-omarchy-wine/fusion-wine-11.17` |
| Installed helpers and lock | `~/.local/share/fusion360-for-omarchy-wine/{bin,lib,compatibility-lock.json}` |
| Private integration/recovery record | `~/.local/share/fusion360-for-omarchy-wine/integration-record.json` |
| Private evidence | `~/.local/state/fusion360-for-omarchy-wine` |

The renderer experiment can be chosen explicitly with
`launch --qt-backend default|opengl|d3d11`, after closing the current session.
This changes Qt UI composition, not Fusion's own modeling-canvas preference.
An existing process with a different renderer or runtime is rejected. Do not
launch another runtime against this prefix to bypass that check.

Authentication uses the current session record and the dedicated Wine prefix.
If the Wine server exits between the callback's process check and invocation,
Wine can restart that same prefix's server; attachment is not atomic. The
callback cannot select the first experiment or the default Wine prefix. Both
callback and browser-helper output are suppressed; URLs are passed literally,
without shell evaluation.

To restore Test 1's authentication association after closing Test 2, first
confirm the current handler is still the owned Test 2 entry, then restore the
`previous_adskidmgr_handler` recorded in the private integration record.
Retain the Test 2 prefix and backups until all validation work is preserved.
Never point the first runtime at the migrated second prefix or overwrite the
first prefix with it.

Installation from scratch, update/rollback packaging, Open With, automatic
focus and optional Omarchy widget integration are not yet complete for this
second route. They follow a successful native application review.
