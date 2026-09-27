# Critical audit of the selection rejection — 26 September 2026

**The broad rejection was premature. Test 2 has a working Normal-selection
configuration, including after native feature edits and a full cold restart.**
The earlier gray screenshots were real, but they did not establish an
unavoidable rendering defect in either runtime. Full application acceptance
remains pending.

## What the earlier review missed

The old probe established that some BRepFace was selected; it did not establish
which visible face. The click helper also warped/moved the pointer immediately
before mouse-down, so a delay before calling that helper did not guarantee a
settled pointer. Both routes shared Fusion, DXVK, inherited preferences and the
same test method. Their results were not independent evidence of a runtime cause.

The earlier blue screenshot taken just after selecting Simple was also an
inadequate positive control. This audit reproduced blue remaining immediately
after that preference change, followed by gray on a fresh selection. A screenshot
after changing a preference does not establish how subsequent clicks behave.

## Controlled reproduction

The root agent opened a new document from the preserved validation F3D on the
ordinary installed Wine 11.17 / Qt D3D11 / DXVK configuration. No runtime,
compiler, driver, desktop configuration or personal design was changed.

The API identified the visible front face by its 1440 mm² area, centroid
`[2.4, 0, 1.5]` cm and outward normal `[0, -1, 0]`. The camera was on its visible
side. Its projected screen location supplied the native click target. Selection
was cleared and verified empty; the pointer moved once, settled for 800 ms, then
received an 80 ms button hold with no intervening motion. Screenshots were taken
with the pointer away before the read-only selection probe. Fusion's native
status bar independently reported the same face area. Main-window focus was
checked by address and PID; the extrusion HUD was separately identified for input.

| Control | Observed result |
| --- | --- |
| Original Simple preference, fresh native click before any new edit | Correct visible face selected; gray |
| Explicit API selection of that exact face | Gray |
| Normal preference, API and fresh native selection | Blue |
| Native timeline edit from 8 to 10 mm, then fresh native selection in Normal | Blue; edited thickness and selected face verified |
| Switch back to Simple | Prior blue initially persists; clearing and reselecting yields gray |
| Restore Normal and select again | Blue on the identical post-edit face |
| Second native edit from 10 back to 8 mm, then native selection | Blue |
| Close Fusion and its dedicated Wine server, ordinary launch, reopen original F3D, native selection | Normal persisted; blue |

Face temporary IDs changed when geometry regenerated, so the comparison also
uses geometry, outward normal, area and screen position. Both Normal and Simple
are documented [Fusion selection display styles](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_SelectionDisplayStyles.htm).
This audit does not establish whether gray in Simple is intended on native
Windows/macOS or is a compatibility issue. It does establish that Normal avoids
the reported selection blocker in these tests.

An optional graphics getter, `degradedSelectionDisplayStyle`, returned
`Low-end graphics card`; this is not proof of software rendering. The cold
session still used the pinned runtime identity, Radeon RADV, DXVK and native
Autodesk compiler. Dynamic graphics and the Custom preset remained unchanged.
No frame-rate or complete Windows/macOS parity claim is made.

## Independent audit and remaining gate

A fresh agent, `review_method_audit`, independently inspected the evidence and
revised its initial interpretation after the A/B/A comparison. It agreed that
the whole-route rejection was premature and explicitly retracted treating the
immediate Simple screenshot as a valid positive control. The root operated
the application during this audit; this is not the final independent operational
acceptance requested by the user.

Normal is retained in the local Test 2 profile. Test 1's runtime and profile
were not changed or retested with this control. Neither route is marked accepted.
The next useful work is the remaining operational review: cloud save/reopen,
local round trips, sustained navigation, menus/modals and mixed-monitor behavior.
The optional Omarchy plugin remains uninstalled. No agent-dot-files were changed.

## Private evidence

`~/.local/state/fusion360-for-omarchy-wine/reviewer-audit-20260926/` contains
screenshots, face/camera state, input helpers and runtime checks. Key pairs:

- `baseline-native-click-pointer-away.png`, `baseline-native-click-state.json`
- `explicit-front-selection-pointer-away.png`, `explicit-front-selection-result.json`
- `normal-native-click.png`, `normal-native-click-state.json`
- `normal-after-native-edit-selected.png`, `normal-after-native-edit-selected-state.json`
- `simple-style-immediate.png`, `simple-roundtrip-native-click.png`, `simple-roundtrip-state.json`
- `normal-second-native-click.png`, `normal-second-state.json`
- `normal-edit-back-selected.png`, `normal-edit-back-selected-state.json`
- `cold-native-selection.png`, `cold-native-selection-state.json`
- `cold-runtime-status.json`, `cold-graphics-modules.json`

The original rejected-review evidence and original F3D remain intact.
