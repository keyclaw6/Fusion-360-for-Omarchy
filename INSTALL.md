# Install Fusion 360 for Omarchy

This guide is for the desktop user or an agent operating that user's Omarchy
machine. Use the **GE-Proton implementation at the repository root**. The
`experimental/wine/` directory is unfinished research, not an installation route.

## 1. Check the machine first

The reviewed system is x86-64 Omarchy 4.0.4-1, Hyprland 0.56.2, an AMD Radeon
8060S with Mesa/RADV 26.2.2, and Fusion 2705.1.25. See the full
[tested configuration](README.md#tested-configuration). Other combinations need
their own verification; a clean installation on a second machine has not yet
been demonstrated.

The 7 October 2026 desktop regression review also passed on Fusion 2705.1.30
and kernel 7.2.5-3-omarchy. That scope covers the reported window, local-export
and launch-placement issues; the broader modeling review above remains dated.

Before running the installer, check:

- A normal logged-in Omarchy desktop, Xwayland, and working user systemd/D-Bus.
- Hardware Vulkan and OpenGL support; software rendering is not acceptable.
- Python 3.12 or newer and Lua's `lua`/`luac` tools. The window integration needs
  Hyprland's Lua API and the regular file `~/.config/hypr/hyprland.lua`.
  Without that file the installer skips this integration; do not call that a
  complete installation. Do not convert somebody's desktop configuration blindly.
- **umu 1.4.4**, as pinned in `compatibility-lock.json`. The installer can add
  missing native packages through `omarchy pkg add`, but does not downgrade an
  incompatible installed umu. Check package availability before proceeding.
- If `~/.local/share/umu/steamrt4` already exists, it must match the locked
  **4.0.20260914.260627** runtime. Do not replace a conflicting shared runtime
  used by other applications to force this installation through.
- Generous free storage and time for downloads and a source build. The compiler
  SDK alone is about 2.2 GiB compressed and 6.3 GiB extracted; the runner, build,
  Fusion installation and recovery copies require additional gigabytes.

Inspect existing Fusion installations and preserve designs, unsynced work and
account state. Close Fusion and its identity/update helpers normally before
changing its installation. Keep backups private. Use the documented default
paths for a first installation; do not run the installer as root or with a
synthetic HOME. Symlinked configuration/state ancestry may be refused.

## 2. Download and install

```sh
git clone https://github.com/keyclaw6/Fusion-360-for-Omarchy.git
cd Fusion-360-for-Omarchy
python3 -B install.py
"$HOME/.local/bin/fusion360-for-omarchy" status --json
```

The installer obtains Fusion from Autodesk, GE-Proton from its upstream release,
and the pinned Steam runtime. It builds the project's two Wine compatibility
modules from pinned source in a compiler SDK, verifies their exact hashes, and
installs desktop commands and protocol handlers. It may add missing source-build
tools through Omarchy's package command. No compiled Fusion or Wine binaries are
distributed in this repository.

Read [installation and recovery](docs/install.md) for the ownership checks,
paths, build recipe, backups and rollback. A checksum/build mismatch is a stop
condition: investigate the changed input or toolchain, rather than changing the
expected digest just to accept the result.

The Autodesk installer may open Fusion or leave Identity Manager running before
configuration completes. Close that session normally, then resume with:

```sh
python3 -B install.py --no-packages
```

This reuses verified downloads and the installed application. If only a verified
idle runtime remains, the documented `fusion360-for-omarchy stop-idle-runtime`
command can clean it up; do not indiscriminately kill Wine processes.

After the installer adds its owned Hyprland block, reload the desktop
configuration and check for configuration errors as described in
[window integration](docs/hyprland.md). The installer does not reload it for you.

## 3. Sign in and verify the real application

Open **Fusion 360 for Omarchy** from the Apps menu. Complete Autodesk's normal
browser sign-in with your own account and entitlement. An agent should let the
user complete interactive authentication; never place passwords, tokens or
callback URLs in the repository. See [sign-in troubleshooting](docs/authentication.md).

Autodesk streams its current application payload: a pinned downloader does not
guarantee Fusion 2705.1.25. Record the installed version and review any different
build before accepting it. Confirm DirectX 11 hardware rendering and use
**Normal** selection display for the documented selection checks.

Before reporting success, test the actual UI:

1. Create a sketch and check grids, workplanes, geometry and dimensions.
2. Extrude, fillet and edit features; select an identified visible face and
   confirm its highlight after editing and reselection.
3. Orbit, pan and zoom a representative assembly; check for visible artifacts
   and noticeable stalls. A GPU name alone does not prove a smooth viewport.
4. Save and reopen a cloud design, export and reopen a local F3D, and confirm
   that the geometry and timeline survived.
5. Switch applications, use Browser/Comments panels and, where available, move
   Fusion between monitors. Close it normally and perform a true cold launch.

For an installation claimed to match this project's accepted scope, use the
[independent operational review](docs/operational-review.md) as the checklist
and have a separate reviewer inspect the result. Record failures and untested
areas. Do not infer UI acceptance from MCP success or a window appearing.

## 4. Optional integrations

- **Omarchy bar widget:** after application acceptance, follow
  [the widget guide](docs/plugin.md). Copy only `Main.qml` and `manifest.json`
  into a new plugin directory, validate it, wait for shell discovery, then
  enable it. Preserve any existing plugin instead of overwriting it blindly.
- **Agent access through MCP:** follow [native Fusion automation](docs/native-automation.md).
  Enable Fusion's local server in its preferences and use the exact displayed
  loopback address. The included Codex registration helper is optional. Finish
  modal dialogs and document loading before sending requests.

Fusion remains usable from its ordinary launcher without either optional
integration. Updates require a private backup and renewed application checks;
see [update and recovery](docs/install.md#update).
