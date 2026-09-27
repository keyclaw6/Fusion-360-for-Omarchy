# Two-route assessment — 27 September 2026

**Both approaches were installed and operated with hardware GPU acceleration.
Corrected controls passed native post-edit selection in both routes, so rejecting
both over this symptom was premature. Installed GE-Proton v3 has subsequently
passed independent modeling, rendering, file workflows, monitor movement and
three authenticated cold starts. The final palette focus repair passed, and
the independent reviewer accepted GE for the documented application scope.**
Standalone Wine remains a working selection/modeling fallback with a narrower
review; it has not passed that full operational gate.

| Route | What was actually tested | Outcome |
| --- | --- | --- |
| **Test 1: GE-Proton 11-7 through umu and Steam Linux Runtime 4** | OpenGL Core canvas first, then DirectX 11/DXVK; scoped Wine window/presentation patches; DirectX/OpenGL Qt controls; corrected exact-face selection retest; installed v3 operational review. | Independently accepted for the documented Design/modeling, rendering, file and desktop scope. Native file round trips, assembly navigation, repaired monitor/palette behavior and three authenticated cold starts pass. |
| **Test 2: standalone Fusion-patched Wine 11.17** | Same Fusion build directly on the host, DirectX 11/DXVK canvas, both Qt backends; Autodesk's native shader compiler; source-matched Wine transparency corrections; subsequent Simple/Normal selection audit. | Fixed invisible solids and black Browser panels. Grids and native modeling passed. Simple showed gray selection; Normal showed blue before/after native edits and after a cold restart. Full operational acceptance remains pending. |

Proton is itself Wine-based. Test 2 replaces Proton and its Steam library
environment with standalone Wine; it is not a native Windows build. Test 2 did
not retest Fusion's OpenGL Core modeling renderer. The Qt backend controls are
separate from that canvas setting.

## What improved

In Test 2, selecting the Microsoft shader compiler already shipped by Autodesk
made committed geometry visible. Qt also requested a system compiler, so the
same verified native DLL was copied only into Test 2's private system32, with
the old file preserved. A reproducible Wine 11.17 X11 module corrected Browser
transparency. Its exact source inputs, hashes, ABI checks and sanitizer tests
are included in the repository. The launcher has 33 passing isolated tests.

The actual application reports hardware DirectX initialization on the Radeon
8060S. Live module maps and per-process DRM engine counters corroborate work on
the physical GPU. This establishes acceleration; it is not a frame-rate or
Windows/macOS performance-parity measurement.

Normal browser sign-in succeeded in Identity Manager, although Fusion initially
reported a handoff failure. A cold restart entered an authenticated workspace,
and later cold starts retained it. The first handoff error is still recorded.
Test 2's final cloud-save/reopen acceptance was not reached.

## Correction to the selection rejection

The earlier reviewer saw a gray face and confirmed one selected BRepFace, but
did not identify that face or test the final candidate with Normal selection.
The root audit verified an empty selection, the exact visible face, screen
coordinates and native selected-area readout. Gray reproduced under Simple even
before a new edit. With Normal, fresh native clicks displayed blue before and
after native timeline edits from 8→10→8 mm, and after closing Fusion and its
dedicated Wine server and performing an ordinary cold launch.

An A/B/A comparison returned gray under Simple after reselection and blue again
under Normal on the same face. An immediate screenshot after switching to Simple
retained the prior blue until reselection, explaining why the earlier positive
control was unreliable. A fresh independent auditor inspected this evidence and
agreed that the whole-route rejection was premature. The root agent operated
these controls; the final independent operational gate is still outstanding.
See [the audit](reviewer-audit.md) for exact evidence and limits.

Whether gray in Simple is intended on native Windows/macOS remains unverified.
The current evidence does not locate a Wine/DXVK/driver fault. Test 1 subsequently
passed its corrected visible-face control with Normal already selected. No
preference change was needed there, so its success does not establish the same
cause as Test 2. Both routes shared components and test methods; the repeated
old symptom was not independent proof of a common cause. See
[the GE retest](../../../docs/ge-normal-retest.md).

## Recommendation and limits

Standalone Wine has the simpler runtime arrangement because it does not require
the Steam runtime. GE-Proton has the more complete installer, rollback, removal,
desktop launch and protocol integration, and now the more extensive passing
hands-on workflow evidence. **GE-Proton v3 is the primary installed candidate.**
This does not establish greater frame rate or universal compatibility than
standalone Wine. The separate Test 2 prefix, native-compiler findings and
reproducible source remain preserved as a fallback.

Both implementations are now preserved in one public repository: GE at the root and unfinished Wine in `experimental/wine/`. The final reviewer has accepted the installed palette
focus repair; the optional GE widget also passed its separate live lifecycle review. GE passed
cloud save/reopen, local F3D round trips, representative assembly navigation,
tested menus/modals and repaired mixed-monitor movement. See
[the operational report](../../../docs/operational-review.md).
The evidence does not support a blanket Windows/macOS parity promise.

The native Fusion MCP server is configured in Codex and was exercised for
inspection, export and reopening test fixtures. Recent official September 2026
visual references were compared during Test 1; [the visual report](../../../docs/visual-comparison.md)
records their dates and exact-build limits. Static layout comparison and native
operation were checked separately. The optional Omarchy widget is installed and
enabled on the accepted GE installation after its own live lifecycle review.

The original Test 2 model was exported privately to F3D (86,749 bytes). Its runtime
is closed while GE-Proton remains the primary installation. The original local histories, runtime backups, private validation designs and
evidence are preserved privately; this public source tree contains both
implementations without those runtime or account artifacts. No agent-dot-files were changed. See [the historical review](review.md),
[its critical audit](reviewer-audit.md) and [the experiment matrix](experiments.md)
for the detailed record.
