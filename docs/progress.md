# Implementation progress

## User constraints

- Standalone repository named Fusion 360 for Omarchy; leave agent-dot-files untouched.
- Operate the real Omarchy desktop and pursue responsive, correctly rendered Fusion.
- Authentication worker and independent hands-on reviewer are required.
- Local Omarchy plugin follows functional acceptance. No publication has been requested.

## Baseline (2026-09-26)

- Omarchy 4.0.4-1; Hyprland 0.56.2; Linux 7.2.3-arch1-3.
- AMD Ryzen AI MAX+ 395, Radeon 8060S, amdgpu, Mesa/RADV 26.2.2.
- Native Steam 1.0.0.87-3 installed; GE-Proton11-5-x86_64 exists.
- Host Vulkan enumerates physical Radeon 8060S and CPU llvmpipe.
- Two monitors with mixed scaling (1.5 and 1); normal desktop is the test target.
- About 149 GiB available at baseline. No Fusion process/window was running.
- Existing `~/launch-fusion.sh` forces llvmpipe/software rendering and invokes Proton directly.
- Existing `fusion360-linux` launcher uses Distrobox plus a Wine virtual desktop.
  Its `--auth` path explicitly rejects callbacks. These are retained intact for now.
- GE-Proton11-7 release and pinned Fusion180 commit verified by upstream worker.

## Current work

**Latest state, 27 September: v3 is installed and independently accepted for the
tested Design, modeling, rendering, file and desktop scope.** The corrected GE control disproved the earlier broad
selection rejection. The subsequent hands-on review passed native modeling,
grid/workplanes, identified post-edit selection, cloud and local round trips,
64-occurrence assembly navigation, two authenticated cold launches, and the
repaired mixed-monitor movement paths. See
[operational-review.md](operational-review.md).

Two scoped Hyprland integration corrections keep palettes with the main window:
one follows individual window moves across mixed-scale monitors; the other
restores missing fullscreen eligibility after returning to Fusion. The first
passed independent review. The second passed 37 focused implementation checks,
was installed with unchanged runtime identity, and passed native context-menu
and keyboard smoke checks. The independent reviewer subsequently passed four
application-switching returns, panel keyboard/context-menu input, the former
focus/Escape failure, monitor movement and a third genuine Apps-menu cold launch.
See [monitor-integration.md](monitor-integration.md) and
[focus-integration.md](focus-integration.md).

Fusion's native MCP tools are registered and working directly in the active
Codex session, including after all three cold restarts. The optional Omarchy widget
passed its live lifecycle review and is installed and enabled. Reopening clears
old diagnostics and scroll state; closing cancels and invalidates a pending report.
Its removal left ordinary desktop operation intact. Standalone Wine Test 2 is
preserved as a separately tested GPU-accelerated fallback; its corrected Normal
selection control passed too. Neither selection correction proves universal
Windows/macOS parity.

Final handoff: the narrative acceptance metadata was deployed through the
integration-only installer without changing the runtime lock or Hyprland config.
All 26 installed ownership entries verified; the enabled widget matched its
reviewed source hashes. The temporary diagnostic callbacks were absent,
Hyprland reported no configuration errors, and normal desktop idle behavior was
restored. Fusion remained open on DP-1 with the saved, unmodified review model.
Private final receipt: `~/.local/state/fusion360-for-omarchy/final-acceptance-20260927.json`.

Everything below is a historical checkpoint. Statements such as “not installed”
or “pending” describe that checkpoint, not the current state above.

## Historical stop before the corrected audit

**Test 1 stopped after a final rejected workflow review.** The private v3
candidate keeps the DirectX 11/DXVK canvas and selects OpenGL for Qt UI
composition. It corrected the gray startup and passed native sketch, grid,
workplane, extrusion, fillet and initial cloud-save checks. However, the reviewer
reproduced a missing face highlight after a normal 6→8 mm extrusion edit at
.3/1/3-second captures. Passive capture showed gray source pixels. A subsequent
read-only API inspection confirmed one selected BRepFace and the correct 8 mm
geometry. At that time this was classified as a rendering failure. The later
controlled audit showed that selected count and type alone did not establish
which face was selected, and the corrected GE retest passed. The broad rejection
below is retained as history, not the current assessment.

The v3 source, exact environment identity and rollback migration support are
complete (76 launcher and 40 installer tests pass; the unchanged desktop rule
suite previously passed all 12). V3 has not replaced the installed v2 launcher.
The final fixture is preserved locally and in the validation cloud document.
Per the user's direction, retain this rejected experiment and begin standalone
Fusion-patched Wine as Test 2 in a separate repository and prefix. See
`experiments.md` for the configuration comparison and decision.

## Previous v2 checkpoint

The installed v2 candidate uses pinned GE-Proton, three scoped X11 fixes, and a
Vulkan presentation-completion fix. Both Fusion's canvas and Qt composition use
DirectX 11. Legitimate sign-in persists. All 121 automated launcher, installer and
desktop-integration checks pass, as do the runtime helper sanitizer checks.
These checks do not establish application acceptance.

The independent review of the ordinary installed launch was rejected. Its canvas
was gray; native sketches and the grid drew, but committing an extrusion left no
visible solid. Passive capture confirmed that Fusion's native source image was
also gray, unlike the earlier source-to-window copying race. The API confirmed a
healthy visible solid; native Fit, an image export and importing the previously
working 64-part fixture did not restore rendering. The reviewer's geometry was
preserved as a local F3D before controlled restarts.

Some diagnostic launches render correctly. Controlled cold tests are isolating
their differences from the ordinary launch. Good and bad runs load the same
graphics libraries; no driver, visibility or camera mismatch has been found.
A repeatable fix and another complete independent review remain necessary. The
optional Omarchy widget follows application acceptance. Historical findings below
describe earlier checkpoints, including successful modeling, file round trips,
assembly navigation and mixed-monitor operation on those configurations.

The gray startup also reproduced in a private control with the original Win32u
module and then with both original Wine graphics modules. It is therefore not
introduced by the presentation or X11 fixes. A separate candidate retains the
DirectX modeling canvas and present-wait correction while selecting OpenGL for
Qt's UI composition; its initial scene renders with all diagnostics disabled.
The reviewer is checking that combination, including the complete sketch toolbar,
before any production configuration change.

The added visual comparison uses actual frames from Autodesk's September 2026
release video and current sketch documentation; see `visual-comparison.md`.
Static interface details agree in the inspected regions. The latest listed build
is the installed 2705.1.25 (September 22). Exact-build native screenshot parity
and universal Windows/macOS behavior are not claimed.

Fusion's native MCP endpoint is enabled and registered for future local Codex
sessions without changing agent-dot-files. Live discovery returned four tools;
a read-only inspection returned the installed version successfully. The endpoint
listens only on 127.0.0.1. See `native-automation.md`.

## Confirmed DirectX canvas presentation race

A native empty-sketch grid toggle was captured after two seconds without any
intervening input or MCP request. The checkbox was unchecked but the screen still
showed the grid. Passive XComposite pixmap reads isolated the cause: the canvas
producer already contained the correct white image, while the visible parent
still contained the old grid. Private evidence is in `root-grid-off` under the
application state directory; `root-grid-baseline` records the preceding state.

The exact Wine source copies an offscreen Vulkan drawable immediately after host
`vkQueuePresentKHR`. Mesa 26.2.2 enqueues that presentation to a worker, so the
copy can run before the new frame reaches the drawable. Wine's OpenGL equivalent
already waits for swap completion before copying. A private opt-in candidate is
being built to wait for the submitted Vulkan present ID before the copy. It is
not installed or accepted yet. Periodic redraws are not used to hide this defect.

The separate File-menu observation retains an actual mapped popup after Escape,
so it is not explained by stale canvas pixels. Its Windows styles match the
Browser palette, while its Qt window class differs. No speculative window-style
change has been promoted.

## Recorded integration fallback

Steam was started normally. It presented a required account login and no existing account
profile. To meet the ordinary independent desktop-launch goal, use the brief's supported
umu fallback with the same pinned GE-Proton11-7. The runtime itself remains containerized.
GE-Proton11-7 requires Steam Linux Runtime 4.0 (appid 4183110). Its official SHA512
checksum was verified successfully before archive extraction.

## Clean installation

Official Autodesk downloader installed Fusion 2705.1.25 into the new prefix in 175 seconds.
The installation log reports successful deployment. The installer started Fusion;
its first launch is still at sign-in and is not accepted. A minimal OpenGL Core
preference was created in the new prefix; TLS-related preferences were not changed.
The installer process ran through srt-bwrap/pressure-vessel and GE-Proton11-7.
The initial bootstrap lacked the umu reentry service; normal launches must enable it
so browser callbacks enter the existing runtime instead of opening a second one.

## Startup investigation

The new runtime service and same-container command reentry are confirmed. Prestarting
Identity Manager gives a ready SSO server, and Fusion receives IsLoggedIn=false normally.
The ordinary launcher waits for a fresh SSO readiness record before starting Fusion.

The desktop was found locked during the startup investigation. The first window
capture showed the splash screen, but moving/resizing the Fusion window caused the
welcome screen and Sign In button to repaint. A clean restart with no Qt graphics
overrides reproduced the welcome screen after the same resize. Neither the experimental
Qt Quick OpenGL setting nor the embedded WebEngine GPU-disable flag is retained.
This is evidence of visible startup controls, not modeling acceleration or acceptance.
Normal input and initial repaint behavior need rechecking after the desktop is unlocked.

The host browser session has provisionally reached Autodesk using the intended Google
account. Fusion itself is not authenticated yet. No old token database was copied.

## Packaging

The standalone launcher, guarded callback route, and optional Omarchy widget are implemented.
Both runtime and runner downloads are pinned in `compatibility-lock.json`. Installation,
private backup/recovery, and owned-integration removal are under isolated verification.
The standalone integration is installed at its permanent paths. The new desktop
protocol handlers replaced the previous defaults after preserving them in a private
manifest; effective defaults are verified. An actual outgoing WineBrowser call from
the live runtime opened the normal host browser successfully. Installer coverage
includes a competing old callback handler to catch xdg-utils fallback behavior.
An independent reviewer is assessing the implementation; hands-on acceptance remains pending.

## Verified checkpoint

- Full installer adoption succeeded against the actual verified runner, Steam runtime,
  existing Fusion deployment, permanent browser helper and desktop handlers.
- All 48 automated tests pass. The independent reviewer reran them and closed the
  implementation findings; see `review.md`. This is code/lifecycle acceptance only.
- The installed desktop entry started the restored prefix. Its first initializing
  window mapped in 12.11 seconds. A second launch returned successfully with the
  same single Fusion process. This is not a signed-in startup or performance benchmark.
- Real closed-prefix backup and restore succeeded. Registry hashes matched the snapshot,
  the prior prefix was retained, and the `pfx` and Z: drive links remained correct.
  Both snapshot directories are private. No authenticated cloud design existed yet.
- A maintenance request while the application was running was correctly refused.
- The clean app process opened `/dev/dri/renderD128` with no software-renderer or
  experimental Qt environment overrides. Actual modeling acceleration is still unverified.

## Signed-in rendering investigation

Fresh browser sign-in returned through the installed callback route. Cached
sign-in survives cold restarts; no old token database was transferred. OpenGL
Core 4.6 on the physical Radeon 8060S is confirmed in Fusion's own diagnostic,
and the process's amdgpu engine counter increases during modeling/camera work.

Initial Qt renderer experiments did not resolve the black native palettes.
Later inspection found that Wine filters Unix `QT_*` variables before creating
the Windows environment, so those particular backend tests were inconclusive.
Diagnostic overrides must use Wine's `WINEQT_*` import mechanism and be checked
inside Fusion; a Unix process environment alone is insufficient evidence. An
exact-source GE-Proton11-7 Wine X11 module was built privately with the matching
Steam runtime SDK. The owned-tool-window patch makes Fusion palettes managed
utility windows. An additional opt-in ARGB input-shape patch fixes alpha-zero
uploads clipped by an X11 bounding shape: the black backing pixels are now
transparent, while input cutouts remain. No global graphics driver or Qt
renderer override was required. The original GE archive remains unchanged.

Actual fixture modeling, cloud save/reopen and F3D/STEP round trips pass; see
`../validation/README.md`. A third patch implements constant-opacity GDI upload
in an ARGB buffer, correcting the Save backdrop despite Hyprland ignoring
`_NET_WM_WINDOW_OPACITY`. The source recipe reproduces the exact module hash.
A Fusion-only `focus_on_activate=false`
rule prevents the desktop from warping the pointer to the main window during
dialog activation. It is being prepared as a removable, backed-up integration.

The pinned overlay, source/build provenance, integrity checks and rollback are
implemented. The installer/launcher/focus suite passed 87 tests before the final
desktop-launch review. An actual-byte
isolated promotion and interrupted rollback restored the original module and
prior lock with full archive verification. A native timeline repaint defect
found during interactive checks is still being investigated. No final
application acceptance or plugin publication has occurred. The independent
reviewer must operate the final installed runtime before the optional Omarchy
widget is enabled and tested.

The stale timeline was present in both direct X11 pixels and its XComposite
backing pixmap. A corrected Qt paint trace showed the new three-feature timeline
being drawn and flushed through implicit D3D11 RHI; the later hover corrected
it without another timeline paint. This narrowed the defect to presentation.
`QSG_RHI_BACKEND=opengl` selects OpenGL for that implicit main-window composition
while leaving the Browser raster path intact. Three real assembly/manual tab
switch pairs, transparent Browser, and Save dialog/backdrop pass on this
configuration. No forced QWidget RHI or periodic repaint workaround is used.
The final installed runtime still requires independent review.

The final overlay and exact three-setting environment were promoted through the
full installer after a fresh private prefix snapshot. The independent reviewer
then caught a normal-launch rejection: Btrfs reports different device numbers
for `stat` and `/proc/PID/maps` even for the same file and inode. This was
reproduced with a private host mapping outside Wine. The launcher now derives
the expected identity from an exact, non-executing private mapping and compares
it with the runtime's mappings, preserving stale/deleted-library rejection.
The correction passed all 88 tests and was deployed through the integration-only
installer. Independent hands-on review has resumed.

That review found a further canvas defect after editing an extrusion, saving the
design to the cloud, and closing it. The active document and its viewport both
reported an empty Untitled design, but the old model remained in the native
OpenGL source image and the main window. A cloud-open/close baseline cleared
correctly: all 26 traced buffer swaps used the requested window, including four
native canvas swaps. The failing edit/save/close trace contained three requests
to swap the canvas device context that instead swapped Qt window drawables;
only two earlier swaps reached the native canvas.

The pinned Wine `win32u_wglSwapBuffers` implementation selects the current GL
context's drawable whenever a context is current, even when the supplied device
context identifies another window. This matches the failed trace and conflicts
with the [Windows SwapBuffers contract](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-swapbuffers),
which targets the window associated with the supplied device context. The next
experiment uses Fusion's native DirectX11 canvas while retaining the working
Qt OpenGL configuration, as the brief permits after OpenGL rendering defects.

The DirectX 11 repeat passes: a native extrusion edit from 13 to 14 mm, cloud
save, and Ctrl+W leave an empty canvas after five untouched seconds. The subsequent
API query confirms the viewport belongs to the empty document. Graphics Diagnostic
reports Radeon 8060S, DirectX 11.0, and software rendering unchecked. The 64-part
fixture also passes; detailed API timings are in `../validation/README.md`.
The installer now seeds this renderer while preserving its original preference
backup. The revised configuration was installed through the normal integration
path before the next independent review.

## Idle runtime cleanup

The launcher service's termination request can leave daemonized Wine services
alive. One Autodesk analytics process had a zombie leader with live worker
threads, which ordinary leader-only inspection missed. Process inspection now
uses live-thread metadata when needed and continues to validate the complete
prefix before stopping anything. Cleanup uses pidfds for exact allowlisted idle
services; a short grace period precedes forced termination of only the observed
stuck device service or an already-zombie, verified analytics group. Applications,
updates, unknown processes, and mismatched runtimes prevent cleanup.

The first 96 tests passed, including shutdown races and refusal cases. A live cleanup
after normal Fusion quit removed both the old orphaned trace runtime and the new
test runtime. A subsequent check found no prefix processes before installation.

Independent code review then reproduced two narrower races: a selected metadata
worker could exit while another worker remained, and application activity could
begin between two signals. Metadata inspection now retries another worker of
the same group and fails closed after identifying a surviving matching prefix.
Every individual signal gets a fresh activity, process-image, runtime-bus and
Wine-server check. The original reproducer and eight targeted regressions passed
independent review. Local desktop file URIs are also normalized into the existing
verified Windows path mapping. The complete suite now has 102 passing tests.
No new Wine patch or application acceptance is claimed from this diagnosis.

## DirectX presentation ordering

The additional screenshot review caught a grid-state mismatch under DirectX:
the checkbox changed, but the visible canvas retained the previous grid state.
Passive XComposite captures separated the two images without sending Fusion an
input event or an API request. The Vulkan source drawable already contained the
correct image; the visible client window contained the previous one.

Wine copied that drawable immediately after `vkQueuePresentKHR` returned. The
installed Mesa implementation queues the X11 presentation on another thread,
so that return does not establish that the source drawable has been updated.
An opt-in `win32u` patch now waits for the application's submitted presentation
ID before the offscreen client copy. It has a finite timeout and preserves the
existing path when the required feature or valid ID is unavailable. Source tests
also cover mixed native/managed batches, repacking failures, and failed host
submissions; none may authorize a wait for an ID that was never submitted.

The independently audited v2 candidate is
`201ef0e0f4d48dfc093a16ffdd221c0ef37427e35ec59238756e0dc54c134d38`.
It runs only in a private experimental runner at this checkpoint. Root observed
workplanes after 350 ms and four matching grid off/on captures after 350 ms,
without incidental mouse movement or MCP calls between action and capture.
Returning Qt's implicit composition to D3D11 also produced the complete sketch
toolbar after its initial transition. Normal raster palettes remain unchanged.

A native orbit of the 64-part test assembly produced 115 canvas presentations
during 2.561 seconds of mouse input, with a median 22 ms presentation interval.
These are source-presentation timings from a diagnostic run, not a measured
display frame rate or final performance certification. The cold comparison using
DXVK's supported `dxgi.syncInterval = 0` produced 116 presentations in 2.565
seconds with the same 22 ms median interval. Workplanes and grid toggles still
passed, but the setting provided no meaningful performance benefit and was
removed. The selected configuration has four required values: the two ARGB
flags, presentation completion, and Qt D3D11 composition. Inherited inline and
file DXVK overrides are cleared and incompatible sessions are rejected.

The reviewer independently repeated four grid toggles at 350 ms and workplane
checks at one and five untouched seconds on the default-DXVK v2 candidate.
Those checks pass. Complete production workflow acceptance is still pending.

The interrupted first experimental logger left one recovery entry for root's
empty sketch, timestamped 17:27:16 local time. A later attempt to open it,
followed by an API inspection, left the recovery dialog unresponsive; the cause
was not isolated. The intact recovery directory and index were preserved in a
private backup before stopping that owned test service and moving the test entry
out of the active profile. The subsequent cold launch, native grid tests, model
import, MCP operations and normal quit worked. This does not establish recovery
dialog correctness, and scripts should not be sent while native dialogs or
document loading are active.
