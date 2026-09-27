# Fusion palettes after application switching

The installed GE v3 review reproduced a separate desktop integration defect
after the monitor-position repair: returning to Fusion could show the model
while leaving Browser and Comments invisible and unable to receive input.
Their workspace and coordinates were correct. Hyprland reported the main
window as eligible above fullscreen windows, but the palettes as ineligible.
One targeted raise of the missing Browser immediately restored it.

## Source diagnosis

The installed Hyprland 0.56.2 source, revision
`efb50993780079460b0cbed1363e2166a2de1d9f`, explains the distinction:

- `src/desktop/state/FocusState.cpp` restores eligibility for the focused
  floating window itself.
- `src/desktop/state/WindowState.cpp`, `moveToZ`, changes eligibility, input and
  fade state for the explicit target. It moves X11 transient descendants in
  stacking order without applying that same state update to each descendant.
- `src/desktop/view/Window.cpp`, `isAllowedOverFullscreen`, does not inherit
  this eligibility from an X11 transient parent.

The supported Lua `window.alter_zorder` dispatcher updates these states for a
targeted window. It also simulates pointer movement, so preserving useful focus
and keyboard input must be checked live. `window.bring_to_top` reaches the same
implementation; it is not a focus-neutral alternative. There is no writable
per-window eligibility property in this version. Disabling palette focus would
break keyboard input and is not part of the repair.

## Bounded live experiment

A temporary callback on `window.active` and `window.fullscreen` raised only
ineligible members of the currently active Fusion window group. Main was first,
followed by its two known palettes. A local guard prevented reentrant callbacks.
It did not hide/lower windows, move the pointer, dispatch focus, poll, or change
rendering. Fixed process/window identifiers were used only in this private
diagnostic, not as a portable installation contract.

Eight ordinary Alt+Tab cycles and four pointer-position controls passed. When
Fusion became active, the main and both palettes were visible and interactive;
when the other application covered it, the group became ineligible normally.
Recorded callback focus addresses did not change during the tested repairs.
Native Browser expansion, Body1 selection, its context menu, inline Rename
typing and Escape cancellation also passed. A subsequent direct MCP read
confirmed that the validation document remained saved and unmodified.

These observations support the scoped repair. They are not a universal claim
about every fullscreen combination or a substitute for independent review of
the portable installed version.

## A rejected Fusion-specific diagnosis

During these controls, maximizing and restoring a floating window over an
already-maximized Zen window could clear active focus. An initial terminal
comparison failed to hold Zen's fullscreen state constant and was invalid.
With that state matched, a native Foot window lost focus in all four cycles,
just as Fusion did. Fusion retained focus in all four cycles when Zen was not
maximized. The behavior also occurred without the experimental Fusion hook;
temporarily enabling `focus_on_activate` for the main window did not cure it.

This is a reproduced general Hyprland fullscreen interaction, not evidence of
a Fusion rendering failure or a reason to add another Fusion focus workaround.
The earlier Fusion-specific interpretation is withdrawn. The independently
reproduced missing-palette eligibility issue above remains distinct.

Both temporary Foot controls were closed, Zen was restored to its initial
non-fullscreen state, the temporary activation override was removed, and the
diagnostic trace subscriptions were removed.

## Evidence and review

Private evidence is under
`~/.local/state/fusion360-for-omarchy/focus-repair-20260927/`:

- `before-targeted-raise.*`, `after-targeted-raise.*`
- `float-cycle-geometry.json`, `float-cycle-*-browser.png`
- `hook-event-details.txt`, `pointer-controls.json`, `pointer-hook-events.txt`
- `browser-context-input.png`, `browser-rename-keyboard-before-cancel.png`,
  `browser-rename-cancelled.png`
- `matched-native-foot-over-maximized-zen.json`,
  `no-other-fullscreen-control.json`, `no-hook-native-maximize-control.json`,
  `activation-true-maximize-control.json`, `no-hook-maximize-focus-events.txt`

The portable hook was deployed through `install.py --integration-only
--no-packages --no-register` and `hyprctl reload`. Configuration errors were
empty. The temporary exact-window callback was removed before deployment;
both its global and the diagnostic trace global were confirmed absent. All 26
installed manifest entries matched their receipts, and the runtime compatibility
lock was unchanged. The installed block SHA256 is
`9239f81b3ad92a9ca2460f5f85d71ff4fd934fd6ec1ff4fda37c428b10341ae2`;
the helper SHA256 is
`5b8db34d9576093843470ca135a6813771dfcc8789ae40e8fbf5189135b5f045`.

Thirty-seven focused tests passed without skips, covering group scope,
reentrancy and failure handling, the unchanged monitor hook, three-version
migration, nested recovery records, rollback, surrounding user edits, and
installer integration/removal. After installation, native Browser context-menu
Rename, keyboard typing and Escape cancellation passed again. The initial
capture immediately after configuration reload showed a black canvas; the
settled capture after ordinary pointer movement showed the complete selected
part. No API redraw, resize or renderer restart was used between those captures.
This reload transition is recorded separately from settled-state acceptance.

Deployment and smoke-test evidence adds `before-portable-deployment.json`,
`portable-deployment.json`, `portable-owned-files-verified.json`,
`portable-first.png`, `portable-settled.png`, `portable-context-menu.png`,
`portable-keyboard-rename.png` and `portable-keyboard-cancel.png`.
The independent reviewer accepted the installed application on 27 September
after four ordinary Alt+Tab returns, neutral-app coverage without stray palettes,
Browser interaction, settled context-menu Rename typing/cancellation, the former
exact-main focus/Escape failure, another mixed-scale move and physical drag,
and a genuine Apps-menu cold launch with newly created windows. The saved cloud
version 2 reopened complete and unmodified. No persistent black frame appeared
in settled use. Evidence, shortcut observations and limits are recorded in
[operational-review.md](operational-review.md).
