# Application fixture

`FusionValidation` is an optional Fusion script for repeatable application checks.
It creates a new document with a parametric plate, tests a thickness edit, adds
four through holes and corner fillets, and builds an array of 64 instances.
It exports a Fusion archive, STEP file, viewport image and JSON observations to
a unique `%LOCALAPPDATA%/FusionOmarchyValidation/` directory in this installation.
It does not open or modify existing designs or automatically save to the cloud.

Run the script through Fusion's Scripts dialog after successful sign-in. Inspect
the result and verify local import and cloud save/reopen separately. Camera/refresh
API timings characterize those calls only; they are not display FPS, input latency,
or proof of GPU acceleration. The independent reviewer must still operate Fusion
and inspect rendering and responsiveness directly.

The script was written against the API definitions bundled with Fusion 2705.1.25.
Its first live run on 2026-09-26 completed: all 64 occurrences were created,
feature health and the thickness edit passed, and the measured master volume
matched the analytic result, 30.3640355263 cm³. Nonempty F3D, STEP and viewport
image files were written. Construction took 0.91 seconds; 90 camera/refresh
calls had a median of 20.70 ms and p95 of 22.50 ms. These are API call durations.

That run requested an experimental Qt widget/OpenGL environment. Later inspection
showed Wine had filtered those `QT_*` variables, so that request is not evidence
that the backend changed. Native transparent
panels still rendered black, and modal window handling prevented cloud-save
verification. The geometry result is useful evidence, but it does not accept
the desktop installation or establish the final renderer configuration.

## Corrected renderer run, 26 September 2026

The implementation agent repeated the fixture with the separate GE-Proton11-7
owned-tool-window/ARGB-input-shape candidate and no Qt rendering overrides.
All geometry and feature checks passed again. Construction took 0.89 seconds;
90 camera/refresh calls had median 21.38 ms, p95 22.68 ms, maximum 31.87 ms.
These remain API call durations, not measured display FPS.

Fusion's Graphics Diagnostic showed Radeon 8060S, OpenGL Core Profile 4.6,
and an unchecked software-renderer option. The process's amdgpu graphics-engine
counter increased from 244,105,393 to 836,275,416 ns across the modeling/camera
test. The Browser's transparent backing pixels changed from opaque black to
ARGB zero, and actual desktop captures show the corrected panel and geometry.

The Save dialog created a new validation folder in Default Project and saved
the 64-plate document. Fusion then reported saved=true, modified=false,
cloud_complete=true and cloud_version=1. Closing and reopening that cloud
document, importing its F3D archive, and importing its STEP export each restored
64 solid plates with the expected master volume, 30.3640355263 cm³.

A desktop mouse click selected a real BRepFace, with the corresponding face
highlighted. Mouse orbit, pan and wheel zoom changed the view correctly.
The attempted screen recording was incomplete and provides no timing evidence.
Full responsiveness and ordinary desktop behavior remain subject to the
independent reviewer. Native Save-modal backdrops still appear opaque black
because this Hyprland version ignores the X11 constant-opacity property; that
separate defect remains open. None of these observations constitutes acceptance.

## Constant-opacity correction

A third candidate adds an opt-in GDI constant-alpha upload path, using a separate
premultiplied upload buffer. A fresh build through the repository recipe exactly
reproduced its SHA256, `6b5f680717f8e1db59039eeb50a953ac7703d6a7e88cd1e891c345e372020f1f`.
Actual Save-backdrop pixels now have alpha 76/255 (`0x4c000000`), and desktop
captures show the intended dimmed model with an opaque, usable Save dialog.
The 64-part fixture again passed, with construction 0.897 seconds and API
camera/refresh median 21.04 ms, p95 22.55 ms and maximum 43.24 ms.

A fully transparent MessageTray window still received a compositor border.
Removing only that named Fusion window's border removes the empty rectangle;
the notification window, contents and input behavior are retained.

Further testing confirmed a separate timeline-redraw defect: switching from the
64-part document to the reviewer's single-part document updates the canvas and
Browser, but the timeline can retain the assembly icons until pointer hover.
This occurred with real document-tab clicks as well as an API import and was
treated as an acceptance blocker. A manually edited extrusion redrew correctly within
the first 0.48-second capture, so this is not evidence of a general canvas stall.

## Targeted UI composition correction

A Qt paint trace showed the new timeline reaching the main window's implicit
D3D11 RHI composition. Hover corrected the visible timeline without another
timeline paint. Selecting `QSG_RHI_BACKEND=opengl` changes that implicit
composition while preserving raster rendering for the transparent palettes.
Three real tab-switch pairs between the 69-feature assembly and the three-feature
manual part then updated the timeline without pointer hover. The Browser and
Save dialog/backdrop remained correctly rendered. Globally forced QWidget RHI
and periodic redraws are not part of this configuration.

The exact three-patch module and this scoped setting are now installed through
the normal launcher. The independent reviewer is testing the final installed
runtime; their result belongs in `../docs/review.md` and is not implied by these
implementation-agent observations.

## Native DirectX 11 canvas

The final-runtime reviewer rejected OpenGL Core after a native extrusion edit,
save and close left the old model in an empty document. A controlled repeat
captured three canvas swap requests being sent to Qt surfaces by Wine; a close
without the preceding feature edit had no such mismatch. This is separate from
the corrected feature-timeline presentation.

Changing Fusion's canvas preference to `VirtualDeviceDx11`, while retaining
`QSG_RHI_BACKEND=opengl`, clears the model after the same native edit/save/close
sequence. The untouched five-second capture shows an empty canvas; the subsequent
API query confirms the viewport belongs to the empty document. Graphics Diagnostic
reports Radeon 8060S and DirectX 11.0 with software rendering unchecked.

The fixture run at `20260926T142034.749946Z` passed all geometry, feature-health,
volume and export checks. Construction took 0.792 seconds. The 90 camera/refresh
calls had median 4.70 ms, p95 5.77 ms and maximum 68.14 ms. These are API call
durations, not display FPS or input latency. This configuration still requires
the independent reviewer to repeat the full interactive workflow.
