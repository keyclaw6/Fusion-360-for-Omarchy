# Independent operational review — installed GE v3

Review dates: 26–27 September 2026 (Europe/Copenhagen). Reviewer:
`operational_review`. Private evidence timestamps use UTC.

**Accepted for the tested Design, rendering, file, and desktop workflows on this
machine.** The installed GE v3 candidate with the final portable monitor and
palette-focus hooks passed independent hands-on review. The two substantive
desktop defects found during review were corrected and retested. This is a
bounded operational acceptance, not a claim that every Fusion workspace,
arbitrarily large model, or Windows/macOS behavior has been exhaustively matched.
The optional Omarchy plugin has a separate acceptance gate.

## Candidate and method

I operated the ordinary installed GE-Proton 11-7 v3 candidate, Fusion 2705.1.25,
with its DirectX 11/DXVK canvas and Qt OpenGL interface. The installed overlay
identity is `c47f8b1d22dd6f0152b54166cbb57707af5992200281c0252bef82829b15731d`.
Normal selection was already configured and read back as enum 0. No renderer,
preference, runtime, or persistent desktop configuration was changed by this
review. The root supplied separate physical Radeon/RADV process evidence from
this same PID 1111270, including a nonzero graphics-engine counter increment.

Final desktop integration under review is repo commit `3437b16`, installed
block SHA256
`9239f81b3ad92a9ca2460f5f85d71ff4fd934fd6ec1ff4fda37c428b10341ae2`,
helper SHA256
`5b8db34d9576093843470ca135a6813771dfcc8789ae40e8fbf5189135b5f045`.
The root removed its temporary diagnostic callbacks before this independent
review. My final focused review exercised the supported installed hooks.

The root handed me exclusive shared desktop and MCP control. I used actual
mouse/keyboard input for sketching, modeling, feature edits, cloud and local file
workflows, menus, and navigation. Screenshots were captured before subsequent
read-only API queries when checking selected or newly regenerated geometry.
The API supplied independent dimensions and face identity, and imported the
existing representative assembly fixture for navigation. No personal design
was edited.

## Passed workflows

- A fresh sketch displayed origin workplanes, continuous grid and colored axes.
  Grid off/on matched the checkbox state. A natively entered, constrained
  50 × 30 mm rectangle displayed dimensions, constraint markers, and profile fill.
- Native 6 mm extrusion, 2 mm edge fillet, and timeline edit to 8 mm all rendered
  correctly. The committed part had one body and three timeline features.
- Fresh native selections were blue before and after editing, with the pointer
  away during capture. After regeneration, the selected visible +X face was
  identified by its 1440 mm² area, normal `[1,0,0]`, centroid
  `[0.8,2.6,1.5]` cm, camera position, and projected screen position. The earlier
  face was at X = 0.6 cm; this verifies selection of the regenerated front face,
  not merely the presence of some selected BRepFace.
- Native cloud Save created **Omarchy final GE review 2026-09-26** in
  **Default Project / Omarchy validation 2026-09-26**. Its data file reported
  version 1 and complete. I closed the document, reopened it through the Data
  Panel, and verified the same three features and 8 mm thickness.
- Native File → Export produced an 86,997-byte F3D; after closing the document,
  native Open → Open from my computer reopened that file with the same body,
  bounding box and features. The native chooser and export completion
  notification were visible and usable. Clipboard text worked in the cloud
  Save name and Windows file paths. One malformed initial file path was caused
  by `ydotool type` interpreting backslash escapes; clipboard entry resolved
  that test-input error.
- The single part and a 64-occurrence mounting-plate fixture responded to
  repeated native orbit, pan, wheel zoom and selection. Multiple captures
  during three assembly orbit sequences showed changing geometry, preserved
  holes/edges, and usable controls. I observed no persistent stale geometry or
  blocked input on DP-1 during these operations. This is a bounded interaction
  review, not a measured FPS, frame-pacing, or native-platform latency comparison.
- Escape cancelled the native Open modal, Create Version modal, and an empty
  Fillet command. File commands remained usable.

The local round-trip file is private:
`~/.local/state/fusion360-for-omarchy/operational-review-ge-v3/exports/native-final-8mm.f3d`.
Local import opens an unsaved copy, which is expected; that copy was closed
without overwriting the exported file or cloud document.

## File-menu observation

The File menu remained mapped after Escape, including with a settled pointer,
pointer inside or outside the menu, repeated Escape, a Down-arrow attempt, and
explicit popup focus. Clicking outside immediately dismissed it, and its actual
commands worked. Alt+F did not open it; no documented Alt+F contract was assumed.
Other tested modals and feature commands cancelled with Escape.

This is recorded as a bounded usability/parity uncertainty. I have no
exact-build Windows/macOS reference establishing File-menu Escape behavior and
did not treat this observation alone as a rendering failure or blocked workflow.

Alt+F4 exited the app in an earlier cold-start check, but did not exit the
floating app after Browser interaction during the final focus review, including
one canvas-click retry. Omarchy's documented Super+W close shortcut exited
cleanly in about five seconds. The inconsistent Alt+F4 observation is retained;
it does not prevent the ordinary Omarchy close/relaunch workflow.

## Original mixed-monitor failure — repaired and independently retested

DP-1 uses scale 1.5 at logical origin `[0,1000]`; the portrait DP-3 uses scale 1.0
at `[2560,0]`. Moving the maximized main window with the ordinary Hyprland
window-move operation from workspace 1 to workspace 5 moved the main UI and
rendered model to DP-3, while the Browser and Comments utilities remained on
workspace 1 at X = -949, outside the visible desktop. Waiting did not restore
the Browser. Maximizing/restoring on DP-3 recovered Comments but not Browser.
Moving back to workspace 1 recovered Browser, while Comments could remain on
the other workspace.

For an independent input control, I returned to DP-1, unmaximized, floated and
resized the main window to 1100 × 900, where Browser was visible. I then used
the normal Omarchy Super + left-button drag from `[1902,1733]` to `[3270,1733]`.
The main window moved to DP-3/workspace 5 at `[2720,1283]`, size 1200 × 900.
Comments was visible, but Browser was again absent. This therefore also occurs
with the desktop's normal mouse gesture, not only a direct workspace command.

Missing Browser is a substantive issue for work on the second monitor. The
main canvas itself remained responsive and correctly rendered. This evidence
supports investigating owned-window positioning/workspace behavior; it does
not identify the renderer as the cause or reject the overall GE approach.
The earlier historical monitor pass used transfer of an entire Fusion-only
workspace. This review moved the individual main window. The two tests exercise
different desktop paths; this finding does not invalidate that narrower earlier
workspace-transfer observation.

The root subsequently deployed the scoped workspace-event repair through the
supported installer. I tested the installed integration after a full application
and runtime shutdown, without the root's temporary experiment callbacks or
window overrides. Installed hook identity for this retest:

- block SHA256:
  `f67ad6bc9e2cf463d2c576142679a984eb5b4b2838915df6b3001f993c45b778`
- helper SHA256:
  `6728f89d3a5dad7f5bb408ec4be2efa37829d42a4892417cf89b1d0cd0b9254c`

Individual maximized-window transfer from DP-1/workspace 1 to DP-3/workspace 5
and back passed. Browser and Comments followed, with correct sizes and usable
input. On DP-3 I expanded Bodies and selected Body1 through the native Browser;
the expected solid became blue. The physical Super + left-button drag then
passed from `[1902,1733]` to `[3270,1733]`, followed by a return drag from
`[3320,1733]` to `[1850,1733]`. Browser and Comments remained visible on each
destination, and native Browser selection also worked after the physical drag.
These repeat the two formerly failing movement paths.

## Two ordinary cold starts and persistent saved data

Both launches used the real Omarchy Apps menu, selecting the production
**Fusion 360 for Omarchy** desktop entry. This exercises the installed entry
without relying on a shell tool's detached-child lifetime. The runner status
identified the same GE v3 overlay and Fusion 2705.1.25. The freshly created main
window's initial title was `Autodesk Fusion ` in both instances.

- Cold start 1 created Fusion PID 1648233. Cached authentication worked without
  interactive login. A fresh sketch displayed workplanes and a grid; grid off/on
  worked. Native cloud Open reopened the saved review part as version 1,
  complete and unmodified. A native timeline edit from 8 to 10 mm rendered
  correctly. The visible blue face, captured before the API check, had normal
  `[1,0,0]`, area 1440 mm², and centroid `[1.0,2.6,1.5]` cm, confirming the
  regenerated +X face in Normal selection mode.
- I restored 8 mm through the native feature dialog and used Ctrl+S. The cloud
  file became version 2, complete and unmodified. Normal Alt+F4 exited Fusion;
  the verified-prefix `stop-idle-runtime` command succeeded, and launcher status
  showed no Fusion or Identity process before the next launch.
- Cold start 2 created Fusion PID 1737106. The first main window appeared about
  23 seconds after the menu activation; that measures initial window appearance,
  not ready-to-model latency. Cached authentication again worked. Native cloud
  Open reopened version 2 with the same 8 mm extrusion, 2 mm fillet, one body,
  three features and bounding box `[0,0,0]` to `[0.8,5,3]` cm. Native selection
  again displayed the correct +X face in blue before the probe: area 1440 mm²,
  centroid `[0.8,2.6,1.5]` cm, normal `[1,0,0]`, Normal style enum 0.

## Original focus/stacking defect — repaired and independently retested

I used a temporary neutral Foot window to cover Fusion and test switching back
to it, without opening personal content. Fusion palettes did not remain visible
above the covering maximized Foot window. Ordinary Alt+Tab also reached the
existing Autodesk sign-in browser window and then the exact Fusion main.

On returning to floating Fusion over the maximized browser, the main canvas was
visible and responsive, but Browser and Comments were absent. Their workspace,
monitor and geometry remained correct. Hyprland reported the main as visible
with `allowedOverFullscreen=true`, while the palettes were
`visible=false`, `acceptsInput=false`, `allowedOverFullscreen=false`. Waiting
and a native canvas click did not restore them. Maximizing the exact Fusion
main immediately restored them. Further cycling also demonstrated a separate
palette focus target over the browser; returning to the main could restore the
complete app.

The objection is the missing functional Browser, not the generic behavior of a
floating window remaining above a tiled/maximized window, and not the mere
number of Alt+Tab targets. This review did not establish a native app with an
equivalent owned-palette arrangement as a baseline. Root subsequently matched
the other window's fullscreen state and reproduced generic maximize/restore
focus loss with native Foot as well as Fusion. That separate compositor
behavior is not a Fusion-specific failure. The missing-palette eligibility
defect remained substantive and was corrected rather than accepted with a
maximize workaround.

After cold start 2, I reproduced a useful final state without another application
switch: exact-main focus followed by Escape to clear the selected face left
Browser invisible even though the main was maximized; Comments remained visible.
The saved model was unaffected. This state is preserved for diagnosis in
`installed-monitor-retest/cold2-handoff.png` and `.json`.

### Final installed-hook review

After the root deployed the final hook, I independently repeated the failing
focus path using a temporary neutral native Foot window and ordinary Alt+Tab.
Four returns to the exact Fusion main restored the main, Browser and Comments
together, with usable input. Native screenshots of the covering maximized Foot
window showed no stray Fusion palettes. The app returned complete without a
manual palette raise, maximize recovery, API redraw or runtime change.

Browser collapse/expand and Body1 selection worked. Its native context menu
opened Rename; actual typed text appeared in the inline editor and Escape
restored Body1. One immediate automated typing attempt left the original name
unchanged. A controlled repeat after the editor settled accepted typing without
an extra click, and an explicit field-click control also accepted text. I did
not mistake the first input-timing attempt for a permanently unusable editor.
The saved cloud document remained version 2 and unmodified.

The final hook also passed a mixed-monitor regression: native Super+Shift+5
moved the main to DP-3, native Browser collapse/expand/selection worked there,
and a real Super + left-button drag returned the complete app to DP-1. Both
palettes followed correctly across scale 1.0 and 1.5.

I then closed Fusion with Super+W, successfully stopped its verified idle
runtime, and verified empty Fusion/Identity PID lists. A third genuine cold
launch through the ordinary Apps menu created PID 2035753, with the expected
fresh initial title. The first main window appeared about 23 seconds after
activation and the Untitled UI was captured about 39 seconds after activation.
These are coarse startup observations, not an FPS or native-platform benchmark.
Authentication persisted and native cloud Open reopened the saved review v2.
The settled model rendered normally; Browser expansion/selection and native
face selection worked. Exact-main focus followed by Escape now cleared the
selection while leaving both palettes visible, repeating the final previously
failing sequence on freshly created windows. No persistent black canvas was
observed during these settled interactions.

This focused rerun resolves the two substantive findings. Earlier completed
modeling, local/cloud round-trip and representative-assembly checks remain the
basis for those unchanged parts of the application acceptance; I did not claim
to rerun the entire modeling suite after a desktop event-hook change.

## Evidence and handoff

Private evidence is under
`~/.local/state/fusion360-for-omarchy/operational-review-ge-v3/`.

Key files include:

- `fresh-workplanes.png`, `fresh-sketch-grid.png`, `grid-off.png`, `grid-on.png`,
  `native-rectangle-50x30.png`, `native-extruded-6mm.png`
- `selected-before-edit.png`/`.json` and
  `selected-after-native-edit.png`, `selected-after-edit.json`
- `cloud-saved-state.json`, `cloud-reopened-state.json`,
  `cloud-reopened-panel-closed.png`, `local-reopened-state.json`
- `assembly-orbit-*.png`, `assembly-navigation-timing.json`,
  `assembly-panned.png`, `assembly-selected-confirmed.png`, `assembly-state.json`
- `file-menu-escape-*.png`, `file-menu-click-outside.png`,
  `open-modal-after-escape.png`, `empty-fillet-after-escape.png`
- `mixed-monitor-dp3-settled.png`, `dp3-remaximize.png`,
  `mixed-monitor-back-dp1.png`, `physical-drag-main-browser-missing.png`,
  `mixed-monitor-actions.json`, `handoff-clients.json`

The subsequent installed-integration evidence is in
`installed-monitor-retest/`, notably:

- `menu-cold1.png`, `cold1-first-window.json`, `cold1-authenticated-blank.png`,
  `cold1-fresh-grid.png`, `cold1-grid-off.png`, `cold1-grid-on.png`
- `cold1-native-selected-after-edit.png`, `cold1-postedit-selection.json`,
  `cold1-resaved-state.json`
- `installed-max-dp3.png`, `installed-dp3-browser-expanded.png`,
  `installed-dp3-browser-selected.png`, `installed-max-back-dp1.png`
- `installed-physical-drag-dp3.png`/`.json`,
  `installed-drag-dp3-browser-selection.png`,
  `installed-physical-drag-back-dp1.png`/`.json`
- `focus-other-app-covering.png`, `focus-return-settled.png`/`.json`,
  `focus-return-after-canvas-click.png`, `focus-return-maximized.png`,
  `focus-main-after-palettes.png`/`.json`
- `before-cold2-status.json`, `menu-cold2.png`, `cold2-first-window.json`,
  `cold2-authenticated.png`, `cold2-reopened-v2.png`,
  `cold2-reopened-state.json`, `cold2-native-selection.png`,
  `cold2-selected-face.json`, `cold2-handoff.png`/`.json`

Final portable-focus evidence is in `installed-focus-retest/`, including:

- `installed-settled-before-focus.png`, `neutral-covering-fusion.png`,
  `alt-tab-return-1.png` through `alt-tab-return-4.png` and their geometry/focus
  JSON records, `neutral-covering-cycle-4.png`
- `exact-main-focus-escape-regression.png`, `browser-context-menu.png`,
  `browser-keyboard-after-field-click.png`,
  `browser-rename-settled-typing.png`, `browser-settled-rename-cancelled.png`
- `monitor-dp3-after-focus-fix.png`/`.json`, `monitor-dp3-browser-input.png`,
  `monitor-physical-drag-back-dp1.png`, `monitor-roundtrip.json`
- `before-cold-document.json`, `before-cold-status.json`,
  `menu-cold-final.png`, `cold-final-launch.json`,
  `cold-final-reopened-v2.png`, `cold-final-browser-input.png`,
  `cold-final-face-selection.png`, `cold-final-main-focus-escape.png`,
  `cold-final-document.json`, `final-handoff.json`

At final handoff, Fusion PID 2035753 is maximized on DP-1/workspace 1, with the
saved, unmodified and fully synchronized version 2 review document. Browser,
Comments and the model are visible. No modal or unfinished command is active;
selection is cleared. The temporary Foot control has exited. Zen is restored
to fullscreen 0; its remaining position follows the existing scrolling layout
behind maximized Fusion. No browser content was changed. The exclusive GUI/MCP
lease has been returned to the root.

**Application verdict: accept within the tested scope above.** The File-menu
Escape and inconsistent Alt+F4 shortcut observations are disclosed limitations,
with working ordinary dismissal/close paths. Suspend/resume, the optional
plugin, CAM, simulation, every other Fusion workspace, heavy-assembly performance,
quantitative FPS/frame pacing, and exact Windows/macOS parity were not tested or
claimed. Those limits do not erase the demonstrated native Design, rendering,
file and desktop workflows, nor should they be presented as a guarantee of
universal flawlessness.
