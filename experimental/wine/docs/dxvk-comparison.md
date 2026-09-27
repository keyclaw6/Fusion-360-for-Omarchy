# Preserved DXVK versus official 3.1.1

Read-only comparison on 26 September 2026. The official alternative was downloaded and verified privately; it was not installed or run. There is no confirmed face-highlighting repair in this version comparison, so the prepared pair is not selected for another runtime test.

## Current pair

The Test 2 `system32/d3d11.dll` and `system32/dxgi.dll` are regular x64 files and match the original GE-Proton11-7 DXVK pair byte for byte. GE pins DXVK commit `601930949d111edbbcf9dd463948426d9f8f6ddd`; the embedded version string identifies the `v3.1-19-g601930949d111ed` development build. The PE Windows FileVersion values are compatibility metadata and should not be read as the DXVK version. [Pinned GE source tree](https://github.com/GloriousEggroll/proton-ge-custom/tree/c191f35dcebbeccfacd3b4c6f6eea026e588c1c2), [DXVK source commit](https://github.com/doitsujin/dxvk/commit/601930949d111edbbcf9dd463948426d9f8f6ddd).

| Current x64 file | Size | SHA-256 |
| --- | ---: | --- |
| `d3d11.dll` | 6,692,864 bytes | `c4cc77df68bd00c50dd8d6f47190555273cf1098284de4e592d7920919e0d0ad` |
| `dxgi.dll` | 4,857,856 bytes | `a32191d1292ee388d7e0c3b8e43716f944971c7b49ce77f213be2cf4f6432756` |

GE's preparation script applies six downstream patches to that DXVK commit:

1. `layered-overlay-dxvk.patch`: optional non-opaque composite alpha when `WINE_LAYERED_OVERLAY_ALPHA` is set.
2. `dxvk-preserve-swapchain-on-acquire-backpressure.patch`: preserves the swapchain after `VK_NOT_READY`/`VK_TIMEOUT`, skips that presentation attempt, and keeps the acquisition fence state by reference. This behavior is active without an application option and was written for Wine's managed child-surface path.
3. `dxgi-defer-initial-fullscreen-for-probe-swapchains.patch`: an opt-in fullscreen deferral enabled for Lineage II.
4. `dxgi-follow-d3d12-fullscreen-client-resizes.patch`: guarded handling of explicit D3D12 fullscreen client resizes; it excludes D3D11.
5. `dxgi-keep-fullscreen-on-focus-loss.patch`: an opt-in policy enabled for Final Fantasy XIV.
6. `black-desert-keep-fullscreen-on-focus-loss.patch`: enables that policy for Black Desert.

These make the GE binary different from an unmodified upstream release even though its upstream shader/rendering base is effectively current. There is no evidence yet that these patches cause Fusion's missing face highlight. The backpressure patch is the most relevant presentation difference, but no triggering `VK_NOT_READY` or `VK_TIMEOUT` was established in this comparison. [Exact pinned GE preparation script](https://github.com/GloriousEggroll/proton-ge-custom/blob/c191f35dcebbeccfacd3b4c6f6eea026e588c1c2/patches/protonprep-valve-staging.sh), [downstream patch directory](https://github.com/GloriousEggroll/proton-ge-custom/tree/c191f35dcebbeccfacd3b4c6f6eea026e588c1c2/patches/dxvk).

## Official alternative and exact source difference

Official DXVK 3.1.1 was released on 15 September 2026. The signed tag points to commit `b1a1c99ab52b687cf950d62c88bc2fa316b41663`; GitHub reports the tag signature valid. The tag is one commit ahead of GE's pinned upstream base. The only source changes in that commit are the `RELEASE` value, Meson's project version, and the declared Vulkan `engineVersion`. The release's renderer/shader fixes were already present in GE's pinned upstream revision. [Official release](https://github.com/doitsujin/dxvk/releases/tag/v3.1.1), [exact source comparison](https://github.com/doitsujin/dxvk/compare/601930949d111edbbcf9dd463948426d9f8f6ddd...v3.1.1).

The release notes mention DXGI scaling/background-color support for some Adobe applications, an ENB shader-compiler crash fix, flat-shading correction, and several game-specific rendering/presentation fixes. None is identified as a Fusion selection fix, and none is a new shader change beyond the preserved upstream commit. The official pair is therefore a control for downstream patches/build differences, not evidence of a newer rendering fix. [Release notes](https://github.com/doitsujin/dxvk/releases/tag/v3.1.1).

Downloaded artifact: [dxvk-3.1.1.tar.gz](https://github.com/doitsujin/dxvk/releases/download/v3.1.1/dxvk-3.1.1.tar.gz), 18,041,512 bytes. Published and independently verified SHA-256:

`40565b4a724aadc4433fa4e010b4b23916d9b1f1baeee64e17186db94f54e608`

Only the matching x64 Windows `d3d11.dll` and `dxgi.dll` pair was extracted for the candidate. The separately published `dxvk-native` package is for native application ports and is not the Wine DLL pair.

| Official x64 file | Size | SHA-256 |
| --- | ---: | --- |
| `d3d11.dll` | 7,483,406 bytes | `0a203b6255c893430f0a8461c618962df04e62aa41538d5a875b21868317cf9f` |
| `dxgi.dll` | 5,414,926 bytes | `e3c1178eb7f0dd59f91bcfcc257549e5b9cfdb5e8508719293de7f8704f53160` |

Private artifacts are in `/tmp/fusion-dxvk-3.1.1-review/`: the original archive, `x64/` pair, release/source metadata, and `artifact-manifest.json`. No prefix, installed runtime, DLL override, desktop association, or global package changed.

## Compatibility and compiler distinction

The current DXVK 3.x documentation requires Vulkan 1.4, Wine 10.1 or newer for WineVulkan, and RADV 25.0 or newer. Wine 11.17 and RADV 26.2.2 meet those version minimums; this research did not perform another live GPU probe. D3D11 requires both `d3d11.dll` and `dxgi.dll` from the same build. [Driver requirements](https://github.com/doitsujin/dxvk/wiki/Driver-support), [tagged installation instructions](https://github.com/doitsujin/dxvk/blob/v3.1.1/README.md).

DXVK's DXBC-to-SPIR-V compiler and Microsoft's HLSL `d3dcompiler_47.dll` perform different stages. Replacing DXVK does not ensure Qt and Fusion use a native HLSL compiler. The separately observed distinction between Autodesk's native `d3dcompiler_v2` and the Wine compiler in `system32` should remain its own controlled test. A private-prefix copy of the verified matching x64 Microsoft compiler, with the Fusion-specific override and rollback bytes retained, is a narrower way to make that compiler choice consistent than changing this DXVK pair at the same time.
