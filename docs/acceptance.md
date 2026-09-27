# Acceptance — installed GE v3

Status on 27 September 2026: **independently accepted for the tested Design,
modeling, rendering, file and desktop workflows**. The reviewer operated the
installed application and accepted the final palette repair after repeated
switching, native panel input, monitor movement and a fresh ordinary cold
launch. This satisfies the user's application review gate for the scope below.
The optional widget also passed its separate live lifecycle review and is enabled.

Current candidate: Fusion 2705.1.25, pinned GE-Proton 11-7 through umu and Steam
Linux Runtime 4, DirectX 11/DXVK modeling with Qt OpenGL UI, physical Radeon
8060S, and the v3 overlay. See [installation](install.md) and the
[independent operational report](operational-review.md).

| Area | Evidence / current result |
| --- | --- |
| Hardware rendering | Application diagnostics, physical Radeon/RADV module mappings and per-process GPU engine work verified. |
| Visual completeness | Recent official September 2026 references compared; reviewer passed workplanes, axes, grid off/on, constraints, geometry and identified blue face selection before/after feature editing. |
| Native modeling | Reviewer passed constrained 50 × 30 mm sketch, extrusion, fillet and timeline edits. |
| Responsiveness | Reviewer operated the single part and a 64-occurrence assembly using native orbit, pan, wheel zoom and selection without persistent stale geometry or blocked input in those checks. |
| Cloud persistence | Native save, close and Data Panel reopen passed; saved version 2 remained complete and unmodified across cold launch. |
| Local persistence | Native F3D export and file-picker import passed with the same body, dimensions and features. |
| Input / dialogs | Clipboard, native file chooser, Browser input, settled context-menu Rename typing and tested modal cancellation passed. File-menu Escape and inconsistent Alt+F4 are recorded shortcut observations; outside-click menu dismissal, file commands and Omarchy Super+W close work. |
| Mixed-scale monitors | Independent reviewer passed individual maximized-window transfers and physical Super + left-button drags in both directions, with Browser input on DP-3. |
| Application switching | Independent reviewer passed four ordinary Alt+Tab returns, neutral-app coverage without stray palettes, and the former exact-main focus/Escape failure using the installed repair. |
| Cold startup / login | Two ordinary Apps-menu launches passed with cached authentication, cloud reopen and correct native post-edit selection; a third genuine cold launch with the final event hooks passed new-window discovery, settled rendering, cloud v2 reopen and palette input/visibility. |
| Native MCP | Four native tools discovered; direct read and read-only execution passed. Direct read also succeeded after the cold restarts, including the final new process, without reconfiguration. |
| Installation / recovery | Pinned sources, private prefix backup/recovery, integration upgrade/rollback and guarded removal verified. Latest scoped integration changes pass 37 focused tests; all 26 installed manifest entries match receipts. |
| Optional Omarchy widget | Installed and enabled after live click/keyboard, diagnostics, cancel/reopen, missing-launcher error, disable/re-enable, shell restart, removal and ordinary-launcher independence checks. See [plugin.md](plugin.md). |
| Independent final decision | Accepted for the documented application scope by the operational reviewer; see [operational-review.md](operational-review.md). |

The earlier blanket GE and standalone-Wine selection rejections were premature.
The corrected controls are in [ge-normal-retest.md](ge-normal-retest.md) and
[the two-route comparison](../experimental/wine/docs/comparison.md).
Earlier gray-canvas and stale OpenGL geometry findings remain historical evidence
in [experiments.md](experiments.md); they are not the current v3 result.

Limits: no exact-build Windows/macOS performance comparison, quantitative frame
pacing guarantee, heavy-assembly guarantee, suspend/resume test, or comprehensive
CAM/simulation/every-workspace coverage is claimed. Native modal dialogs and
document loading must finish before automation requests are sent. Suspend/resume
was deferred to avoid disrupting unrelated running work. Record any remaining
failures explicitly instead of turning untested items into passes.
