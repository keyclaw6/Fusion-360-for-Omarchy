# Fusion palettes on mixed-scale monitors

During the installed GE v3 operational review, moving the individual Fusion
window from DP-1 (scale 1.5) to DP-3 (scale 1.0) stranded Browser and Comments
on the original workspace. A normal Super + left-button drag reproduced this.
Moving an entire workspace had passed an earlier review; that exercises a
different compositor path.

## Diagnosis

Both palettes had the correct X11 `WM_TRANSIENT_FOR` main-window owner, process
ID and utility-window type. Their native X11 rectangles were correct. Hyprland
kept the old monitor association and therefore converted the new rectangle
through the old monitor's scale and origin. For example, native Browser
position `[164,1404]` became offscreen logical `[-851,1936]`; on DP-3 its correct
logical position was `[2724,1404]`.

The installed Hyprland 0.56.2 source (revision
`efb50993780079460b0cbed1363e2166a2de1d9f`) corroborates this distinction:
`GlobalWindowController.cpp` moves the selected window without its transients;
`WorkspacePlacementController.cpp` updates every workspace member. The drag
controller likewise moves only the dragged target. In `Window.cpp`, X11
configure handling converts coordinates using the window's current monitor.

The main-window workspace event runs before its monitor field is updated.
The repair must use the event's destination workspace and monitor. Moving the
palettes there and preserving their physical size across the scale change lets
normal Fusion layout supply their final positions. No graphics-driver change
is involved.

## Controlled live experiment

The smallest tested hook moved the two verified live palettes to the supplied
destination and resized by `old_scale / new_scale`. It used no polling, timers,
external geometry reassertion, position overrides or animation overrides.

Root checks passed four floating transfers, three maximized transfers, and
normal mouse dragging in both directions. Browser labels, Comments, model
edges and holes remained visible. Native Browser row selection and component
expansion worked after transfer. These implementation checks supplement the
independent reviewer; they do not constitute final acceptance.

An apparent additional corruption in some reduced screenshots was model
geometry visible through the intentionally transparent Browser. Full-resolution
native XComposite and composited Browser captures showed intact text. This
observation does not negate the separately reproduced workspace-position bug.
Transition captures taken while windows were resizing were not treated as
settled-state failures.

Private experiment evidence is under
`~/.local/state/fusion360-for-omarchy/monitor-repair-20260926/`:
`before-repair.json`, `native-browser.png`, `composited-browser.png`,
`simple-follow-*`, `max-follow-*`, `mouse-drag-*`,
`browser-click-after-move.png` and `browser-expanded-after-move.png`.
The earlier diagnostic scripts with fixed process/window IDs are not part of
the installed integration.

## Deployment and independent review

The portable hook was deployed through `install.py --integration-only
--no-packages --no-register`, using the existing application state directory.
The runtime compatibility lock remained byte-identical. The installer migrated
the exact owned legacy block, retained its private configuration/record backups,
and deployed the same helper bytes as the repository. `hyprctl reload` returned
`ok`; `hyprctl configerrors` was empty.

The installed block SHA256 is
`f67ad6bc9e2cf463d2c576142679a984eb5b4b2838915df6b3001f993c45b778`.
The helper SHA256 is
`6728f89d3a5dad7f5bb408ec4be2efa37829d42a4892417cf89b1d0cd0b9254c`.
Twenty-eight focused checks passed without skips: 26 ownership/event tests and
two installer registration/removal tests. Private deployment evidence is
`before-portable-deployment.json` and `portable-deployment.json` in the same
experiment directory.

Fusion and its dedicated runtime were closed before the handoff. The temporary
experiment subscription was removed and per-window overrides ended with the
old windows. The independent reviewer passed individual maximized-window moves
in both directions, physical Super + left-button dragging in both directions,
and native Browser expansion and selection on DP-3. Two ordinary desktop-entry
cold launches also passed, with cached authentication and cloud document reopen.
The runtime and renderer remained unchanged.

That review separately found missing palette eligibility after application
focus changes; see [the focus diagnosis](focus-integration.md). The hashes above
identify the monitor-only block tested at that checkpoint. Final acceptance and
subsequent integration identities remain in
[the operational report](operational-review.md).
