# Documentation

Start with the [project overview](../README.md) and [agent installation guide](../INSTALL.md).
The root GE-Proton implementation is the default. The [standalone Wine subtree](../experimental/wine/README.md)
is unfinished research retained for future fallback development.

## Current guides

- [Installation, updates, backups and removal](install.md)
- [Autodesk sign-in](authentication.md)
- [Hyprland integration](hyprland.md)
- [Local filesystem access](filesystem.md)
- [7 October desktop fixes and verification limits](issues-2026-10-07.md)
- [Optional Omarchy widget](plugin.md)
- [Native Fusion MCP and agent configuration](native-automation.md)
- [Acceptance status](acceptance.md), [operational review](operational-review.md)
  and [widget review](plugin-review.md)

## Research and review history

- [Experiment record](experiments.md) and [initial review](review.md)
- [Corrected GE selection retest](ge-normal-retest.md)
- [Monitor integration](monitor-integration.md) and [focus integration](focus-integration.md)
- [Official visual reference comparison](visual-comparison.md)
- [Upstream source review](upstream-review.md)
- [Comparison of both approaches](../experimental/wine/docs/comparison.md)
- [Wine review-method audit](../experimental/wine/docs/reviewer-audit.md)

Reports record the implementation machine and the state at each test date.
Earlier rejections and intermediate candidates are history, not the current
acceptance decision. In particular, the corrected selection controls superseded
the blanket rejection of both runtimes.

This public repository consolidates the two original local projects into a
sanitized source snapshot. Old local commit IDs in reports identify the original
test records and are not commits in this public history. Private evidence paths
identify logs, screenshots and validation designs retained on the test machine;
those files and the account-bearing runtime are intentionally not distributed.
Public reports summarize the findings and scope without providing those private
artifacts. Reproduce the checks on your own installation before claiming it is
accepted.
