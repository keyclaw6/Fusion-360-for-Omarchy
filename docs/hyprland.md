# Fusion window rules

The Fusion desktop integration needs scoped Hyprland rules on this Omarchy
configuration. Omarchy enables `misc.focus_on_activate` globally. A Fusion menu
can trigger reactivation of its main X11 window; Hyprland then warps the pointer
to that window's center. Testing the candidate with the rule set to `false`
removed that warp. This rule does not fix renderer or palette defects, which
must be addressed and verified independently.

The installed Hyprland 0.56.2 behavior is visible in
[the activation path](https://github.com/hyprwm/Hyprland/blob/efb50993780079460b0cbed1363e2166a2de1d9f/src/desktop/view/Window.cpp#L1363).
The [current window-rule reference](https://wiki.hypr.land/Configuring/Basics/Window-Rules/)
documents the per-window Lua effect.

There is no supported per-window warp-only setting in this version. Both the
activation handler and Lua focus dispatcher focus the window and then warp the
pointer; suppressing that globally would affect unrelated applications. The
scoped activation rule therefore remains the smallest supported correction.
`render_unfocused` does not repair delayed toolbar painting: its timer skips
visible windows, and normal rendering of visible windows does not test keyboard
focus. Read-only X11 checks showed the Fusion main window focused while both
utility palettes were unfocused. `WM_HINTS.input=false` is paired with
`WM_TAKE_FOCUS` and does not mean input is disabled.

A separate rule removes the compositor border from Fusion's frameless
`Msg:QTView:...MessageTray` notification window. Its empty, fully transparent
surface otherwise leaves a visible rectangle over the canvas. The match requires
the exact Fusion class, Xwayland, and that title pattern; other Fusion windows
keep their existing borders. This changes only `border_size`, preserving the
notification window's content, mapping, and input behavior.

The block retains these two rule effects:

```lua
o.window({ class = "^steam_app_fusion360$", xwayland = true }, { focus_on_activate = false })
o.window({ class = "^steam_app_fusion360$", title = "^Msg:QTView:.*MessageTray$", xwayland = true }, { border_size = 0 })
```

It is appended after the existing Omarchy defaults in
`CONFIG_HOME/hypr/hyprland.lua`. The installed `default.hypr.apps` loader scans
only packaged files under `/usr/share/omarchy/default/hypr/apps`; there is no
automatic user `hypr/windows.lua` or `hypr/apps/` include. A separate app file
would require another config edit, so this integration owns only the marked
block. Normal mouse clicks, keyboard focus, and other applications retain their
existing rules. No `no_focus`, `no_follow_mouse`, or global focus change is added.

The workspace hook keeps mapped Fusion XWayland windows of the same process
with its unique main window. Moving a palette or dialog also carries the rest of
that process's group. Newly opened children join the main window's workspace.
The observed main title is `Autodesk Fusion` (surrounding whitespace ignored).
Save is a NORMAL X11 window without a transient-owner property, so limiting the
hook to Browser/Comments left its modal behind. Multiple main windows, other
processes/classes and unmapped windows are excluded. Floating physical sizes
are preserved across monitor scale changes; recursive callbacks are guarded.

Fusion's utility windows (`initial_title` exactly `Fusion360`) have `no_anim=true`.
Qt already updates their positions during native dragging. Animating those
updates through Omarchy caused reversals against the cursor; both drag directions
passed after the scoped rule. Main-window and other-app animations remain enabled.

The focus/fullscreen hook repairs stacking eligibility only while the active
window belongs to the unique same-process Fusion group. It raises the main
window, then palettes/backdrops, then other Fusion dialogs so Save remains above
its gray veil. Only members lacking eligibility are normally raised; an already
eligible modal is raised again if a preceding member needed repair. No focus,
hide, cursor or global configuration command is dispatched. If native pointer
handling switches focus to another application, repairs stop. Opening a window,
moving the group between workspaces or changing fullscreen schedules one repair
after 600 ms, force-raising only actual dialogs after the compositor settles.
A newer event cancels the older timer. The timer keeps the unique main window
and checks its group afresh, so a disappearing backdrop does not lose repair of
a still-open Save. Independent live review passed on 2705.1.30, including native
input, pre-input rendering, focus away during the timer, workspace movement and
Cancel; see the ordered work record.

The launcher captures its invoking workspace before slow initialization. When
there are no existing Fusion windows, a temporary named rule places new Fusion
windows there silently. The splash shares the main window's title, so the rule
stays until a unique main and its same-process MessageTray are mapped. Open and
close events both check readiness; a closing splash is excluded even while its
mapped flag remains set. A two-minute timeout releases failed launches. Cleanup
removes that attempt's timer and both subscriptions; its token prevents delayed
cleanup from disabling a later retry.
Future child windows follow the persistent workspace hook. Omarchy's
global launch tracking and other application behavior are unchanged.

See [the ordered reproduction and validation record](issues-2026-10-07.md) for
live evidence and limits. The complete owned block comes from
[the integration helper](../lib/fusion360_hyprland.py).

## Helper contract

`lib/fusion360_hyprland.py` exposes:

```python
install_focus_rule(config_path: Path, state_dir: Path) -> bool
remove_focus_rule(config_path: Path, state_dir: Path) -> bool
rollback_focus_rule(config_path: Path, state_dir: Path) -> bool
validate_lua(config_path: Path) -> None
```

The boolean reports whether configuration bytes changed. Failures raise
`FocusRuleError`. The installer supplies its selected config and state paths;
the helper never assumes that another app-specific Lua file is included. It
does not execute Lua, start Fusion, request a compositor reload, or install the
optional shell widget.

Before a config write, the helper parses the complete candidate with `luac -p`
and creates a byte-for-byte backup, SHA256 hashes, original mode, and ownership
record in `STATE/hyprland-focus/`. That directory is private (`0700`), with
backups and records at `0600`. State is refused inside a Git repository.
Configuration symlinks, symlinked parent directories, and paths through
`agent-dot-files` are refused. The config must already exist as a user-owned
regular file.

Repeated installation does not duplicate the block. Removal requires its exact
unchanged text and ownership record; user changes outside the block remain.
An edited, duplicated, or unowned block is preserved and reported. An unchanged
installation restores the original bytes, including a missing final newline.
Current config permissions are preserved. A second private backup precedes
removal, and all backups remain available afterward. If the file changes while
the candidate is being prepared, the helper refuses to overwrite that edit.

Eight exact block versions are recognized: the original two rules, monitor
following, group eligibility, workspace grouping, palette dragging, and the
dialog grouping/stacking, deferred fullscreen repair, and deferred open/workspace
repair. Earlier versions
are frozen byte for byte.
Upgrading saves both the exact previous configuration and raw ownership record
before replacing the owned block. Each history link must lead to a strictly
older known version. Removal still preserves surrounding user edits and the
original uninstall baseline. `rollback` restores one earlier block and its exact
record while retaining later edits outside the block; a second rollback can
restore the original two-rule version. An interrupted upgrade completes its
recorded target before considering a newer version. None of these actions rolls
back Fusion, its graphics modules or user preferences. Recovery files stay private.

## Controlled application and removal

The supported installer has applied this block on the implementation machine;
`hyprctl configerrors` returned no errors. Further live application and reload
must be coordinated with any ongoing desktop work. The helper's CLI
requires explicit paths, for example:

```sh
python3 lib/fusion360_hyprland.py install \
  --config "$HOME/.config/hypr/hyprland.lua" \
  --state "$HOME/.local/share/fusion360-for-omarchy"
```

Once a config change is authorized and applied, validate and reload through the
normal installed interface:

```sh
python3 lib/fusion360_hyprland.py validate --config "$HOME/.config/hypr/hyprland.lua"
hyprctl reload
hyprctl configerrors
```

Omarchy watches its configuration, so writing it can already trigger a reload;
do not treat omission of the explicit reload command as an isolation mechanism.
Test the profile menu, Preferences, real dialog keyboard input, window switching,
the empty MessageTray border, and an ordinary cold launch. Keep this acceptance separate from the
[optional widget](plugin.md).

To remove the owned rule, use the same state and config paths with the `remove`
action, then validate, reload, and inspect config errors again. Do not restore a
whole old config backup over newer unrelated user changes. The automatic remove
path edits only its owned block; retained private backups are for deliberate
recovery.

To reverse one integration upgrade:

```sh
python3 lib/fusion360_hyprland.py rollback \
  --config "$HOME/.config/hypr/hyprland.lua" \
  --state "$HOME/.local/share/fusion360-for-omarchy"
hyprctl reload
hyprctl configerrors
```

Rollback restores the immediately preceding installed block, including its
documented limitations. Repeated rollback traverses the recorded installation
history. The `remove` action instead removes all unchanged owned
Fusion rules, including the older focus and notification corrections.

The focused automated checks use temporary config/state directories and the real
Lua parser. They cover exact round trips, private backups, idempotence, surrounding
edits, changed blocks, invalid Lua, symlinks, repository isolation, concurrent
edits, altered ownership records, and the exact scope of all three rule effects. They
also exercise the event payload in an isolated Lua harness, legacy migration,
rollback and interrupted recovery. They never operate the live compositor.
