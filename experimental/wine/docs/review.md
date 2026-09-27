# Independent native review — 2026-09-26

**Later correction:** this is the historical Simple-mode review. The
[critical audit](reviewer-audit.md) found working Normal-mode selection after
native edits and a cold restart. The gray observation stands, but the inference
of an unavoidable post-edit runtime defect was premature. Full acceptance is
still pending; the original evidence and report below are preserved.

**Result: rejected. The user's independent acceptance gate has not passed.**

This review operated the installed Test 2 candidate through the native Fusion UI. The final tested session was PID 717259, Hyprland window `0x562707e43200`, on DP-1 at 150% scale. Runtime handoff identified Wine 11.17, the source-matched X11 alpha module with both alpha flags, Qt D3D11, the native DirectX 11 modeling canvas, Autodesk's native `d3dcompiler_47` copies, and Simple selection. The reviewer changed no runtime, compiler, graphics preference, or desktop setting.

## Blocking result

The first settled face selection after an extrusion edit did not display the expected blue selection highlight. The face stayed gray in both captures, although a subsequent read-only Fusion query reported `SelectCommand`, one selected `adsk::fusion::BRepFace`, three timeline entries, and an extrusion distance of 8.0 mm.

The native sequence was:

1. Start a sketch on the visible front origin plane.
2. Toggle Sketch Grid off and on, restoring its original enabled state.
3. Draw a dimensioned 50 × 30 mm rectangle and finish the sketch.
4. Extrude it 6 mm.
5. Apply a 2 mm fillet to one vertical edge.
6. Open the extrusion's native Edit Feature dialog from the timeline, change 6 mm to 8 mm, and commit.
7. Click blank canvas, press Escape, move onto the large front face, let the pointer settle for 600 ms, and select it with a 180 ms mouse-button hold.
8. Capture without further input or API calls. Both captures show the gray face.

Capture intervals measured from return of the click command were 1.000–1.320 seconds and 3.320–3.628 seconds. These are capture start/completion intervals, not exact button-release latency or frame-rate measurements.

The read-only state probe ran only after those captures. Its top-level getters printed the state above, then Fusion's script wrapper reported `NameError: name 'run' is not defined` because the probe omitted the required entry point. The preserved response contains the state evidence and the error. It is not recorded as a successful end-to-end MCP test. The probe performed no design mutation.

## Native checks that passed in this session

- Fresh white canvas and transparent/white Browser panel; the previous opaque black Browser was absent.
- Visible origin workplanes and complete sketch toolbar.
- Grid off/on states matched their checkboxes in the corresponding captures. The filenames' `350ms` labels describe the requested delay before capture, not measured display latency.
- Dimensioned rectangle, solid 6 mm extrusion, 2 mm fillet preview/commit, and visible 8 mm thickness edit.
- Native feature dialogs rendered legibly.

The reviewer stopped after confirming the selection defect, as requested. Cloud save/reopen, local import/export, modal and menu behavior, navigation smoothness, mixed-monitor operation, and a reviewer-controlled cold relaunch were not completed on this final candidate. Earlier candidates' passes do not substitute for those checks.

## Evidence and handoff

Private evidence is under `~/.local/state/fusion360-for-omarchy-wine/review-installed-alpha-native/`:

- `initial.png`, `workplanes1.png`, `sketch-grid-initial.png`
- `grid-off350ms.png`, `grid-restored350ms.png`, `rectangle.png`
- `extruded6mm-idle3.png`, `fillet-preview2mm.png`, `edit6-before.png`
- `post-edit-selection1.png`, `post-edit-selection3.png`, `capture-timing.json`
- `selection-readonly.py`, `selection-readonly.json`, `result.json`

Exclusive GUI/API ownership was returned to the root agent with the unsaved 50 × 30 × 8 mm filleted validation plate intact. No personal design was opened or changed. No agent-dot-files were modified. Acceptance remains blocked; no further settings permutations were attempted by the reviewer.
