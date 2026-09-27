# Installation and recovery

This repository packages the pinned GE-Proton/umu route used on this machine. It
is independent of `agent-dot-files`. Application acceptance is tracked in
[acceptance.md](acceptance.md); a successful installation command is not a claim
that every Fusion workflow works.

Run from this checkout, as the desktop user:

```sh
python3 install.py
fusion360-for-omarchy status --json
fusion360-for-omarchy launch
```

The installer checks native Arch packages (`umu-launcher`, `mesa-utils`, and
`xdg-utils`) and uses `omarchy pkg add` for missing packages. The umu version must
match `compatibility-lock.json`; this script does not downgrade system packages.
`--no-packages` checks existing packages without adding any.

GE-Proton and the official Autodesk downloader are checked against the SHA256
digests in the lock before use. Steam runtime 4 is downloaded from its immutable
versioned snapshot, checked against its locked SHA256, safely extracted and
verified with its own `pv-verify` mtree checker. An existing shared umu runtime
must match the recorded build and pass mtree verification; it is never replaced
to make this application install. No `latest` runner or runtime is selected.

The official downloader installs Fusion into a dedicated prefix. Autodesk's
streaming application payload is live: pinning the downloader does not freeze
Autodesk's server-side application build or entitlement requirements. A changed
application build must be exercised and reviewed before being accepted. A
checksum mismatch stops the command; inspect the upstream change and update the
reviewed lock explicitly instead of bypassing verification.

When `runner_overlay` is present in the reviewed compatibility lock, the selected
route requires the exact modules named by that overlay. Versions 2 and 3 use the pair
`files/lib/wine/x86_64-unix/winex11.so` and
`files/lib/wine/x86_64-unix/win32u.so`; version 1 remains supported for recovery
of the earlier single-module installation. Original and patched hashes, target
paths and required environment are recorded separately from the unchanged
official GE-Proton archive hash. Only those explicit file differences are
accepted when rechecking an existing runner. Any other changed archive member
stops installation. The compatibility lock keeps schema 1; the paired-module source
manifest and recovery receipt use schema 2.

The selected version 3 accepts exactly `WINE_X11_ARGB_SHAPE_INPUT=1`,
`WINE_X11_ARGB_CONSTANT_ALPHA=1`, `WINE_X11_VULKAN_PRESENT_WAIT=1` and
`QSG_RHI_BACKEND=opengl`. Historical version 2 requires `d3d11` for that last
value and remains readable for recovery. Version 3 reuses the same two module
hashes; its distinct identity prevents attachment to an older session with the
wrong Qt renderer. These four values
must agree between the lock, source manifest and launcher. Candidate acceptance
remains separate from this format support.

The overlay is built from the source recipe in `runtime-patches/` into the app
cache when no verified copy exists. The recipe downloads pinned source and an
official compiler SDK, so a first build needs additional disk space and time.
The durable installed recipe includes `build-overlay.py`, its SDK-side
`compile.sh`, the portable `test-constant-alpha.py`, all manifest-listed patches
and their license notices. Schema 2 also requires `test-present-wait.py`.
Installation checks completeness and patch hashes
before copying integration files, so rebuilding does not depend on the checkout.
Only the source-generation tools (`git`, `bubblewrap`, `patch`, `autoconf`,
`automake`, and `libtool`) come from native packages. An existing reviewed local
artifact can be supplied without rebuilding:

```sh
python3 install.py --overlay-dir /absolute/path/to/reviewed-pair
```

That directory must contain both `winex11.so` and `win32u.so`. Version 1 alone
uses `--overlay-file /absolute/path/to/reviewed/winex11.so`. Each supplied or
cached module must match its locked hash; a mismatch is preserved for inspection
and stops before any production module is changed. Binaries and build products stay
outside Git. The production runner remains at its ordinary fixed path; an
experimental runner is never selected automatically. Before promotion, the
installer saves every original module and the exact previous installed
compatibility lock under private `STATE/runner-recovery/`. The complete recovery
set and receipt are durable before promotion. It deploys compatible launcher
support and the required-overlay lock before replacing either module. Each
replacement is atomic and its containing directory is synced. There is no
two-file atomic rename: interruption can leave a mixed pair, which the launcher
rejects under the new lock. Rerunning the same installation verifies its receipt
and completes the pair; rollback is also supported. Both verified modules under
the matching lock are coherent even if the final receipt phase write was
interrupted.

By default, the installation uses:

| Purpose | Location |
| --- | --- |
| Dedicated prefix | `~/.local/share/fusion360-for-omarchy/prefix` |
| Pinned GE-Proton and installed launcher support | `~/.local/share/fusion360-for-omarchy/` |
| Shared umu Steam runtime | `~/.local/share/umu/steamrt4/` |
| Verified downloads | `~/.cache/fusion360-for-omarchy/` |
| Commands | `~/.local/bin/fusion360-for-omarchy*` |
| Desktop entries | `~/.local/share/applications/fusion360-for-omarchy*.desktop` |
| Private ownership and previous-handler record | `~/.local/share/fusion360-for-omarchy/install-manifest.json` |

Installed launchers do not depend on this checkout or the optional Omarchy
plugin. `--integration-only` copies and registers the launchers without
downloading or changing a prefix. Use this after wrapper source updates.
`--no-register` leaves protocol defaults unchanged. Installation refuses to
overwrite unrelated or manually modified integration files.
Integration-only deployment cannot activate an absent or mismatched required
overlay, or remove an active overlay requirement. A full install refuses to
change the production runner while any process still uses the prefix, including
an experimental runner or a live worker whose process leader has exited.
Maintenance checks the prefix independently of overlay flags, so a session with
older or missing flags still blocks replacement. The overlay environment is
applied before the initial Identity Manager startup; mixed or older sessions
require a cold restart.

Only `adskidmgr` and `fusion360` URL schemes are registered with `xdg-mime`.
Their previous defaults are preserved in a private manifest. URI arguments go
directly to helper programs, without shell interpolation. The WineBrowser
override uses the installed browser helper through the same runtime and prefix.
Desktop entries use a fixed, unquoted `/usr/bin/python3` executable followed by
the quoted helper path. This accommodates spaces and avoids this machine's
`xdg-mime` parser treating quotes as part of an executable name. Registration
checks the effective default, including when an older Fusion handler exists.
The launcher accepts local paths and local `file://` URIs supplied by desktop
Open With. Remote file authorities, query strings and fragments are rejected;
local paths still pass through the prefix's verified C:/Z: mapping. No generic
STEP or archive file associations are taken over.
The only seeded Fusion preference is `VirtualDeviceDx11`; other options and
TLS validation settings are preserved. An original preferences file is retained
beside the edited file. Close Fusion before a full install or prefix maintenance.
If the Autodesk installer opens Fusion or leaves Identity Manager running,
close that session before completing configuration. The script stops rather
than editing a busy prefix; rerun `python3 install.py --no-packages` after the
session closes. It reuses the installed application and verified downloads.
If maintenance reports that only the runtime container remains after Fusion and
Identity Manager exit, use `fusion360-for-omarchy stop-idle-runtime` and retry.
That command verifies the dedicated runtime and refuses to stop active or
unrecognized application/update work; maintenance does not kill background work
automatically.

After the runtime service exits, this explicit command can stop verified orphaned
Wine services using process handles that cannot be redirected by PID reuse. It
also checks live threads when a process leader has exited. A grace period precedes
forced completion of only a stuck stock device service or a registered Autodesk
analytics process with an already-dead leader. Other unrecognized or changing
work prevents cleanup.
Metadata reads retry another worker if the selected worker exits. Each individual
signal is preceded by a fresh application, identity, process-image, bus and
Wine-server check; new work stops the remaining cleanup.

The selected overlay configuration also installs the Fusion window rules and
palette monitor-following hook described in [hyprland.md](hyprland.md). Its helper owns only the marked
block in `~/.config/hypr/hyprland.lua`, preserves unrelated settings and keeps its
recovery record outside the repository. The installer does not invoke a desktop
reload command.

## Back up and recover

```sh
fusion360-for-omarchy-maintenance backup
fusion360-for-omarchy-maintenance restore /absolute/path/to/snapshot-directory
```

Backups default to `STATE/backups/`, mode `0700`. They contain account/session
state and possibly unsynced designs, and must stay private and outside Git.
`backup --backup-dir /private/path` selects another location. GNU `cp -a
--reflink=auto` uses copy-on-write where supported and copies otherwise; Wine
directory symlinks are retained as links rather than followed. Designs located
outside the prefix need their ordinary separate backup.

Restore stages a copy, verifies the snapshot's runtime identity, then swaps the
prefix. The prefix that existed immediately before recovery is moved into a
new private `before-restore-*` snapshot. Recovery never deletes that state.
Snapshots are local state copies, not a promise that an old application build
will keep working with future Autodesk services.

To undo the runtime overlay, close every Fusion session, including any
experimental same-prefix session, then run:

```sh
fusion360-for-omarchy-maintenance rollback-overlay
```

This verifies all recovery data and current module hashes before restoring
anything. It restores every original module first and its exact prior installed
compatibility lock last. An interruption between module replacements therefore
retains a lock that rejects the mixed pair. It also updates the owned-lock hash so subsequent
installation or removal remains consistent. Prefix data, desktop integration
and recovery files remain. This returns to the original renderer limitations;
it is a recovery operation, not a declaration that the original rendering is
acceptable. A repeated rollback safely completes an interrupted one. To reapply
the reviewed overlay later, run a full install from this checkout.

Migration between overlay versions is explicit; a full install refuses to
replace an active overlay with a different configuration. With Fusion and its helpers closed, run the
new checkout's recovery command, then the new full installer:

```sh
python3 maintenance.py rollback-overlay
python3 install.py --overlay-dir /absolute/path/to/reviewed-pair
```

The first command understands the original deployed version 1/schema 1 and
version 2/schema 2 receipts without requiring today's source manifest to
describe the old configuration. Before migration, copy the existing
`STATE/runner-overlay.json` into a private recovery directory; preserve its
post-rollback form there too. The subsequent installer creates a new receipt
at that fixed path. Keep the old recovery directory intact. The second command
reuses the prefix. If no reviewed pair is supplied, omit `--overlay-dir` to
use the verified cache or pinned build recipe. After an interrupted rollback,
rerun `rollback-overlay` before attempting migration.

Prefix snapshots record overlay identity for diagnostics. Their restore check
uses the exact base GE-Proton archive and Steam runtime identities. The runtime
overlay does not migrate prefix data, so snapshots from either side remain
restorable under the same base runtime.

## Update

```sh
fusion360-for-omarchy-maintenance update
```

This first backs up the closed prefix and prints the recovery path, then reruns
the locked official downloader in the same prefix. It reapplies the browser and
renderer configuration and records the resulting build in private
`STATE/last-update.json` as not yet reviewed. It does not advance GE-Proton, umu
or the Steam runtime. After any update, exercise modeling, rendering, local
export, cloud save/reopen and cold launch. If it fails, close the session and
restore the printed snapshot. Fusion can also update through its own service;
make a snapshot before accepting an application update in the UI.

## Remove the integration

```sh
fusion360-for-omarchy-maintenance uninstall
```

This removes only manifest-owned launcher/support files, command symlinks and
desktop entries. It restores a previous protocol default only when this
installation is still the current default. If the user chose another handler
after installation, that choice remains. Because `xdg-mime` has no unset
operation, cleanup removes only this application's exact desktop IDs from the
relevant user MIME keys and preserves other entries. Edited owned files are
retained and reported for inspection.
The unchanged owned Hyprland focus block is removed through its separate
ownership record; unrelated configuration edits are preserved.

The prefix, designs, backups, downloaded files, pinned runner and shared umu
runtime remain. Existing older Fusion installations and system packages remain.
There is intentionally no automatic prefix purge. Reinstalling from the checkout
can reuse a preserved prefix.

## Isolated checks

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Installer tests use temporary directories and synthetic prefixes, including the
real `xdg-mime` utility with isolated XDG directories. They cover checksum
failure, archive traversal, runtime bootstrap, preference preservation,
ownership conflicts, install/reinstall/removal, private backups and recovery
after a simulated failed update. Version 2 fixtures also exercise interruption
before each module replacement, interruption before the final receipt or restored
lock, repeatable recovery, full-pair preflight, schema 1 receipt migration and
worker detection after a process leader exits. They do not certify a real
Autodesk update, account login or application performance.

On the implementation machine, the actual pinned Steam runtime archive was also
downloaded and hash-verified, then installed into temporary XDG directories with
the production installer functions. Safe extraction, `pv-verify`, umu entry
point creation and subsequent existing-runtime verification all passed. This
test did not change the machine's active shared runtime.

The actual original GE-Proton archive and initial alpha X11 candidate also
passed an isolated promotion/rollback round trip. The patched module hash was
`456ba82329fd8fe5eddf0d02acf4ee3dd3a50b71c991517fbdd4ebe863f56e17`;
rollback restored
`5acbf619a5d13b4d38cde3adba9724e5de5427a117caf0e2336864e20281f080`.
Every archived file was rechecked after promotion with only that exact overlay
exception, then rechecked against the untouched archive after rollback. An
injected interruption between module and lock restoration was detected by the
launcher; repeating rollback completed it. Lock ownership, a design sentinel,
the absolute `pfx` symlink and recovery data were preserved, and owned-support
removal passed. All temporary test state was deleted. This validates the
transaction machinery with that candidate, not the GUI acceptance of a later
candidate.

The version 2 recipe pair also passed promotion and rollback in a separate
temporary state directory: `winex11.so` hash
`6b5f680717f8e1db59039eeb50a953ac7703d6a7e88cd1e891c345e372020f1f`
and `win32u.so` hash
`201ef0e0f4d48dfc093a16ffdd221c0ef37427e35ec59238756e0dc54c134d38`.
The test verified the official archive digest, read both original modules from
that archive, copied the durable integration, activated the pair and exercised
launcher hash validation. Rollback restored both original hashes, the exact
prior lock and its owned-file hash. Repeat rollback and owned-support removal
passed while preserving a design sentinel and absolute `pfx` symlink. Temporary
state was deleted and the archive digest was unchanged. This checked the actual
module transaction; it did not repeat full archive extraction or exercise Fusion.

All maintenance commands accept `--state`, `--cache`, `--data-home`,
`--config-home` and `--bin-home` before the subcommand. Installer commands accept
the same options. Existing manifest paths are reused unless explicitly
overridden; changing an established installation's paths requires a separate
installation. `FUSION360_STATE` also selects a dedicated state directory.
