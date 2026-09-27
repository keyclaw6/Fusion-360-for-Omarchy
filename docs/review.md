# Independent review

**Historical review record.** The later corrected control passed and GE v3 was
subsequently installed. See [the retest and promotion](ge-normal-retest.md) and
[the new operational review](operational-review.md) for the current assessment.
The earlier observations and verdicts below are preserved as recorded.

**26 September 2026 — acceptance has not passed.** The latest ordinary cold
launch of the installed v2 candidate produced a persistent gray canvas, and a
newly committed native extrusion was not drawn. The reviewer preserved that
state and returned control for diagnosis. Earlier candidates passed substantial
modeling and file workflows but had other rendering defects, recorded below.
Those historical passes do not establish acceptance of the final installation.
The subsequent private candidate with Qt OpenGL drew the model correctly, but
the reviewer reproduced a missing selection highlight after feature editing.
That candidate is also rejected; no v3 configuration was deployed and no final
acceptance was granted.

## Observed evidence

- The initial independent test run passed all 30 tests. After the startup,
  file-path, runtime, browser, and desktop-registration fixes, the latest
  independent repeat passed all 87 tests before the Btrfs launch repair. The
  implementation agent reports 88 tests after that repair.
  These exercise wrapper
  boundaries and isolated installation/recovery fixtures; they do not establish
  Autodesk cloud access, real update recovery, or graphics performance.
- Read-only status identified Fusion 2705.1.25 in the new dedicated prefix,
  GE-Proton11-7, a matching live session attachment, and the
  `VirtualDeviceGLCore` preference. That preference is not confirmation of the
  renderer currently driving a modeling canvas.
- The clean-baseline startup capture rendered the welcome text and Sign In
  control. Subsequent exploratory modeling and viewport observations are
  recorded below; startup alone was not treated as acceptance.
- Registered local file opening is `Fusion360.exe "%1"`; registered Fusion URI
  opening is `NLauncher.exe "%1"` in the same current deployment.

## Findings sent to the implementation agents

1. Prefix maintenance originally checked for running processes without sharing
   its lock with launch. A launch after that check could overlap backup or
   recovery; simultaneous cold starts were also uncoordinated. The updated
   shared maintenance lock and exclusive startup lock close this race in the
   supported launcher. Independent review and the new concurrency tests pass.
2. Runtime validation originally accepted any installed Steam runtime launch
   client and did not check the current umu version. Because the runtime is
   shared, another application could change it after installation. The final
   preflight checks the installed umu executable's version and both the depot
   and platform rows in Steam's version record. Missing or changed versions
   fail closed; the reviewer verified the implementation and regression tests.
3. Local file arguments originally remained Unix paths when sent to the Windows
   executable. The updated code now maps them through the actual C: or Z: drive.
   The reviewer confirmed this installation's Z: mapping resolves to `/` and a
   path containing spaces is converted intact; boundary tests pass.
   Cold and already-running file opening still require application testing,
   including checking that another full Fusion instance is not created.
4. The implementation agent found that `xdg-mime` on this host ignored a quoted
   first executable token and selected an old callback handler. Desktop entries
   now start with `/usr/bin/python3` and pass the absolute helper as a quoted
   argument. The reviewer independently passed the real GIO argument-delivery
   test and the competing-handler install/removal regression. Registration also
   reads back the effective handler and rejects a mismatch.
5. The public `install-exe` and `configure-browser` CLI dispatches also needed to
   honor the maintenance lock. They now hold it exclusively through their
   operation, while internal installer calls retain their existing lock without
   nesting. Independent review and three added tests verified exclusion,
   operation lifetime, and browser configuration in a live matching session.

The browser helper's host loader now includes systemd's library directory and
uses the exposed public session bus from within the runtime. Tests verify that
this changes only the helper child's environment and retains normal host
behavior. The implementation agent separately verified the permanent
WineBrowser-to-Zen route with a benign Autodesk URL; the reviewer has not yet
performed an authenticated callback or cloud save/reopen operation. The
implementation agent subsequently completed sign-in and reported that a cold
restart retained the account session.

All concrete static/lifecycle findings raised in this review are resolved in
the reviewed source. The implementation agent also reports a real closed-prefix
backup/restore: registry hashes matched the snapshot, a later marker disappeared
from the restored prefix but remained in the preserved previous prefix, and
Wine's self/root drive links retained their intended targets. This is useful
recovery evidence; authenticated unsynced work has not yet been exercised.

## Exploratory hands-on review

The reviewer independently operated Fusion 2705.1.25 on the second experimental
Wine alpha candidate, using only the saved validation assembly and a new test
document. No compositor configuration, prefix configuration, or runtime files
were changed during this review.

- Created a dimensioned 60 × 40 mm sketch with a 10 mm circular hole using the
  native sketch tools. Extruded the profile 8 mm, added a 2 mm edge fillet, then
  edited the extrusion to 12 mm through the timeline. The solid and through hole
  rendered correctly. A read-only API check confirmed the dimensions and healthy
  extrude and fillet features.
- Preserved the new manual model in a 92,065-byte F3D archive at
  `prefix/drive_c/users/steamuser/AppData/Local/FusionOmarchyValidation/reviewer-interactive-20260926T124705Z/manual-plate.f3d`
  under the installation state directory. This was a local preservation export;
  the reviewer has not yet reopened that archive. The new document remained open
  when GUI control was returned to the implementation agent.
- Operated the saved 64-part validation assembly with real Shift + middle-button
  orbit, middle-button pan, and wheel zoom. Geometry remained visible without
  observed corruption through those actions. The Fusion process's AMD GPU
  graphics-engine counter increased by 182,583,914 ns during the inputs. This
  demonstrates GPU work during viewport navigation; it is not a display frame
  rate or input-latency measurement.
- Used native menus, sketch controls, feature dialogs, and timeline editing.
  Staged input after the field became active worked. Some rapid synthetic input
  batches missed an initial digit or did not commit an edit; these are not
  sufficient evidence that ordinary physical input fails.

Private screenshots and `reviewer-navigation-gpu.json` are retained in
`~/.local/state/fusion360-for-omarchy/`. The implementation agent separately
reported cloud save/reopen, F3D and STEP reimport checks, and Graphics Diagnostics
identifying the AMD Radeon 8060S with OpenGL Core 4.6. These are supporting
implementation observations, not substitutes for the independent final gate.

The native Save dialog's fully black backdrop was an implementation-reported
rendering blocker on the second candidate. It was subsequently fixed and passed
the independent installed-runtime check below.

Short delayed-paint observations also need a controlled repeat. A timeline icon
appeared after pointer movement, and an extrusion edit preview remained in a
visible-region capture about 1.2 seconds after committing the edit. A later
capture was correct, but a read-only API request occurred between captures, so
the reviewer has not established whether elapsed time or a further event caused
the repaint. These captures used the visible monitor region, not cached hidden
window capture. Persistent stale rendering is not proved. Repeat on the final
candidate with delayed captures and no intervening API requests.

## Installed OpenGL canvas review — rejected

The installed runner was verified as GE-Proton11-7 with overlay
`ge-proton11-7-omarchy-x11-v1`, module SHA-256
`6b5f680717f8e1db59039eeb50a953ac7703d6a7e88cd1e891c345e372020f1f`,
both reviewed alpha settings enabled, and `QSG_RHI_BACKEND=opengl`.

The first normal desktop start failed because the runtime check compared Btrfs
`stat()` device identity with `/proc/maps` device identity. These differ for the
same file on this machine. The implementation agent changed the check to derive
the expected identity from a private, non-executing mapping. Independent source
review confirmed that device/inode and deleted-file checks remain in place. A
normal desktop start after deployment succeeded: runtime status reported a
verified overlay, matching attachment, no conflict, and a live Fusion process.
The signed-in account session returned without reauthentication.

The reviewer then completed these native GUI checks:

- Created a new 70 × 45 mm rectangle with a 12 mm circular hole; extruded it 9 mm,
  applied a 3 mm edge fillet, and edited the extrusion through its timeline
  feature to 11 mm. The solid, hole, and fillet rendered correctly.
- Captured all three timeline features after idle time, without an intervening
  pointer action or API call. The earlier missing-timeline-icon symptom did not
  reproduce in this sequence. The feature-edit preview also cleared after
  committing the edit.
- Opened the native Save dialog. Its backdrop was correctly translucent gray,
  and project/folder selection remained usable.
- Passed an exact host → Fusion → host clipboard round trip, replacing the host
  clipboard with a sentinel before copying the native field back.
- Saved **Omarchy reviewer final 2026-09-26** under **Default Project / Omarchy
  validation 2026-09-26**. A read-only check confirmed saved=true,
  modified=false, cloud_complete=true, and cloud version 1.

**Blocking failure:** a normal Ctrl+W closed the saved document and produced an
empty Untitled document. The title, Browser, and timeline updated, but the canvas
retained the closed plate. Opening the native cloud Open dialog displayed it
over the stale plate. Cancelling that dialog and waiting five seconds without
input or API calls did not clear the geometry. A subsequent read-only check
confirmed one active Untitled document with zero bodies and zero occurrences.
Real pointer movement followed by another two-second wait also failed to clear
the stale canvas. A gray strip persisted at the bottom after the dialog closed.

The reviewer returned exclusive GUI control in that exact state for diagnosis.
The manual model is safely saved in the cloud. Evidence is retained privately in
`~/.local/state/fusion360-for-omarchy/reviewer-final/`, particularly
`closed-manual.png`, `closed-idle-no-api.png`, `closed-after-inspect.png`,
`closed-after-motion.png`, and `milestones.json`.

## Installed DirectX 11 canvas review — in progress

The reviewer independently launched the ordinary `Fusion 360 for Omarchy`
desktop entry from `/tmp`, with the stable installed runner and the same
`6b5f6807…2020f1f` overlay and three required environment settings. The configured
canvas preference was `VirtualDeviceDx11`. Native Graphics Diagnostics confirmed
**AMD Radeon 8060S Graphics (RADV STRIX HALO), DirectX 11.0**, with software
rendering unchecked. Driver date/version appear as Unknown in this compatibility
layer. An independent test run passed all 96 tests before the subsequent wrapper
cleanup/file-URI changes. The reviewer then independently passed all 102 tests
after those changes, including local file URI normalization and per-signal
shutdown activity rechecks. Their installed behavior still awaits the final
integration checks.

These checks have passed through the native application UI:

- The signed-in account returned after a normal cold desktop launch without
  reauthentication. The reviewer opened the saved **Omarchy reviewer final
  2026-09-26** through the native cloud Open dialog. Its one solid, three timeline
  features, saved parameters, healthy extrude/fillet features, and completed
  cloud version were confirmed with a read-only API query.
- The prior blocking sequence was repeated: native timeline extrusion edit
  from 11 to 13 mm, Ctrl+S, then Ctrl+W. After five seconds of idle time with no
  intervening input or API request, the empty document's canvas was correctly
  clear. A later read-only query confirmed zero bodies and occurrences.
- Created another model entirely with native sketch and feature tools: a
  **50 × 30 mm plate, Ø8 mm through hole, 6 mm extrusion, and 2 mm edge fillet**.
  Saved **Omarchy reviewer DirectX11 2026-09-26** in **Default Project / Omarchy
  validation 2026-09-26**. Read-only verification found one solid, healthy extrude
  and fillet features, three timeline entries, exact parameters, volume
  **8.672654884863064 cm³**, saved=true, modified=false, and completed cloud
  version 1.
- The native Save dialog displayed its translucent gray backdrop and usable
  project/folder controls. A second exact host → Fusion → host clipboard round
  trip passed, using a replaced host clipboard sentinel before copying back.
- Exported that model using native File → Export and the native file chooser.
  Reopened the resulting **F3D and STEP** files through Ctrl+O → Open from my
  computer. The F3D retained all three timeline features and dimensions with
  identical solid volume. The STEP had one healthy base feature and a volume of
  **8.672654884863062 cm³**, agreeing within floating-point precision. Temporary
  imported copies were closed; the exported files and cloud original remain.
- Switched between the manual model and the saved 64-part validation assembly
  three times in each direction. Delayed visible-region captures correctly
  showed the three-feature and approximately 69-feature timelines without an
  additional pointer event or API request.
- Operated the 64-part assembly with real Shift+middle-button orbit,
  middle-button pan, and wheel zoom. Geometry and holes remained visible without
  observed corruption. The matching GPU graphics-engine counter advanced by
  **350,923,827 ns** during the actions. A 4.7-second screen recording contains
  the navigation sequence. Neither the counter nor the recording's configured
  30 fps is a measured application frame rate.
- Confirmed face selection and blue highlighting. Rapid synthetic pointer
  warp/click batches produced ambiguous intermediate captures; waiting 0.5 s
  between pointer motion and clicking produced the expected hover and selected
  fill in captures without intervening API calls.
- Moved the Fusion-only workspace from the landscape **3840 × 2160, 1.5×**
  monitor to the portrait **1440 × 3440, 1×** monitor and back. Canvas, Browser,
  menus, timeline, and ViewCube remained legible and operable. Clicking the
  ViewCube's Top face changed the assembly orientation correctly. Floated and
  resized the main window to 1550 × 1050 logical pixels, then restored its tiled
  geometry. No persistent display configuration was changed.
- Opened Save on a fresh blank document, pressed Escape, then Ctrl+W without a
  canvas click. The blank tab closed and the two saved documents remained. The
  earlier Save-cancel keyboard-focus concern did not reproduce.
- Reopened the manual sketch and inspected the grid, red/green origin axes,
  dimension labels, constraints, shaded profile, Ø8 mm circle, Sketch Palette,
  ViewCube, and navigation controls. The grid itself is present and renders
  clearly; the toggle timing observation below remains unresolved.

Private evidence is in
`~/.local/state/fusion360-for-omarchy/reviewer-final-dx11/`, including
`edit-save-close-idle5.png`, `graphics-diagnostics.txt`,
`native-sketch-grid-axes-dimensions.png`, `assembly-navigation.mp4`,
`navigation-gpu.json`, the tab-switch screenshots, and both files in `exports/`.

### Observations returned for diagnosis

1. **File menu Escape:** twice, a normally opened File menu remained open after
   Escape and three seconds of idle time. A canvas click dismissed it. The
   second reproduction used the restored main monitor without a window or
   monitor transition. A menu left open while the main window moves remains at
   its old position until dismissed. Evidence:
   `file-menu-before-escape.png`, `file-menu-after-escape.png`, and
   `floating-after-escape.png`.
2. **Grid toggle display timing:** after clicking Sketch Grid off, the checkbox
   was unchecked but the canvas grid remained in a capture after 1.5 seconds.
   After clicking it back on, the checkbox was checked while the grid was absent
   in the next delayed capture. These clicks included a 0.5-second pointer
   settling delay. This is an observed mismatch, not evidence that grid drawing
   is unsupported. Evidence: `sketch-grid-disabled.png` and
   `sketch-grid-restored.png`.
3. **Create Sketch workplanes:** the fresh document remained blank for five
   seconds after Create Sketch; moving the pointer into the canvas displayed
   the orange workplanes and axes immediately. This might be command-hover
   behavior, so it needs comparison rather than being declared an independent
   rendering defect. Evidence: `workplanes-idle5-no-input.png` and
   `workplanes-after-motion.png`.

The reviewer researched native menu behavior using Agent Reach/Exa, original
Autodesk pages, and a second search index. Autodesk QA engineer Phil Eichmiller
described Escape as the baseline dropdown-menu action while discussing native
Windows/macOS input in [December 2016](https://forums.autodesk.com/t5/fusion-design-validate-document/3d-connexion-quot-numpad-quot-key-problems/m-p/6743751#M247648).
Autodesk QA's [April 2020 macOS response](https://forums.autodesk.com/t5/fusion-support-forum/macos-esc-button/m-p/9433221#M118911)
also treats Escape dismissing menus as expected. Current [basic-operation
documentation](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GS-BASIC-OPERATIONS.htm)
explicitly documents Escape dismissal for the **Marking menu**, which is a
different UI. These sources support investigating the File-menu behavior as a
compatibility defect; they do not prove how the exact 2705.1.25 custom File menu
behaves on a native installation. No current File-menu-specific native
demonstration was found, and native parity must not be claimed from this search.

The reviewer also independently inspected the September 2026 official video
frames at 48, 78, and 283 seconds and Autodesk's constrained-sketch example from
[the reference comparison](visual-comparison.md). Selected-face shading, thin
outlined edges, Browser transparency, and the visible interface structure agree
with the local captures. That static comparison does not resolve the observed
grid state mismatch or establish input latency.

The reviewer stopped input when the active application changed to an unrelated
browser and returned exclusive GUI/API control to the implementation agent.
Fusion remained in plane selection in a fresh blank document; no geometry was
created there. The saved manual model may have a view-setting modification from
entering the sketch and toggling its grid; its geometry was unchanged.

## Private present-wait v2 preliminary review

This bounded review used the experimental `GE-Proton11-7-present-wait` runner,
the existing `6b5f6807…2020f1f` X11 module, DirectX 11 canvas,
`QSG_RHI_BACKEND=d3d11`, and `WINE_X11_VULKAN_PRESENT_WAIT=1`. It was not a
review of the final installed desktop launcher. The implementation agent
requested an early checkpoint before a cold performance comparison.

- Four native Sketch Grid checkbox changes correctly hid, showed, hid, and
  restored the grid in captures 350 ms after click completion. There was no
  intervening API request or additional pointer movement. The pointer was
  allowed to settle for 0.5 seconds before each click. Red/green axes, the
  workplane, ViewCube, palette, and navigation controls remained visible.
- Create Sketch in a fresh document displayed its orange workplanes in both
  the one-second and five-second captures without further input or API calls.
  This improves on the previous installed candidate's observed behavior.
- An initial assembly face selection stayed gray in delayed captures and
  became blue after a read-only selection query. That trial followed the
  implementation agent's explicit Qt File-widget focus experiment. After
  restoring ordinary main-window interaction, clearing selection, and repeating
  the same settled click, the face was correctly blue after three seconds
  without an API request. The first observation remains recorded, but did not
  reproduce in the normal-focus repeat.
- The empty test sketch was finished and discarded through the native close
  confirmation. The imported 64-part scratch assembly then returned correctly.
  No cloud design was modified in this preliminary review.

Evidence and timing records are in
`~/.local/state/fusion360-for-omarchy/reviewer-preliminary-v2/`, particularly
`grid-off-350ms.png`, `grid-on-350ms.png`, `grid-off-repeat-350ms.png`,
`grid-on-restored-350ms.png`, `grid-toggle-timestamps.json`,
`create-sketch-idle1.png`, `create-sketch-idle5.png`,
`selection-repeat-idle3.png`, and `selection-repeat-timestamps.json`.

The authentication reviewer independently checked the implementation agent's
File-menu trace: Escape reached the exact focused File widget, yet that menu
remained mapped. Related Fusion QML menus explicitly request outside-click
dismissal without requesting Escape dismissal; the File widget is compiled
code. This evidence does not establish a Wine keyboard-delivery defect or the
native intent of this exact custom File menu. A working canvas-click dismissal
is available, so a global Escape workaround is not justified by the evidence.

Exclusive GUI/API control was returned to the implementation agent with the
blank Untitled and imported assembly tabs open. No final acceptance is implied;
the final installed candidate must still pass the remaining workflow and
restart checks below.

## Installed v2 cold-launch review — rejected checkpoint

The reviewer independently started the ordinary desktop entry with detached
`gtk-launch fusion360-for-omarchy` from `/tmp`, after status confirmed no running
Fusion or identity processes. The installed pair was verified by status:

- X11 module SHA-256:
  `6b5f680717f8e1db59039eeb50a953ac7703d6a7e88cd1e891c345e372020f1f`.
- Win32u module SHA-256:
  `201ef0e0f4d48dfc093a16ffdd221c0ef37427e35ec59238756e0dc54c134d38`.
- Aggregate overlay SHA-256:
  `0625fc013bf89ec1730a1460e73a1d418eda4c6a3b077ad1c755463b189446b0`.
- Fusion 2705.1.25, `VirtualDeviceDx11`, runtime ready, overlay verified, no
  session conflict or reported preflight error.

The signed-in profile returned without a sign-in or recovery prompt. The saved
Codex MCP registration was independently checked, without sending a Fusion
request: its enabled endpoint is `http://127.0.0.1:27182/mcp` with the expected
timeouts. No MCP request was made during this launch before the failure.

Fresh Create Sketch workplanes appeared on the first action. Four native grid
toggles correctly changed the grid in captures 350 ms after click completion,
without an extra pointer event or API request. The reviewer then drew a native
30 × 50 mm rectangle and an Ø8 mm circle, finished the sketch, selected the
outer profile in Extrude, entered 6 mm, and committed with Enter.

**Blocking observation:** the canvas had remained flat gray since startup, with
the sketch and selected profile visible against that gray. After extrusion was
committed, no solid appeared: delayed captures at one and five seconds show an
entirely gray canvas, while the Browser contains a Bodies folder and the
timeline contains the extrusion entry. The model's API state was deliberately
not queried before handoff, to preserve the rendering failure without a
possible diagnostic wakeup. This is an observed rendering failure; its cause
was not yet established by the reviewer.

Exclusive GUI/API control was returned to the implementation agent in that
exact state, main window `0x562707d94fd0`, Fusion PID 3875351. The only document
is the reviewer's unsaved validation model; no cloud design was changed.
Private evidence is in
`~/.local/state/fusion360-for-omarchy/reviewer-installed-v2/`, including
`startup-idle5.png`, `fresh-sketch-grid.png`, the four grid-toggle captures,
`extrude-preview.png`, `extruded-body-idle5.png`, and `checkpoint.json`.

## Private Qt OpenGL plus present-wait retest — rejected

This test retained the v2 module pair and native DirectX 11 canvas, changed Qt's
backend to `QSG_RHI_BACKEND=opengl`, and used `WINEDEBUG=-all` without diagnostic
logging or DXVK overrides. It ran in the private candidate runner, not through
the final production launcher. Fusion PID 120246 and main window
`0x562706d05c40` remained unchanged throughout the recorded review.

The reviewer successfully created another model entirely through native tools:
a 30 × 50 mm rectangle, Ø8 mm through hole, 6 mm extrusion, and one 2 mm edge
fillet. The previously failing extrusion now displayed correctly on the white
canvas in one-second and five-second idle captures. Fresh workplanes displayed
at 350 ms and one second. Four grid toggles matched their checkboxes at 350 ms
and one second without intervening API requests. The visible toolbar, Browser,
Sketch Palette, and ViewCube rendered completely in these captures.

The reviewer observed a gray face highlight after a settled selection click
following extrusion and again following filleting. Input was paused for the
implementation agent's passive comparison. On later resumption after a desktop
lock/unlock, the implementation agent reported blue selection and passing
ordinary selection repeats. The reviewer did not treat that later result as
proof that the post-command case was resolved.

The reviewer then saved the model through the native cloud Save dialog as
**Omarchy reviewer QtGL present 2026-09-26**, in **Default Project / Omarchy
validation 2026-09-26**. The translucent Save backdrop and folder chooser worked,
and the dialog closed to the named document with a saved checkmark. The face
was correctly blue before the next feature edit. No Fusion API request had
been made by the reviewer.

**Repeatable remaining failure:** the reviewer opened the extrusion from the
timeline, changed its selected distance from 6 to 8 mm, and committed with
Enter. The solid visibly thickened, preserving the hole and fillet. After
0.8 seconds, the reviewer clicked blank canvas with a 0.6-second pointer settle,
pressed Escape, waited 0.5 seconds, then selected the front face with another
0.6-second pointer settle. Mouse clicks used `ydotool click -D 180 0xC0`, whose
documented delay applies between down/up events. The face remained gray in
captures at 0.3, one, and three seconds. No extra input or API request occurred
between these captures. The main window retained focus; the feature palette
was closed and all three timeline entries remained visible.

The reviewer returned control in that state for passive producer comparison
and preservation. The implementation agent then captured both the main window
and actual canvas producer `0x220040f`; both remained gray. Its first subsequent
read-only MCP query reported `SelectCommand`, one selected `BRepFace`, three
timeline entries, and an 8.0 mm extrusion. This confirms a selected model entity
without its expected visible highlight, rather than a missed click.

The 6 mm model was cloud-saved; the latest 8 mm edit was still unsaved at
handoff. The implementation agent took responsibility for saving/exporting
that edit before closing. The candidate is **rejected**. The remaining
close/reopen, assembly navigation, monitor, and normal launcher checks were not
completed on this candidate. No v3 configuration was deployed, and no final
acceptance was granted. The implementation agent will pursue the separately
authorized second approach in its own repository.

The implementation suite remains at **128 checks**: 76 launcher, 40 installer,
and 12 Hyprland integration checks. These are historical software-boundary
results and do not override this native application failure. Evidence is under
`~/.local/state/fusion360-for-omarchy/reviewer-v2-qtgl/`, particularly
`native-extruded-body-idle5.png`, `saved-native-model.png`,
`native-extrude-edit-dialog.png`, and `post-edit-selection-{300ms,1s,3s}.png`.

## Required hands-on decision

Before acceptance of either route, resolve the reproducible display failures,
compare the installed UI against current official Autodesk reference images,
verify the final wrapper deployment with a normal quit/cold restart and retained
authentication, and exercise the installed desktop Open With route for the test
F3D. The reviewer will also reopen the newly saved DirectX 11 model from the cloud
and record the final decision. A successful launcher, API fixture, or static
test suite cannot satisfy this gate by itself.
