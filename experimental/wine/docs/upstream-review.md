# Standalone Wine upstream review

Research date: 26 September 2026. This records the inputs and limits of Test 2 before its independent acceptance review. It does not declare Fusion working.

## Route and pinned artifact

The selected archive contains a complete, Fusion-patched Wine 11.17 installation intended to run directly on the Linux host. It replaces the Proton/umu/Steam-container route used by Test 1. The project's current installer recommends this standalone `--fusion-wine` route. It is a community runtime, not an Autodesk-supported Linux build. [Pinned project source](https://codeberg.org/Lolig4/Autodesk-Fusion-360-on-Linux/src/commit/7da442d6af5ac2619e5151475d2be54efe6170bc), [upstream setup script](https://codeberg.org/Lolig4/Autodesk-Fusion-360-on-Linux/src/commit/7da442d6af5ac2619e5151475d2be54efe6170bc/files/setup/autodesk_fusion_installer_x86-64.sh).

| Item | Verified value |
| --- | --- |
| Release | [Lolig4 Version_1](https://github.com/Lolig4/Autodesk-Fusion-360-for-Linux/releases/tag/Version_1) |
| Archive | [fusion-wine-build.tar.gz](https://github.com/Lolig4/Autodesk-Fusion-360-for-Linux/releases/download/Version_1/fusion-wine-build.tar.gz) |
| Size | 568,123,659 bytes |
| SHA-256 | `9ef47e25de30d52fb110b9f257d128755904ecfabda4a0c2ce43416e075a4479` |
| Asset created / updated | 2026-09-16 17:24:48 / 17:28:39 UTC |
| Embedded Wine label | `wine-11.17` |
| Embedded compiler label | GCC 15.2.1 20260123, Red Hat 15.2.1-7 |
| Source review commit | `7da442d6af5ac2619e5151475d2be54efe6170bc`, 22 September 2026 |
| Official Wine base | `wine-11.17`, commit `36b6a2cf679fb395f668a917b76537190e212d9c` |

The GitHub asset API publishes the checksum above; the downloaded archive was independently hashed to the same value. The release publication timestamp is 15 September, while the archive was uploaded on 16 September. GitHub now serves releases and a README redirect; its `Version_1` tag points to README-only commit `8af74f6a31b2ab5dcd4ae4d359830474666069b3`, not a build-source commit. [Release metadata API](https://api.github.com/repos/Lolig4/Autodesk-Fusion-360-for-Linux/releases/tags/Version_1).

The archive has 4,226 members under `fusion-wine-build/`: executables, `x86_64-unix` modules, `x86_64-windows` and `i386-windows` modules, headers, and shared data. Its embedded source path is `/root/.local/share/Autodesk-Unofficial/fusion-wine-source`. Static inspection found no full-source commit stamp, build manifest, or binary-source attestation. No program from this archive was executed during this research.

Selected independently measured file hashes:

| Archive path under `fusion-wine-build/` | SHA-256 |
| --- | --- |
| `bin/wine` | `a664cab48d74a1fddef0d5a8ed48ffa5c24ee62baf1cc57a290211bc5f6e8544` |
| `lib/wine/x86_64-unix/ntdll.so` | `12f7f863badddb2be71e7817428f97d3d75a30c0f6902876e9af80af42e8f270` |
| `lib/wine/x86_64-unix/win32u.so` | `79923250de21f0f7d5e6e98e95fc8ecbaf5381e79920f9873e08b0f2f57c8b9d` |
| `lib/wine/x86_64-unix/winex11.so` | `05d4cc19270f43e2cf88b8fd76da07523eef63d2f428c5fe535bab371c5c1d7a` |
| `lib/wine/x86_64-unix/winevulkan.so` | `7a8cc268a9ecf6b4d76fc25697a6c7d66f17c09f23e2dd2a43f503115f01141a` |

The official Wine tag is dated 4 September 2026. The tag contains a signature, but its signing key was not independently verified here. [Official source mirror at wine-11.17](https://github.com/wine-mirror/wine/tree/wine-11.17), [WineHQ source archive](https://dl.winehq.org/wine/source/11.x/wine-11.17.tar.xz).

## Source correspondence and all ten patches

The pinned installer selects Wine 11.17 and applies the following patches, in this order. Paths are relative to `files/setup/data/` in the [pinned source tree](https://codeberg.org/Lolig4/Autodesk-Fusion-360-on-Linux/src/commit/7da442d6af5ac2619e5151475d2be54efe6170bc/files/setup/data).

| Order | Patch path | SHA-256 |
| --- | --- | --- |
| 1 | `inventor-patches/regloadappkey-binary-hive.patch` | `9211e6070062e0a99033a2014eecc976354768a7b522e1d3c270c5d11d73fc42` |
| 2 | `inventor-patches/msi-generate-transform.patch` | `c96b655d7de8eb84f6918350af661d748a01f678df5b4a653af05fe824fecd38` |
| 3 | `inventor-patches/wintrust-wtd-choice-blob.patch` | `b7aa1cae461e423f4dc083192a03ed9e21a6c80054b1268e5b26a8d97092f72d` |
| 4 | `inventor-patches/ole32-revokedragdrop-release-order.patch` | `1f555da43897c0af6dd035f48be97f169ff5a7eb8825969cf33b3346a4f8556d` |
| 5 | `inventor-patches/services-session0-scm1053.patch` | `206844d8d45369e0b10f1ec43a528628facb30c602b09868103ef378d138ddbc` |
| 6 | `fusion-patches/winex11-owned-tool-windows.patch` | `906aa4406dd6cba74b5ad29f0bfa13fad217e387d76843b7d44eaee2931c4e5a` |
| 7 | `fusion-patches/dwrite-glyph-cache-rendering-mode.patch` | `61b99645b04e3af56ef6b989af784e3d53b5362cad641d82204a6381b801adba` |
| 8 | `inventor-patches/ntdll-mapuserphysicalpagesscatter.patch` | `4dee475521bdcbeab5a755cb9c9233464e61f4ac4fb1e7a7fc162f37845a12e6` |
| 9 | `fusion-patches/win32u-vulkan-wait-for-present.patch` | `1d4aadbf6d9e1444e6548b1b3f1ea07ca5cd8859ba12f545301c5046f0c664ba` |
| 10 | `fusion-patches/symcrypt-rsa-exponent1.patch` | `dd1c26f843204c40dc56842966bb9c8185da5963b59eec857e84a37ce2835284` |

These ten files are byte-identical between the last source commit before the asset upload, `579bbf8be1c1ed8dce2fd96f7b8cd3b5e3bc6c1c`, and the reviewed commit. Wine 11.17 had already been selected in commit `607f044409a727509fbd1250238e8d3a06b824ca` on 8 September. The version, build timestamps, source paths, debug symbols, and inspected present-wait machine code are consistent with this recipe. They do not prove that every byte of the published binary came from exactly this source tree.

The SymCrypt patch addresses a documented Wine 11.11+ change: Fusion imports a 512-bit RSA private key whose public exponent is 1. According to the patch, merely accepting the import leaves the derived private exponent wrong and prevents Fusion's 3D subsystem from initializing. It explicitly sets the private exponent to 1 before deriving the CRT exponents. This is a crypto correctness change. It does not establish that Test 1's gray-canvas failure on a different Wine base had the same cause. [Exact SymCrypt patch](https://codeberg.org/Lolig4/Autodesk-Fusion-360-on-Linux/src/commit/7da442d6af5ac2619e5151475d2be54efe6170bc/files/setup/data/fusion-patches/symcrypt-rsa-exponent1.patch).

The upstream Vulkan patch targets the same presentation ordering problem observed in Test 1: an offscreen Vulkan source may be copied into the visible parent before its queued presentation completes. It uses the application's present IDs when provided, or enables supported present-id/present-wait features and supplies IDs. It waits at most one second before the offscreen client copy. Static disassembly of this archive confirms the 1,000,000,000 ns wait at that call site. The module also contains the expected `needs_present_wait`, `find_present_id`, and present-ID variable debug symbols. [Exact presentation patch](https://codeberg.org/Lolig4/Autodesk-Fusion-360-on-Linux/src/commit/7da442d6af5ac2619e5151475d2be54efe6170bc/files/setup/data/fusion-patches/win32u-vulkan-wait-for-present.patch).

This is not the same implementation as Test 1's audited GE overlay: the upstream patch does not separately record actual enabled feature booleans, does not support present-ID2, and ignores the wait result. Its vanilla-Wine presentation code also lacks GE's mixed managed/host swapchain path. Those are review limits to retain during testing, not reasons to transplant a GE binary into Wine 11.17.

The owned-tool-window patch is the same source patch used for Test 1 palettes. The standalone recipe does **not** contain Test 1's ARGB bounding/input-shape patch or its GDI constant-alpha patch. Retest palettes and modal dimming on this complete runtime before considering a source port. The remaining patches cover text glyph caching, binary registry hives, MSI transforms, WinTrust blobs, drag/drop release order, service startup, and MapUserPhysicalPagesScatter. [Owned-tool-window patch](https://codeberg.org/Lolig4/Autodesk-Fusion-360-on-Linux/src/commit/7da442d6af5ac2619e5151475d2be54efe6170bc/files/setup/data/fusion-patches/winex11-owned-tool-windows.patch).

## Host dependencies and graphics

All 36 Unix shared modules were inspected statically. The highest required GLIBC symbol version is 2.38; this machine reports glibc 2.44. Core X11, GL, Vulkan, GnuTLS, and Wayland libraries are present. The archive's X11 module dynamically uses GL, Xcomposite, Xcursor, Xfixes, Xi, Xinerama, Xrandr, Xrender, Xxf86vm, Vulkan, and xkbregistry; those libraries are available here.

Missing dependencies found during this review were `libgphoto2.so.6`, `libgphoto2_port.so.12`, and `libsane.so.1`, belonging to optional camera/scanner modules, plus the optional dynamically loaded `libodbc.so.2`. These findings do not by themselves establish a missing dependency for Fusion's normal graphics/login path. No packages were installed for this review.

Begin on XWayland so the desktop backend does not change at the same time as the runtime. The Radeon 8060S/RADV hardware must remain the renderer. Acceptance needs actual GPU evidence, not just a requested setting; llvmpipe/lavapipe or other software rendering cannot satisfy this experiment.

Standalone Wine does not automatically install native DXVK into an existing prefix. For D3D11, use a matching, pinned pair of `d3d11.dll` and `dxgi.dll` with native overrides. The first comparison can retain the already installed pair in the copied prefix to avoid changing another major component simultaneously. Upstream's installer also installs DXVK/VKD3D, .NET 4.8, GDI+/fonts, winhttp, a native d3dcompiler_47, and WebView2, then applies registry settings. That whole installer should not be run over the preserved working account prefix. [DXVK's primary installation guidance](https://github.com/doitsujin/dxvk), [pinned Fusion setup script](https://codeberg.org/Lolig4/Autodesk-Fusion-360-on-Linux/src/commit/7da442d6af5ac2619e5151475d2be54efe6170bc/files/setup/autodesk_fusion_installer_x86-64.sh).

The independently current DXVK release found during research was 3.1.1, published 15 September 2026; it is a separate candidate, not an implicit dependency upgrade for Test 2. Native Fusion canvas selection and the Qt UI backend must be evaluated separately. [DXVK 3.1.1](https://github.com/doitsujin/dxvk/releases/tag/v3.1.1).

## Isolation, profile identity, and authentication

Use a complete copy or reflink of Test 1's closed, quiescent prefix in the separate Test 2 state directory. Standalone Wine may migrate that copy during wineboot. Never run this Wine against Test 1's only signed-in prefix, or copy the migrated prefix back over it. Use the complete standalone runtime tree and its matching `wine` and `wineserver`; do not mix GE Unix modules into it.

Wine 11.17 derives its Windows username from the Unix `USER` environment variable, falling back to the Unix account when absent. For the copied Proton prefix, set **`USER=steamuser` only in the Wine child environment** while keeping the host user’s real `HOME`. This preserves the existing `C:\users\steamuser` profile location without changing the host account. Set the exact Test 2 `WINEPREFIX`, and use absolute paths to its Wine and wineserver. [Wine 11.17 `set_home_dir()`](https://github.com/wine-mirror/wine/blob/wine-11.17/dlls/ntdll/unix/loader.c#L339).

Do not inherit Proton/Steam/umu container variables or experimental Wine/Qt flags. Choose each intentional setting explicitly. Cached authentication may survive the isolated copy, but a normal browser refresh may still be required.

Direct host WineBrowser can launch a validated host browser wrapper without the pressure-vessel library-loader and user-bus bridge needed in Test 1. Autodesk's callback still has to enter `AdskIdentityManager.exe` in the exact active Test 2 prefix through the matching Wine runtime. The existing IDM startup arguments are `--process_name Autodesk.IDSDK.DefaultProcess-v2 --server_name Autodesk.IDSDK.DefaultServer-v2`.

Do not copy upstream's callback opener verbatim: the reviewed setup writes the complete callback URI into `/tmp/adskidmgr-opener.log`, and also writes callback Wine output to a temporary log. Use strict URI validation, no credential-bearing output, and an exact active-prefix guard. Any MIME handler selection must be deliberate and reversible; merely inspecting or launching Test 2 should not silently replace Test 1's authentication association. [Callback installer implementation](https://codeberg.org/Lolig4/Autodesk-Fusion-360-on-Linux/src/commit/7da442d6af5ac2619e5151475d2be54efe6170bc/files/setup/autodesk_fusion_installer_x86-64.sh).

## Known reports to test immediately

| Upstream report | Relevant evidence and Test 2 implication |
| --- | --- |
| [#8: No blue highlight while selecting faces](https://codeberg.org/Lolig4/Autodesk-Fusion-360-on-Linux/issues/8) | Reporter used GE-Proton with Intel graphics and Hyprland; the face was selected without a visible blue highlight. The reporter says Fusion's normal **Selection Display Style = Simple** setting fixes it. Maintainer could not reproduce and requested a retest after the September patches; the issue remains open. This is a specific pending test, not proof of the cause or a verified fix for this machine. |
| [#15: Cursor click always forced on fusion](https://codeberg.org/Lolig4/Autodesk-Fusion-360-on-Linux/issues/15) | Opened 25 September; reports Fusion receiving clicks intended for other windows. Unresolved when reviewed. Test focus and switching to another application. |
| [#12: Text absent from popup windows](https://codeberg.org/Lolig4/Autodesk-Fusion-360-on-Linux/issues/12) | Unresolved secondary-window text report. Test dialogs and menus rather than accepting the main canvas alone. |

Test the operation that rejected Test 1 first: face highlighting after editing an extrusion, then fillet and subsequent selection. Continue with workplanes, sketch-grid toggles, document switching, save/edit/reopen, transparent palettes, modal dialogs, ordinary quit/relaunch, and GPU-backed interaction. Imported models or one successful scripted construction do not replace the independent native-operation review.

## Rebuilding this route if needed

The reproducible input set is the official Wine commit above plus the ten hash-pinned patch files in the recorded order. A future rebuild should fetch the official `wine-11.17` tag and verify that `git rev-parse HEAD` equals `36b6a2cf679fb395f668a917b76537190e212d9c`; verify every patch hash before applying it with `patch -p1 -F0`. The WineHQ tarball is another official source, but this review did not establish its independent archive checksum.

The published configuration is a complete Wine build, not a two-module overlay:

```sh
./configure --prefix="$test2_runner_dir" \
  CC="ccache gcc" \
  i386_CC="ccache i686-w64-mingw32-gcc" \
  x86_64_CC="ccache x86_64-w64-mingw32-gcc" \
  --enable-archs=i386,x86_64 --disable-tests
make -j"$test2_build_jobs"
make install
```

Use a new private source/build/install directory. Dependencies include GNU make/gcc, both i686 and x86_64 MinGW C/C++ toolchains, bison/flex, and the Wine development headers reported by configure, including graphics, font, and crypto dependencies. Capture the configure feature report because missing optional development libraries can silently omit modules. Do not run the upstream all-in-one installer just to compile; it also installs global packages, fetches moving downloads, and modifies desktop and MIME integration.

An Arch-hosted rebuild will receive its own artifact hash. No claim is made that it will reproduce the Fedora-compiler archive byte for byte.

Research used the agent-reach skill's GitHub CLI and webpage-reading routes, pinned source reads, archive hashing, and static ELF inspection. No Wine process, GUI operation, package installation, or prefix mutation was part of this source review. Runtime validation and final acceptance are recorded separately.
