# Optional Omarchy plugin

The `kab.fusion360` bar widget opens the separately installed Fusion launcher,
reports installation and process status, and displays local diagnostics. It does
not install Fusion, change its renderer, refresh credentials, or manage its
runtime. Disabling or removing the widget leaves the ordinary desktop launcher
and application data intact.

The plugin passed local interaction and lifecycle review on 27 September 2026
and is installed and enabled on this machine. The [live review](plugin-review.md)
records the tested scope and deployed hashes. Widget validation does not establish
Fusion compatibility or replace the independent application acceptance gate in
[acceptance.md](acceptance.md). The widget source is included in this public repository; it has not been submitted to the Omarchy plugin marketplace.

## Installed contract

Development targets Omarchy **4.0.4-1**, inspected on 26 September 2026. This
installation supports manifest `schemaVersion: 1`, `kinds: ["bar-widget"]`, and
`entryPoints.barWidget`. A root `Main.qml` extends the installed `qs.Ui.Panel` and
uses `WidgetButton`, `KeyboardPanel`, `PanelKeyCatcher`, and the shell's theme
tokens. The nested popup is part of the widget and has no separate manifest kind.

The [official development guide](https://plugins.omarchy.org/develop.html) and
[publishing guide](https://plugins.omarchy.org/publish.html) were checked against
the installed sources in `/usr/share/omarchy/shell` and the installed validator.
The widget uses the scoped bar facade and its normal panel lifecycle; it does not
read or edit shell configuration. Older Omarchy installations can continue using
the ordinary desktop launcher without this plugin or a forced shell upgrade.

## Launcher interface

The desktop integration must put `fusion360-for-omarchy` on the shell's `PATH`.
The widget passes fixed argument arrays directly to Quickshell:

| Action | Command | Behavior |
| --- | --- | --- |
| Open Fusion | `fusion360-for-omarchy launch` | Detached from the widget's lifetime |
| Status | `fusion360-for-omarchy status --json` | Refreshed when opened or requested; eight-second timeout |
| Diagnostics | `fusion360-for-omarchy diagnostics` | Only requested by the user; ten-second timeout |

Status requires `schema_version: 1` and boolean `installed`, `running`,
`runtime_ready`, and `session_attachment_ready` fields. Optional
`fusion_version` and static `errors` are shown as plain text alongside a short
application status. If the optional `session_conflict` field is `true`, the panel
asks the user to close the other Fusion session and disables Open Fusion. Other
additional status fields do not change the panel's contract.

Technical runtime and session-attachment details appear only in the explicitly
requested diagnostics. The widget does not
infer a signed-in account, cloud access, hardware acceleration, or acceptance from
these fields. Runtime readiness is only a launcher preflight result. Session
attachment readiness means that the expected live runtime bus and a matching
Fusion or Identity Manager process are available. It does not validate MIME
registration, WineBrowser callbacks, browser sign-in, or cloud access.

Diagnostics uses the launcher's sanitized human-readable report, displayed as
plain text and limited to 12,000 characters. No command output is deliberately
forwarded into the shell journal, no report is saved by the widget, and no browser
callback, token, cookie, or credential is handled here. All subprocesses run as the
current user. There are no install hooks, privileged commands, downloads, or
automatic recurring processes.

Closing the panel cancels an in-flight diagnostic request and invalidates its
result. Reopening starts at the compact status and action buttons; diagnostics
are collected again only when requested.

## Validate without installation

From the repository root:

```sh
omarchy plugin validate "$PWD"
qmllint -I /usr/share/omarchy/shell Main.qml
```

The system `qmllint` on this machine is the older syntax checker. Qt 6.11.2's
analyzer is also installed at `/usr/lib/qt6/bin/qmllint`; see the validation record
below for its import-path requirements and results.

## Local enablement after application acceptance

Install the standalone desktop integration first and confirm its independent
acceptance results. To make a local plugin copy, copy only `manifest.json` and
`Main.qml` into a new `~/.config/omarchy/plugins/kab.fusion360/` directory. Do not
overwrite an existing plugin directory or use symlinks. Run the validator against
that directory, then request shell discovery and explicit enablement:

```sh
omarchy plugin validate "$HOME/.config/omarchy/plugins/kab.fusion360"
omarchy-shell shell rescanPlugins
omarchy plugin enable kab.fusion360 --section right
```

Plugin discovery is asynchronous. If enablement reports that the plugin is not
known immediately after a rescan, wait for it to appear in `omarchy plugin list`
before enabling it. When replacing an already loaded QML file, a shell restart
provides a fresh-load check before accepting the replacement.

Left-click **Fusion** to open the panel. Use its buttons or Up/Down and Enter.
`R` refreshes status, `D` collects diagnostics, Escape closes the panel, and Tab
uses Omarchy's normal panel switching. Shell lifecycle checks are:

```sh
omarchy-shell shell summon kab.fusion360 '{}'
omarchy-shell shell hide kab.fusion360
```

Before treating the plugin as accepted, verify click, keyboard behavior, missing
launcher errors, status, diagnostics, detached launch, disable/re-enable, shell
restart, and removal. Confirm Fusion still opens from its ordinary desktop entry
after disabling and removing the widget:

```sh
omarchy plugin disable kab.fusion360
omarchy plugin remove kab.fusion360 --yes
```

The installed removal command moves a local non-Git copy into
`~/.config/omarchy/plugins/.kab.fusion360.bak.<UTC timestamp>` and removes its bar
entry. Preserve unrelated configuration edits rather than restoring an entire
older `shell.json` backup.

Omarchy marketplace submission remains separate from publishing this source
repository. The
marketplace's manifest checks do not certify Autodesk compatibility.

## Validation record

On 26 September 2026, the initial `omarchy plugin validate` and system `qmllint`
syntax checks passed for this repository without live shell configuration changes.
The launcher's `status --json` and `diagnostics` commands were also exercised
read-only from the repository; both returned the documented fields successfully.
The plugin did not launch Fusion during this check.

Qt 6.11.2's analyzer was also run with the actual shell imports. Quickshell maps
the `qs` namespace at runtime; for a standalone analyzer, create a temporary import
root outside the repository with a `qs` link to `/usr/share/omarchy/shell`, then
use that root with `-I`. This resolves all plugin components. The remaining seven
warnings concern the installed shell's dynamic `QObject` properties
(`bar.foreground`, `bar.fontFamily`, and `Style.font` members). The same warnings
occur in the installed first-party panels, and the referenced members were
verified in the installed sources. They are recorded rather than hidden with
warning suppression. This is static validation, not a live plugin test or
application acceptance.

These checks were repeated on 27 September after the live-review lifecycle fix.
The source and final installed copy both pass the manifest validator, the system
syntax checker passes, and Qt 6 reports the same seven documented warnings with
no new diagnostics. See [the live review](plugin-review.md) for actual interaction,
failure handling, restart, and removal results.
