# Standalone Wine experiments

All rows use the same Fusion 2705.1.25 build, standalone patched Wine 11.17,
XWayland, the physical Radeon 8060S and the preserved DXVK pair. The first
repository and prefix remain separate. This route has no Steam runtime at
application launch. A private SDK is used only to compile the transparency
module.

| Configuration | Native result | Verdict |
| --- | --- | --- |
| Wine builtin shader compiler, DirectX canvas, Qt OpenGL | Sketch/axes/planes visible; committed 6 mm solid disappears at 1 and 5 seconds; Browser black. | Rejected. |
| Autodesk-shipped native shader compiler, same renderers | Grid, sketch, extrusion, fillet and 6→8 mm edit render correctly. First face highlight after editing stays gray at 1 and 3 seconds. | Geometry improved; rejected overall. |
| Same, with Fusion's Simple selection display | Native 8→10→8 mm edits render; face remains gray at 1 and 3 seconds after both edits, despite native status reporting one face selected. | Simple is not a fix on this configuration. |
| Native compiler, DirectX canvas and Qt DirectX | Ordinary authenticated cold launch and imported preserved fixture render correctly. Native 8→10 mm edit succeeds; selected face remains gray at 1 and 3 seconds. | Rejected. |
| Native compiler in both Autodesk and private system32 locations; source-matched Wine 11.17 ARGB input-shape and constant-alpha corrections; DirectX canvas and Qt | Ordinary installed launch maps both native compiler copies and the new module. Reviewer passes Browser transparency, grid/workplanes, rectangle, extrusion, fillet and 6→8 mm edit. Face highlight remains gray after editing; subsequent read confirms one selected BRepFace. | Final candidate rejected. |

Fusion reports hardware DirectX initialization on the Radeon. Passive Linux
DRM counters also increased during the native compiler modeling review: graphics
engine time rose from 365,907,445 to 426,433,518 ns over 9.029 seconds. This is
evidence of work on the physical GPU, not a frame-rate or native-Windows parity
measurement.

The reviewer operated native commands before API inspection in the first three
rows. The fourth row reopens the reviewer's own exported fixture through MCP,
then tests native feature edits. The fifth row starts a fresh native design
through the ordinary installed launcher. No personal design is a test fixture. Screenshots, logs, account
state, runtime files and F3D exports stay outside Git.

The acceptance gate remains correct grids, geometry and selection after normal
editing, responsive representative navigation, usable panels/dialogs, cloud and
local file round trips, repeatable cold starts and independent operation of the
ordinary installed application. Packaging checks cannot waive those failures.
