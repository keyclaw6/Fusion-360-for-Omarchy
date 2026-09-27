# Test 2 progress

**Latest correction:** [the critical audit](reviewer-audit.md) demonstrated
blue face selection with Normal display before/after native feature edits and
a full cold restart. The broad rejection below was premature. Normal is retained
locally; the full independent operational gate remains pending. The sections
below preserve the earlier implementation/review history. GE-Proton v3 is the
primary installed candidate and has subsequently passed independent modeling,
rendering, file workflows, mixed-monitor moves and three authenticated cold starts.
Its installed palette focus repair passed, and the independent reviewer accepted
the documented GE application scope. Test 2 retains its narrower review. See
[the current comparison](comparison.md).

Status: **round complete; final installed candidate rejected**. The reviewer
passed corrected Browser transparency, sketch grid/workplanes and native model
editing, but a selected face still remained gray after a 6→8 mm extrusion edit.
The user's acceptance gate has not passed. See [review.md](review.md) and
[the two-route assessment](comparison.md).

Test 1 is preserved at local commit `c92f298` in the separate **Fusion 360 for
Omarchy** repository. Its private final candidate missed face highlights after
native feature editing. Test 2 uses the complete community Wine 11.17 runtime
directly on the host, with the same Fusion 2705.1.25 build and initial DirectX
11/DXVK canvas plus Qt OpenGL UI selection.

## Preparation completed

- The 568,123,659-byte release archive matched its published SHA-256. It was
  extracted safely into a new private runtime directory. `wine --version`
  reports `wine-11.17`; seven critical runtime executables/modules are pinned
  separately in the lock.
- The closed Test 1 prefix was copied using copy-on-write storage. Original
  registry hashes remained unchanged. Test 2 uses `USER=steamuser` only in the
  Wine child environment, preserving the existing Windows profile path.
- Wine updated the copied Windows environment. Its optional Mono installer
  appeared outside the monitor because of inherited window placement. The
  dialog was moved into view and declined; Fusion's native application does not
  currently require that optional package. No global package was changed.
- 1,231 copied links to GE builtins/fonts now reference corresponding files in
  the new Wine runtime. 59 unmatched ancillary PE/font resources were copied
  into the test prefix as ordinary files. No GE Unix module was transplanted.
  A private record retains the original links and replacement hashes.
- The copied DXVK `d3d11.dll`/`dxgi.dll` pair remained byte-identical. The test
  prefix explicitly selects those native DLLs, X11 graphics and disables Wine's
  automatic menu builder. The live Fusion process maps those native DLLs, the
  new Wine Unix modules, host RADV/Mesa, and opens `/dev/dri/renderD128`. No
  Unix module from the first runtime remains mapped. Subsequent per-process
  DRM counters recorded physical GPU work during modeling; see experiments.md.

## Authentication boundary found

Identity Manager could not decrypt the copied Proton login database under
standalone Wine and did not reach SSO readiness. The entire copied
identity-cache directory was preserved in a private Test 2 backup, then a fresh
directory was created for a normal login. The original Test 1 login state is
untouched. No tokens were extracted or injected.

Fresh Identity Manager initialization reaches SSO readiness, and Fusion shows
its welcome/sign-in screen. The dedicated launcher and callback have been
deployed after 22 isolated tests passed. Status verifies the exact runtime,
prefix and session environment. Its detached systemd worker retains the Wine
processes when the invoking terminal exits.

The `adskidmgr` handler is now deliberately assigned to Test 2; its previous
Test 1 value and owned-file hashes are recorded privately in
`STATE/integration-record.json`. WineBrowser in the copied prefix selects the
new host-browser helper. No authentication URI is logged by either wrapper.
The `fusion360` scheme remains assigned to Test 1 pending a tested Test 2 file
opening contract. Cloud save/reopen is still required.

## Initial native result

The normal browser login completed in Identity Manager, but Fusion initially
displayed a Sign in Failure dialog. After a full, clean restart, Identity
Manager reported `IsLoggedIn=true` and Fusion entered the workspace. The first
handoff error remains an unresolved defect; dismissing it alone was not treated
as successful authentication.

The independent reviewer used native commands, without MCP, to select a sketch
plane, draw a 30 × 50 mm rectangle and extrude it 6 mm. The sketch grid, axes,
rectangle and extrusion preview appeared, but after committing the extrusion
the body disappeared into flat gray at both one and five seconds. The Browser
panel was opaque black. The first subsequent read-only MCP call confirmed one
body and two timeline features. This configuration fails the visual gate.

Fusion's own log reports successful hardware DirectX 11 initialization on the
Radeon 8060S and Qt OpenGL composition. That confirms device selection, not
correct rendering. The native validation model was exported privately to F3D
(46,964 bytes), and both new test documents were closed before runtime changes.

## Scoped shader-compiler control

Live module inspection found Wine's builtin `d3dcompiler_47`, although the
Autodesk deployment includes Microsoft's native compiler. The upstream recipe
also specifies a native compiler. A per-application Wine override was
tested for `Fusion360.exe` only: `d3dcompiler_47=native,builtin`. This uses the
DLL already shipped by Autodesk, with no replacement download. The original
override was absent and is recorded privately for reversal.
The cold restart mapped Autodesk's shipped `d3dcompiler_v2/d3dcompiler_47.dll`
(Microsoft 10.0.14393.33). The independent reviewer then passed native grid and
workplane display, rectangle/extrusion, fillet and a 6→8 mm dimension edit:
committed geometry now remains visible and changes correctly.

Post-edit face highlighting still failed at one and three seconds. The native
status bar showed one selected face, so this was not inferred from API input.
Fusion's built-in Simple selection preference was then selected through its
documented API. Native 8→10→8 mm edits still reproduced the missing highlight.
The setting is therefore a failed control, not a repair. The final fixture was
exported privately (80,143 bytes); subsequent API inspection confirmed one body,
three timeline features, Simple mode and one selected entity.

The Qt DirectX 11 control still failed post-edit highlighting, although geometry
remained correct. Moving the pointer away, a subsequent API read and an explicit
viewport refresh also left the selected face gray. The test fixture was exported
privately at 10 mm (80,948 bytes), then both test documents were closed.

## Final combined candidate

Qt DirectX was additionally loading Wine's system compiler while the modeling
engine used Autodesk's native v2 compiler. The same verified native x64 DLL has
now been copied to the closed Test 2 prefix's system32 directory. Both copies
are pinned; the override remains limited to Fusion. The previous compiler,
runtime module, helpers, lock, session record and registries were backed up
privately before migration.

The two source-matched ARGB corrections are now installed in Wine 11.17's
`winex11.so`. The complete source recipe reproduces its exact hash, passes ABI,
imports, dependencies and relocation checks, and passes ASan/UBSan tests of the
actual upload and shape functions. All 33 launcher tests pass. The new session
identity includes the locked module hashes, both compiler files and renderer
flags. Ordinary launch requires that exact configuration.

The final-round candidate keeps both Qt and the canvas on DirectX 11 and enables
only the two scoped alpha corrections. Live maps show both native Microsoft
compiler copies. No dummy debug flags or timer-based redraw helper is used.
The independent reviewer operated this ordinary installation from a fresh native
design. Browser transparency, workplanes, grid toggles, rectangle, extrusion,
fillet, feature-dialog legibility and the visible 6→8 mm edit passed. The face
highlight still failed. A corrected read-only MCP call subsequently confirmed
one selected BRepFace, SelectCommand, Simple selection, one body and three
timeline features. This confirms the reviewer's state evidence independently
of the entry-point error in the reviewer's initial probe.

The final model was exported privately to F3D (86,749 bytes) and closed. Fusion
and its dedicated Wine session were then closed; zero prefix processes remained.
Normal desktop idle behavior was restored. No additional renderer permutation
was attempted after rejection.

## Unmet completion gate at the original review

Correct post-edit selection remains the blocker. The reviewer therefore did not
continue into the final candidate's cloud-save/reopen, local round trips,
navigation performance, monitor, modal-menu or cold-relaunch acceptance checks.
Earlier candidates' successes do not waive those missing checks. The Omarchy
widget remains uninstalled. A more complete installer cannot repair this
rendering failure and was not released for Test 2.
