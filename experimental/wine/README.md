# Standalone Wine fallback — unfinished

**This is an unfinished alternative to the default GE-Proton implementation.**
It is retained inside [Fusion 360 for Omarchy](../../README.md) for future work
if the primary route stops working. **Do not use it for a normal installation.**

The main installer never selects this code. It has no automatic failover path,
and there is no complete fresh-install procedure for this experiment.

## What is preserved

- A dedicated Wine 11.17 launcher, browser handoff and runtime identity checks.
- Pinned runtime/compiler inputs and reproducible X11 transparency patch sources.
- A fallback native Fusion MCP client.
- 33 isolated launcher tests and the original investigations/review reports.

This route was operated with Fusion 2705.1.25 and hardware Radeon acceleration.
Grids, native modeling, corrected transparency and Normal face selection passed
the recorded checks, including selection after native edits and a cold restart.
Its earlier broad selection rejection was premature; see the
[critical audit](docs/reviewer-audit.md).

## What is unfinished

A complete independent operational review, fresh installation, update/rollback
packaging, Open With, automatic focus, and separate widget integration remain
unfinished. The initial sign-in handoff failed once before a successful cold
restart. This is not a second accepted installation product.

Do not run it concurrently with the GE implementation or point either runtime
at the other's prefix. Any future promotion needs a new review and preserved
user data. The locally tested prefix and account state are not distributed.

## Developer references

- [Comparison with the accepted GE route](docs/comparison.md)
- [Historical experiments](docs/experiments.md)
- [Operating an already-prepared experimental installation](docs/operation.md)
- [Native shader compiler preparation](docs/native-compiler.md)
- [Source build recipes and licenses](runtime-patches/README.md)
- [Validation and MCP client](validation/README.md)

The historical command is `fusion360-for-omarchy-wine`; its presence in this
tree does not install it. Run its isolated tests from this directory with
`python3 -B -m unittest discover -s tests -v`.
