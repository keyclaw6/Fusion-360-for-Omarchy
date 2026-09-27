# GE-Proton selection retest and v3 promotion — 26 September 2026

The preserved GE-Proton candidate passed the corrected visible-face selection
test, including a native extrusion edit. Its prior blanket rejection was
premature. The tested v3 configuration has now been deployed through the normal
installer. The subsequent [independent operational review](operational-review.md)
accepted the installed application for its documented scope.

## Retest observations

The private candidate used the same GE-Proton 11-7, reviewed two-module overlay,
Steam Linux Runtime 4, DirectX 11/DXVK modeling canvas and Qt OpenGL UI as the
last candidate. The original profile already reported Normal selection (`0`),
Custom graphics and Dynamic enabled. No Fusion preference was changed for this
retest, so its result should not be described as the same setting change that
helped standalone Wine.

The root reopened the preserved holed/filleted validation plate into a new test
document. A settled native click selected the identified, visible +X face and
displayed blue. Its area was 1349.735 mm², with the face plane at x=8 mm.
The extrusion was then edited to 10 mm through the native timeline dialog.
After Escape, a fresh settled native click again displayed blue; the pointer
was moved away before the screenshot. No API call occurred between the native
edit and this screenshot. Subsequent inspection confirmed the +X face plane at
x=10 mm, the same face area and the 10 mm extrusion. The original F3D was not
overwritten; the temporary imported document was closed without saving.

Live process mappings confirmed the reviewed GE graphics modules, host Radeon
RADV, DXVK and Autodesk's native shader compiler. The result disproves a
deterministic unavoidable selection blocker in this control. It does not prove
why the earlier review differed or rule out intermittent issues elsewhere.

Private evidence:
`~/.local/state/fusion360-for-omarchy/ge-normal-retest-20260926/`:

- `ge-normal-first-native-selection.png` and matching state JSON.
- `ge-native-edit-dialog.png`, `ge-edited10-result.png`.
- `ge-normal-native-after-edit10.png` and matching state JSON.
- `ge-graphics-before.json`, `ge-baseline.json`, `ge-modules.json`.
- Input/probe helpers and the pre-test preferences copy.

## Safe promotion

After closing Fusion and the dedicated experimental runtime, the installed v2
lock, recipe manifest, ownership manifest, active receipt and current MIME
defaults were preserved privately. A closed-prefix snapshot was created:

`~/.local/share/fusion360-for-omarchy/backups/snapshot-20260926T204658Z-e0b032af`

The supported `maintenance.py rollback-overlay` restored the original modules
and prior lock. Its rolled-back v2 receipt was preserved separately. A full
`install.py --no-packages --overlay-dir` then promoted the already verified
module pair to v3, preserving the prefix. Integration-only installation and
manual lock replacement were not used. Autodesk callback defaults deliberately
returned to Test 1; the preceding Test 2 defaults remain in the private record.

Nine focused existing tests passed: legacy receipt migration/rollback, exact v3
environment, old-session rejection, preference preservation and real desktop
registration. The installation agent independently verified 20 deployed support
files and 26 ownership entries against source/manifest, an active v3 receipt,
the exact graphics module hashes and effective protocol defaults.

The installed v3 identity is
`c47f8b1d22dd6f0152b54166cbb57707af5992200281c0252bef82829b15731d`.
Its normal desktop entry is **Fusion 360 for Omarchy**. Standalone Wine remains
preserved in its separate repository and prefix. No agent-dot-files were changed.

## Subsequent independent acceptance

The fresh independent reviewer operated the installed candidate and passed
native modeling, grid/workplanes, identified selection, cloud and local
persistence, navigation, tested menus/dialogs and ordinary cold launches.
Two subsequent scoped desktop repairs passed the formerly failing individual
monitor moves and palette visibility after focus changes. The reviewer accepted
the tested application scope on 27 September; see
[operational-review.md](operational-review.md) for evidence and explicit limits.
This later hands-on decision, rather than the root retest or installer checks,
satisfies the application gate. The optional Omarchy widget is reviewed separately.
