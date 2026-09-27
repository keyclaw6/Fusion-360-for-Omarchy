# Upstream review — 26 September 2026

The brief's two starting pins exist. The source review supports trying this configuration; it does not establish Fusion usability or GPU acceleration on this machine.

## Verified inputs

| Input | Verified value |
| --- | --- |
| Fusion180 source | [`04ff7ad901e3e6aab34fd342cabcca2b31ea523a`](https://github.com/Kotya31415/Fusion180/commit/04ff7ad901e3e6aab34fd342cabcca2b31ea523a), committed 22 September 2026 |
| Fusion180 license | [MIT, Copyright (c) 2026 KOTARO](https://github.com/Kotya31415/Fusion180/blob/04ff7ad901e3e6aab34fd342cabcca2b31ea523a/LICENSE); retain the notice if copying substantial code |
| Runner | [GE-Proton11-7](https://github.com/GloriousEggroll/proton-ge-custom/releases/tag/GE-Proton11-7), published 16 September 2026 |
| Runner archive | [GE-Proton11-7-x86_64.tar.gz](https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton11-7/GE-Proton11-7-x86_64.tar.gz), 563,784,602 bytes |
| SHA-256 | `c5448b76a230384e2d7bc6beb5ccb97bafb7e2c3b6c527cb03a1a546bbcb00a0`, GitHub release asset digest |
| SHA-512 | `7db87e9787e20c35cbdac26018431d5794626b626e4067b050684e45a88cc2ca229d7d263519eafb2e168cde5bef57611065d159d3685aaec152ccb9abe3073f`, [maintainer checksum asset](https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton11-7/GE-Proton11-7-x86_64.sha512sum) |
| umu source | [1.4.4 / `cf3d1b107147480c447ffbfb3f789dc74335074c`](https://github.com/Open-Wine-Components/umu-launcher/commit/cf3d1b107147480c447ffbfb3f789dc74335074c) |
| Native umu package | [Arch multilib/umu-launcher 1.4.4-1](https://archlinux.org/packages/multilib/x86_64/umu-launcher/), also present in this machine's pacman database. The Omarchy repository separately offered older 1.1.3-1.1. |

## Runtime requirement and recorded fallback

GE-Proton11-7's [x86_64 tool manifest](https://github.com/GloriousEggroll/proton-ge-custom/blob/GE-Proton11-7/toolmanifest_x86_64.vdf) requires tool AppID **4183110**, Steam Linux Runtime **4.0**, with command `/proton %verb%`. Do not substitute sniper. [Valve's runtime documentation](https://github.com/ValveSoftware/steam-runtime#readme) maps Proton 11 and newer to runtime 4.

The implementation agent started native-package Steam and observed only its required sign-in screen, with no existing account session or userdata. An additional Steam account dependency obstructed the requested ordinary Fusion launcher. This is the brief's recorded integration blocker; the selected fallback is **umu 1.4.4 with the same pinned GE-Proton11-7**. The GE maintainer [explicitly supports umu for outside-Steam use](https://github.com/GloriousEggroll/proton-ge-custom/blob/GE-Proton11-7/README.md#ge-proton).

umu's [1.4.4 runtime mapping](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_runtime.py) includes AppID 4183110 and reads the selected runner's manifest. Its [launcher](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py) accepts an absolute `PROTONPATH` and `WINEPREFIX`; `UMU_RUNTIME_UPDATE=0` disables routine runtime updates after setup. Pin the absolute runner directory, not the `GE-Proton` token, which means automatic selection/download.

umu makes `pfx` a link to the requested prefix itself for a new prefix. Keep the identical resolved `WINEPREFIX` for installation, Fusion, and callbacks. Do not interchange a Steam compatibility-data parent and its `pfx` child. Source inspection is not proof that the download matches its checksums; installation records must supply that proof.

## Active-session callbacks

The ordinary Proton verb is `waitforexitandrun`: the [pinned Proton script](https://github.com/GloriousEggroll/proton-ge-custom/blob/GE-Proton11-7/proton) waits for the prefix's Wine server to exit before launching. A second ordinary launch is therefore unsuitable for authentication while Fusion runs.

umu 1.4.4 implements `UMU_CONTAINER_NSENTER=1`. On initial launch this enables a launcher service. On subsequent calls it looks for the exact bus name `com.steampowered.App` followed by MD5 of the resolved prefix pathname, then executes `proton runinprefix` through that runtime's `steam-runtime-launch-client`. **Set NSENTER on the initial launch too**; without it there is no service to re-enter.

The upstream re-entry implementation tries five times and then falls back to a cold launch. Authentication must fail closed if the existing session disappears. The package callback can therefore require the expected bus and a process in the expected prefix/runner, then call that exact launch client directly with the pinned Proton `runinprefix` command. This enters the running runtime, not direct-host Proton. No shell, no callback content in logs, and no fallback to another prefix. Turn off umu debug output: it logs its final argument tuple.

The runtime client exposes `--bus-name`, `--list`, `--directory`, and `--pass-env` on this machine. These are sufficient for guarded attachment. Actual callback and cloud operations still need live acceptance.

## Registry and browser integration

The old and newly installed prefixes register `Software\\Classes\\f3d_file\\shell\\open\\command` to the current build's `Fusion360.exe`. `fusion360` points to its `NLauncher.exe`. Identity Manager registers `adskidmgr` and `adsk.idmgr`. Read those registrations instead of selecting a directory-tree match. If Identity Manager has not registered yet, its executable can be located relative to the already registered Fusion build; do not choose an unrelated build.

[Wine's browser implementation](https://github.com/ValveSoftware/wine/blob/46b29104e3741fe23bf5e2547196a253aab88c89/programs/winebrowser/main.c) first tries `xdg-open` and supports the `HKCU\\Software\\Wine\\WineBrowser` `Browsers` override. The host browser must inherit the host desktop's environment, not Proton's library/graphics environment. The package's override helper validates an HTTP(S) URI and hands it to the systemd user manager as an argument array, with a static unit description and suppressed output. The steamrt4 image lacks `systemd-run`; from inside it, use `/run/host`'s dynamic loader and `systemd-run` to reach the host manager. This mechanism requires live verification before enabling the registry override.

## Fusion180 adaptations

Fusion180's [launcher](https://github.com/Kotya31415/Fusion180/blob/04ff7ad901e3e6aab34fd342cabcca2b31ea523a/launch-fusion.sh) and [installer](https://github.com/Kotya31415/Fusion180/blob/04ff7ad901e3e6aab34fd342cabcca2b31ea523a/installer.sh) directly call `proton run`, auto-select the highest runner name, and find the first application executable. Its desktop handlers put URI data into `bash -c`. Those behaviors are not retained.

The [window helper](https://github.com/Kotya31415/Fusion180/blob/04ff7ad901e3e6aab34fd342cabcca2b31ea523a/fusion-window-fix.py) unmaps large override-redirect dialogs with the title Fusion360. It does not scope by this installation's process. Do not enable it without a reproducible window problem and narrower matching.

The [OpenGL recommendation](https://github.com/Kotya31415/Fusion180/blob/04ff7ad901e3e6aab34fd342cabcca2b31ea523a/README.md) is an author's observation on KDE/Wayland and hybrid Intel/NVIDIA hardware. It does not validate Radeon 8060S or Hyprland. Reject inherited llvmpipe/lavapipe software-rendering overrides, select Fusion's own OpenGL Core option, and confirm Fusion's graphics diagnostics and real modeling behavior.

That paragraph records the initial experiment. Actual Omarchy testing later
reproduced a Wine drawable-selection defect after native feature editing under
OpenGL Core. The current candidate uses Fusion's DirectX 11 canvas through DXVK,
with Qt Quick's separate OpenGL composition retained. See
[the measured failure and fallback](progress.md) and [live review](review.md).

For completeness, Valve's [non-Steam compatibility contract](https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/main/docs/steam-compat-tool-interface.md#non-steam-games) confirms that non-Steam entries use the same waiting verb, derive their own compatibility directory, and require an appropriate working directory. No Steam shortcut implementation is included after the recorded fallback.
