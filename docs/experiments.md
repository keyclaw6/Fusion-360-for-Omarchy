# Runtime experiments

This is **Test 1: GE-Proton through umu and Steam Linux Runtime 4**. Proton
already uses Wine. The separate direct-host Wine test replaces the runtime
and its Linux library environment, not introduce Windows compatibility for the
first time. No Windows VM or software renderer is part of these tests.

The corrected visible-face controls subsequently passed in both routes. GE v3
has been promoted to the installed launcher and is undergoing the remaining
independent desktop review. See [the corrected retest](ge-normal-retest.md),
[the monitor repair](monitor-integration.md) and
[the current review](operational-review.md). The table records the earlier
sequence and decisions at those checkpoints, not the current acceptance status.

## Fixed baseline

Fusion 2705.1.25, Radeon 8060S, RADV/Mesa 26.2.2, Omarchy 4.0.4-1 and
Hyprland 0.56.2. The ordinary mixed-scale desktop is the target. The runner is
GE-Proton 11-7, launched by umu 1.4.4 inside Steam Linux Runtime
4.0.20260914.260627. Exact downloads and module hashes are in
`../compatibility-lock.json` and `../runtime-patches/manifest.json`.

The original Steam-client route required another account login. The supported
umu integration uses the same Proton family without requiring that client.

## Historical experiment sequence

| Configuration or control | Observation | Decision |
| --- | --- | --- |
| Fusion OpenGL Core modeling canvas | Physical GPU verified; modeling and file round trips worked, but the independent reviewer found stale geometry after normal editing/save/close. | Rejected for everyday use. |
| Fusion DirectX 11 through DXVK | Corrected that edit reproduction and rendered the 64-part fixture. Transparent palettes and modal backdrops needed scoped Wine X11 corrections. Native grid changes later exposed an offscreen presentation race. | Continue only with the documented graphics corrections. |
| Patched v2: DirectX canvas and DirectX Qt UI composition | Native grid/workplane tests passed. Ordinary installed cold launch then produced a gray canvas and invisible solids. Source-image capture and Fusion image export were gray too. | Installed application review rejected. |
| Original `win32u.so`, then both original Wine graphics modules | Gray canvas reproduced with diagnostics disabled. | The added graphics patches are not required to trigger the gray-startup failure. |
| Controlled diagnostic environments | Some settings render correctly, including two nonexistent Wine debug channels. Zero/one-channel controls were gray. Loaded library identities matched. | Diagnostic correlation only; dummy debug flags are not a release fix. |
| Same patched module pair, DirectX modeling canvas, **OpenGL Qt UI composition**, diagnostics disabled | Native sketch/grid/workplanes, extrusion, fillet and initial cloud save passed. After a native 6→8 mm extrusion edit, the face highlight stayed gray at .3/1/3 seconds. Passive source pixels were also gray; the first subsequent API read confirmed one selected BRepFace, the 8 mm extrusion and three timeline features. | Final Test 1 candidate rejected. V3 source is retained; no production promotion. |
| Direct-host Fusion-patched Wine | Installed and operated separately in [Test 2](../experimental/wine/docs/comparison.md). Native shader compiler setup corrected invisible solids; source-matched Wine 11.17 alpha patches corrected the Browser. Native post-edit face highlighting still failed on the final ordinary installation. | Independent reviewer rejected Test 2 as well. Both experiments are preserved; the overall goal is incomplete. |

Canvas rendering and Qt UI composition are separate settings. The last row of
the Proton experiments keeps the modeling canvas on DirectX 11/DXVK and the
physical Radeon GPU; selecting OpenGL for Qt does not select Fusion's previously
rejected OpenGL modeling canvas.

## Stop rule and comparison

On 26 September the user authorized one focused final repair/review of Test 1,
followed by an explicit assessment. If ordinary operation remains unreliable,
retain this repository, record the failure and create a separate Test 2
repository for direct-host Wine. Preserve the first prefix and local validation
designs before changing runtimes. Do not keep adding diagnostic environment
switches to obtain a favorable startup.

Either route must pass native grid and selection changes, sketch/extrude/fillet
and feature edits, responsive assembly navigation, cloud save/reopen, local
file round trips, normal dialogs and desktop launching, repeated cold starts,
and actual GPU evidence. The independent reviewer must operate the final
installed configuration. Unit tests, one good screenshot and an API-created
solid are useful evidence but do not satisfy that acceptance gate.

The focused final attempt reached that stop rule. The selection defect recurred
after a normal native feature edit, even though the initial gray-canvas startup
was corrected. Continuing to tune this runtime would require another graphics
investigation. The following experiment used standalone Fusion-patched Wine in
its own repository and prefix. That route improved specific rendering defects
but did not pass the independent post-edit selection gate either. See the
[two-route assessment](../experimental/wine/docs/comparison.md).

The final three-feature, 8 mm reviewer model was exported to a private local
F3D (54,455 bytes) and saved to its existing validation cloud document before
closing Test 1. No personal design was used as the failure fixture.

Test 2 subsequently identified that its application was loading Wine's builtin
`d3dcompiler_47` instead of the Microsoft compiler shipped with Fusion. Its
private native-compiler setup corrected invisible geometry. The later corrected
GE retest verified that GE already loaded Autodesk's native shader compiler;
the absence of the same explicit Test 2 override was not evidence that GE used
the builtin compiler. GE's exact-face selection control passed with Normal
already selected. The earlier blanket rejection was premature; its preserved
observations do not establish an unavoidable defect or its original cause.

Private screenshots, logs, prefixes, authenticated state and F3D fixtures stay
outside Git. See `progress.md` for historical checkpoints and `review.md` for
the earlier independent verdict. The current verdict is in
`operational-review.md`.
