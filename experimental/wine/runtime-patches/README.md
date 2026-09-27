# Wine 11.17 alpha source port

This is an experimental `winex11.so` for the exact standalone Wine archive pinned by Test 2. It was installed locally and corrected the Browser transparency in independent native review. The initial post-edit face-highlight rejection was premature: corrected controls passed with Normal selection, as documented in [the review-method audit](../docs/reviewer-audit.md). The complete standalone Wine route remains unfinished and has not passed the full operational gate; modal-save behavior was not reviewed on this candidate. The build script itself never changes the installed runner, prefix, renderer, or desktop configuration. Its two settings affect X11 transparency; they do not repair missing native shaders or establish complete application acceptance.

The source is official Wine `wine-11.17`, commit `36b6a2cf679fb395f668a917b76537190e212d9c`, with all ten pinned Lolig4 patches followed by the two local patches in `manifest.json`. Every patch is included and hashed. See [the upstream review](../docs/upstream-review.md) for artifact provenance and the publisher's missing binary-source attestation.

`argb-input-shape.patch` keeps an ARGB surface's full bounding rectangle writable and uses the alpha mask as its input shape. Without this change, bounding-shape clipping can prevent transparent pixels from replacing old opaque pixels in an XWayland redirected pixmap. It is enabled only by `WINE_X11_ARGB_SHAPE_INPUT=1`, only for surfaces with per-pixel alpha and depth 32. Shape removal and non-ARGB transitions retain their original behavior.

`argb-constant-alpha.patch` converts GDI constant-alpha uploads to premultiplied ARGB in a separate buffer, rather than depending on `_NET_WM_WINDOW_OPACITY`. Hyprland's XWayland window management does not consume that property. The patch suppresses the redundant property for the converted path, avoiding double alpha on compositors that support it. It is enabled only by `WINE_X11_ARGB_CONSTANT_ALPHA=1`. Native client producers, embedded windows, color-key surfaces, unsupported visuals, and the desktop root keep the original path. Per-pixel alpha remains separate. The source buffer is never repeatedly premultiplied.

The ports preserve these mechanisms from Test 1 but remove GE-only context such as the gamescope shape exception and layered-overlay branch. No GE binary or GE source tree is used to build this module. No Qt backend change is part of this patch set. Changing only Qt Quick's backend does not remove the separate raster Browser surface; forcing all QWidget windows through RHI would introduce a different accelerated-alpha path and needs separate evidence.

## Build inputs and command

`build-module.py` builds from fixed paths inside a private read-only SDK mount using bubblewrap. The SDK is only a compiler environment; the output remains a normal standalone host Wine module. It does not run Wine or use a runtime container to launch Fusion.

Required local commands are Python 3.12 or later, bash, bubblewrap, patch, nm/readelf, gdb, ldd, and a C compiler with AddressSanitizer/UndefinedBehaviorSanitizer. No global package change was needed on the investigated machine. Supply these exact verified inputs:

- The [official Wine commit archive](https://api.github.com/repos/wine-mirror/wine/tarball/36b6a2cf679fb395f668a917b76537190e212d9c), SHA-256 `e638bf7344d6fe073ababe678ebdf6a258457aa30f660bdac53d3018f38bf0af`.
- The [standalone Lolig4 runner archive](https://github.com/Lolig4/Autodesk-Fusion-360-for-Linux/releases/download/Version_1/fusion-wine-build.tar.gz), SHA-256 `9ef47e25de30d52fb110b9f257d128755904ecfabda4a0c2ce43416e075a4479`.
- An already verified Steam SDK root from `registry.gitlab.steamos.cloud/proton/steamrt4/sdk/x86_64:4.0.20260714.251823-0`. Its original `sdk-manifest.json` must be alongside the root and have SHA-256 `6c1789cad862fd8ed9d46d71bbf8752bb7cb2336ab5e9680c0f0e3e7c88d77f1`. The investigated machine already has this private cache from Test 1. The compiler is Debian GCC 14.2.0-19, with both MinGW toolchains. This recipe does not install or update the SDK.

For the current private caches, the reproduction command is:

```sh
python3 runtime-patches/build-module.py \
  --source-archive /tmp/fusion-wine11.17-alpha-port/wine-source.tar.gz \
  --runner-archive /tmp/fusion-standalone-review/fusion-wine-build.tar.gz \
  --sdk-root "$HOME/.cache/fusion360-for-omarchy/builds/palette-ge11-7/sdk-root" \
  --work-dir /tmp/fusion-wine11.17-alpha-recipe \
  --output /tmp/fusion-wine11.17-alpha-recipe-output/winex11.so
```

Work and output locations must be new. Substitute other private paths for a subsequent reproduction. The script checks all archive, patch, modified-source and output hashes. It applies patches with zero fuzz, compiles with warnings as errors, compares the candidate with the archive, and runs the source sanitizer tests. It writes the private output only after checks pass. There is no deployment command.

The expected stripped candidate SHA-256 is `6fdec486a07b4a3d178dcbb70b033d39f46f740da18ea9e8aa19db6cefe769ce`. `compile.sh` retains an unstripped module in the work directory and a separate debug file. Exact paths inside the SDK and file-prefix mappings keep debug paths deterministic.

## ABI and validation boundaries

The candidate links against the archive's exact `ntdll.so` and `win32u.so`, not replacement objects from another build. Their hashes are pinned. Original and candidate have identical defined exports, identical undefined imports, and identical ELF `DT_NEEDED` entries. Actual host `ldd -r` resolves every dependency and symbol with those same two original modules.

The Wine 11.17 user-driver interface version is 110; Test 1's GE interface was 111. Both the original standalone module and the rebuilt candidate have a 1,216-byte `user_driver_funcs`, 712-byte `gdi_dc_funcs`, and 160-byte `window_surface`. The alpha field is internal to winex11; no shared header or driver vtable was changed. This is source and ABI compatibility evidence, not a substitute for a live acceptance test.

`test-constant-alpha.py` extracts the actual upload and attribute functions. Under ASan/UBSan it checks all 65,536 channel/alpha pairs, ignored source-alpha bytes, dirty bounds, 100 repeated uploads without darkening, byte swapping, the existing per-pixel branch, and opt-in/producer/visual exclusions. `test-input-shape.py` extracts the actual flush function and models X Shape upload clipping. It demonstrates old opaque backing surviving the old bounding shape, then verifies transparent replacement with the new input mask, shape removal, depth-24/non-alpha fallback, and disabled or invalid flags. These tests execute native C harnesses; they do not start Wine or touch a display.

The SDK can configure the full Wine source with both i386 and x86_64 PE compilers without installing packages. A complete runtime has not been rebuilt here. Configure reports missing optional Wayland, OpenCL, pcap, scanner/camera, FFmpeg/GStreamer, OSSv4, ISDN and Samba NetAPI development support. Replacing the complete published runtime with such a build would require a separate feature review. The narrow module build avoids changing those existing components.

Wine source context and the local modifications are covered by [LGPL 2.1 or later](LICENSE.Wine-LGPL-2.1). The included Lolig4 patch sources retain the project's [MIT notice](LICENSE.Lolig4-MIT). All original upstream patch URLs and hashes are in the manifest. The official base source, this complete patch set, and the build recipe form the source inputs for this candidate.
