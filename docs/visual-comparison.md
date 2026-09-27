# Visual reference comparison — 26 September 2026

Actual Autodesk reference images were retrieved and visually inspected against
the saved Fusion evidence. The static model and interface conventions agree in
the inspected areas. **The installed v3 captures now pass the grid, workplane,
sketch-detail and post-edit selection comparisons below.** Earlier blanket
rejections were narrowed by the controlled audits. Static images alone do not
establish application acceptance; the final workflow verdict belongs in
[operational-review.md](operational-review.md).

The v2 captures were opened and visually inspected alongside the earlier failed
states, which remain documented below. This comparison reviewed saved evidence;
it did not operate Fusion or change the desktop.

## Reference provenance

- Autodesk's [September 2026 update article](https://www.autodesk.com/products/fusion-360/blog/september-2026-major-product-update-whats-new/)
  is dated September 3 and lists the installed version, 2705.1.25, under its
  September 22 minor update. A remote screenshot of the actual article was
  downloaded, then opened with the image viewer.
- The official Autodesk Fusion channel's
  [September 2026 feature video](https://www.youtube.com/watch?v=kngczKTKIdw)
  was published September 1. Its 1920×1080 visual stream was downloaded using
  yt-dlp; unaltered frames were extracted with FFmpeg at 34, 48, 78, 265, and
  283 seconds and opened with the image viewer. Channel identity:
  `@adskFusion`, `UCiMwMz3RMbW5mbx0iDcRQ2g`.
- These are official demonstrations for the same monthly release family. The
  video does **not** display a verified 2705.1.25 build number and predates the
  minor update. It is not an exact-build screenshot or a locally tested Windows
  or macOS installation.
- Current Autodesk [sketch documentation](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-3D-SKETCH.htm)
  supplies the definitions of blue closed profiles, black constrained geometry,
  and the grid visibility control. Its example images were also downloaded and
  inspected. Their capture date/build is unspecified; they are supplementary
  references, not presented as September captures.

## Installed v3 comparison

During the fresh operational review, the root independently opened the new
reviewer's captures beside the same official references. These are screenshots
of ordinary native input, not API-generated viewport renders. Evidence is under
`~/.local/state/fusion360-for-omarchy/operational-review-ge-v3/`.

| Area | V3 evidence | Observation |
| --- | --- | --- |
| Grid state and axes | `grid-off.png`, `grid-on.png` | Unchecked removes the grid; checked shows continuous fine lines and colored axes. The historical checkbox/canvas mismatch is absent in this pair. |
| Workplanes | `fresh-workplanes.png` | Orange origin planes, colored axes and the plane-selection prompt are visible. |
| Sketch detail | `native-rectangle-50x30.png` | Legible 50.00 and 30.00 dimensions, constraint marks, black constrained edges and light-blue closed-profile shading agree with Autodesk's documented conventions. |
| Selection after a native edit | `selected-after-native-edit.png` | The identified visible face is blue after the 6→8 mm edit; the fillet and thin boundary edges remain clear. The official video at 48 seconds uses the same blue selection convention. Different lighting, geometry and selection contexts prevent a pixel-color identity claim. |
| Interface structure | The captures above and official video at 78 seconds | Toolbar groups, Browser, Sketch Palette, timeline, ViewCube and navigation controls are present and legible. The available tools and workspace layout differ with document type and entitlement. |

The source paths, sizes and hashes for this comparison are recorded privately in
`ge-normal-retest-20260926/v3-visual-reference-comparison.json`. No new reference
date or exact-build native comparison is implied. The live reviewer separately
tests redraws and navigation; these still frames do not measure frame pacing.

## Historical v2 candidate retest

These local links open private evidence on the implementation machine. The root
agent's v2 captures and the independent reviewer's preliminary v2 captures both
show the corrected states. They precede final production acceptance.

| Area | Root agent's captures | Independent reviewer's captures | Observed result |
| --- | --- | --- | --- |
| Repeated grid toggles | Off 1 (private evidence: `~/.local/state/fusion360-for-omarchy/v2-grid-toggle-1.png`), on 2 (private evidence: `~/.local/state/fusion360-for-omarchy/v2-grid-toggle-2.png`), off 3 (private evidence: `~/.local/state/fusion360-for-omarchy/v2-grid-toggle-3.png`), on 4 (private evidence: `~/.local/state/fusion360-for-omarchy/v2-grid-toggle-4.png`) | Off (private evidence: `~/.local/state/fusion360-for-omarchy/reviewer-preliminary-v2/grid-off-350ms.png`), on (private evidence: `~/.local/state/fusion360-for-omarchy/reviewer-preliminary-v2/grid-on-350ms.png`), off again (private evidence: `~/.local/state/fusion360-for-omarchy/reviewer-preliminary-v2/grid-off-repeat-350ms.png`), on restored (private evidence: `~/.local/state/fusion360-for-omarchy/reviewer-preliminary-v2/grid-on-restored-350ms.png`) | **Pass in all eight captures:** unchecked corresponds to an absent grid; checked corresponds to a visible grid. The enabled grids have continuous fine lines and colored axes. The earlier inverted checkbox/canvas state is absent. |
| Origin workplanes after Create Sketch | 350ms capture (private evidence: `~/.local/state/fusion360-for-omarchy/v2-workplane-350ms.png`) | After 1 second (private evidence: `~/.local/state/fusion360-for-omarchy/reviewer-preliminary-v2/create-sketch-idle1.png`), after 5 seconds (private evidence: `~/.local/state/fusion360-for-omarchy/reviewer-preliminary-v2/create-sketch-idle5.png`) | **Pass in the inspected frames:** translucent orange planes and colored origin axes appear in the early capture and remain visible in the settled capture. |

The `350ms` labels describe the nominal idle wait used by the test. They are not
an end-to-end latency measurement. The reviewer's
timestamp record (private evidence: `~/.local/state/fusion360-for-omarchy/reviewer-preliminary-v2/grid-toggle-timestamps.json`)
places the recorded capture timestamps about 0.68–0.72 seconds after button
release. These images establish correct captured states; they do not establish
the first visible response time or exact native-platform frame pacing.

## Reference comparison and earlier failures

The following observations use the earlier private `reviewer-final-dx11`
captures. The grid and workplane failures are retained as the repair's original
evidence; their v2 retest results are above.

| Area | Reference and local observation | Result and limit |
| --- | --- | --- |
| Selected faces and edges | Official video at 48 seconds shows a blue selected face with continuous outlined boundaries. `selection-settled-after.png` shows the same convention on the test assembly; holes and neighboring plate edges remain distinct. | Static appearance consistent. A settled crop cannot establish selection latency. |
| Browser transparency | Official video at 78 seconds shows model geometry behind the Browser tree, with pale label backgrounds. The grid behind the Browser in `new-rectangle.png` is consistent with this transparent panel design. | Transparency alone is not a missing-background artifact. |
| Model detail and interface | Official frames at 78 and 283 seconds contain clear thin edges, holes, visible tool panels, ViewCube, and timeline. The local rectangle and assembly captures preserve those visible structures. | No gross corruption found in the inspected regions. Different geometry, scale, video compression, and available features prevent pixel identity checks. |
| Sketch detail | `new-rectangle.png` and `native-sketch-grid-axes-dimensions.png` show continuous grid lines, colored axes, 50.00/30.00 dimensions, constraint glyphs, and light blue closed-profile shading. Black rectangle edges and the blue circle agree with the documented geometry colors. | Static detail is legible. An exact September native sketch-grid reference was not obtained. |
| Grid state | `sketch-grid-disabled.png` has **Sketch Grid unchecked while the grid is visible**. `sketch-grid-restored.png` has **Sketch Grid checked while the grid is absent**. Autodesk defines this control as showing/hiding the grid. | **Historical failure before v2.** The later repeated v2 toggles pass the same state comparison. The earlier images cannot establish the full delay duration. |
| Workplanes | `workplanes-idle5-no-input.png` has an empty canvas; `workplanes-after-motion.png` shows the origin planes and plane-selection prompt. | Historical before/after discrepancy. V2 shows the planes in both early and settled captures. The frame names alone are not an independent timing measurement. |

## Evidence and retrieval limits

The private reference directory is
`~/.local/state/fusion360-for-omarchy/official-visual-references/`.
visual-reference-manifest.json (private evidence: `~/.local/state/fusion360-for-omarchy/official-visual-references/visual-reference-manifest.json`)
records URLs, frame times, dimensions, and SHA256 checksums, including both the
earlier local evidence and the v2 captures compared here. Reference images and
videos are not committed to the repository.

Direct Autodesk blog media downloads returned HTTP 403, including the
September `Finish-with-AutoConstrain.mp4` clip. Jina Reader successfully supplied
article screenshots, but the full-page capture contained an unplayed gray
video placeholder, not a sketch frame. It was not treated as visual proof.
The official YouTube upload provided the usable release-specific frames;
Autodesk Help supplied accessible supplementary images.

An exact-build native-grid comparison would still need a Windows or macOS
2705.1.25 reference at matching zoom and display settings. The official monthly
video and undated Help examples do not provide that comparison. Earlier
installation reviews and the later corrected audits are recorded separately.
These screenshots alone do not establish smooth operation or satisfy the
reviewer gate; use the fresh installed-v3 operational report for that verdict.
