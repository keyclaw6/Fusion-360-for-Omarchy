# Contributing

The root project is the GE-Proton implementation. Keep its installer independent
of `experimental/wine/`, which preserves unfinished standalone Wine research.
Do not promote that experiment or change runtime defaults without new installation
and independent operational evidence.

## Source checks

Run the two test suites in separate processes and working directories:

```sh
# Repository root
python3 -B -m unittest discover -s tests -v

# Standalone Wine subtree
(cd experimental/wine && python3 -B -m unittest discover -s tests -v)
```

Use Python 3.12 or newer. Install Lua, xdg-utils and GLib desktop utilities to
exercise the real Lua and isolated desktop-registration checks; tests that need
missing utilities may be skipped. Record skips explicitly. These tests use
temporary state and synthetic prefixes; they do not accept a live Fusion build.
Source-level sanitizer checks are documented with each runtime build recipe.

For widget changes, also run the validators in [the widget guide](docs/plugin.md).
Changes affecting rendering, launch, authentication, file handling or desktop
behavior require the relevant native GUI checks and an independent review.
Explain the exact tested versions and scope; do not claim native performance
parity without measurements. See [acceptance](docs/acceptance.md).

## Keep the public tree portable

- Preserve users' existing data and unrelated configuration. Keep tests isolated.
- Keep prefixes, runtime binaries, account/session state, designs, private logs
  and screenshots outside Git. Share sanitized diagnostics, not authentication
  callbacks or a whole Wine prefix.
- Pin upstream inputs, keep source recipes reproducible, and retain license
  notices. Never change an expected hash merely to suppress a mismatch.
- Use portable examples rather than personal home directories or account names.
- Explain behavior changes and their validation in contributions. Historical
  experiment reports should retain corrections and the limits of their evidence.

The integration code uses the root MIT license. Upstream Wine code, patches and
brand marks retain the terms described in [third-party notices](THIRD_PARTY_NOTICES.md).
