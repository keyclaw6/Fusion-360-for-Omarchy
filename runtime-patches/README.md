# Pinned Fusion Wine overlay

This directory contains source for two replacement modules in `files/lib/wine/x86_64-unix/`: `winex11.so` and `win32u.so`. Both are built from exact GE-Proton11-7 source in the pinned Steam Runtime SDK. The original GE archive stays unchanged. The installer verifies and applies the pair under its maintenance lock; other runner files stay official originals.

`manifest.json` schema 2 records the ordered module pair, input commits, SDK manifest, source and patch hashes, output hashes and required environment. Each `modules` entry contains exactly `target`, `original_sha256` and `sha256`. Compilation does not satisfy the separate independent Fusion acceptance gate in `docs/acceptance.md`.

## The four patches

1. `owned-tool-windows.patch` is the exact MIT-licensed patch from [Lolig4 commit 7da442d6](https://codeberg.org/Lolig4/Autodesk-Fusion-360-on-Linux/src/commit/7da442d6af5ac2619e5151475d2be54efe6170bc/files/setup/data/fusion-patches/winex11-owned-tool-windows.patch). It makes owned tool popups managed UTILITY windows. Live Fusion testing made the profile menu and Preferences respond to one click. This is the only patch imported from that project; its combined binary is not used.
2. `argb-input-shape.patch` lets transparent pixels reach layered-window backing pixmaps while preserving their alpha-derived input shape. Before the fix, the Browser panel contained 92,000 opaque black backing pixels behind excluded ShapeBounding regions. Afterward, those pixels were zero-alpha, the bounding region was rectangular and the input region retained 36 rectangles. [XWayland 24.1.13](https://gitlab.freedesktop.org/xorg/xserver/-/blob/xwayland-24.1.13/hw/xwayland/xwayland-window.c) forwards input shapes to Wayland. This path requires `WINE_X11_ARGB_SHAPE_INPUT=1`.
3. `argb-constant-alpha.patch` supports the Save dialog's GDI backdrop. [Hyprland's pinned XWM](https://github.com/hyprwm/Hyprland/blob/efb50993780079460b0cbed1363e2166a2de1d9f/src/xwayland/XWM.cpp) does not consume Wine's `_NET_WM_WINDOW_OPACITY` property. With `WINE_X11_ARGB_CONSTANT_ALPHA=1`, compatible GDI windows requesting exactly LWA_ALPHA use a separate premultiplied ARGB upload buffer. Repeated repaints preserve source pixels. Color keys, native producers and embedded windows retain their existing path. Live testing observed depth32, backdrop pixels `0x4c000000`, no redundant opacity property, correct gray dimming and an opaque Save dialog.
4. `vulkan-present-wait.patch` fixes a confirmed offscreen presentation race in `win32u.so`. After Sketch Grid was turned off, passive XComposite capture showed a correctly white DX11 source pixmap while the visible parent still contained the old grid. No input or automation request occurred between captures. GE called `client_surface_present()` immediately after `vkQueuePresentKHR`; [Mesa X11 WSI](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-26.2.2/src/vulkan/wsi/wsi_common_x11.c) queues presentation to a worker, so the parent copy could read the previous frame. The patch waits for the application's submitted present ID before copying. It adds no repaint timer.

The Vulkan change requires `WINE_X11_VULKAN_PRESENT_WAIT=1`. It applies only to active, offscreen, non-managed, non-retired host swapchains. It checks the actual enabled device feature, matching extension and function pointer, plus the wait2 creation flag when applicable. Existing [present IDs](https://docs.vulkan.org/refpages/latest/refpages/source/VkPresentIdKHR.html) are retained; ID2 is correctly repacked when host and managed swapchains share one batch. Failed preparation, failed host submission and untouched caller result buffers cannot authorize a new wait.

Each wait has a one-second failure bound. A timeout or error disables later waits for that swapchain. Missing features/IDs retain the original copy with a diagnostic; that fallback does not claim correct rendering on unsupported configurations. `WINEDEBUG=-all,+x11present` logs HWND, present ID, result and elapsed time without application data. The shared `vulkan_device` ABI and headers remain unchanged; bookkeeping uses a private allocation wrapper.

## Renderer configuration

The modeling canvas uses `VirtualDeviceDx11` through DXVK. OpenGL Core exposed a separate Wine `SwapBuffers(hdc)` defect: a current Qt context's drawable could be swapped instead of the named canvas. This configuration avoids that interaction; it does not patch WGL.

Version 3 selects `QSG_RHI_BACKEND=opengl` for Fusion's implicit Qt Quick UI composition while keeping transparent palettes raster and the modeling canvas on DirectX 11. The preceding version 2 selected `d3d11`; its ordinary cold launch exposed a gray native canvas even with both original Wine modules. OpenGL Qt composition corrected that startup reproduction with all Wine diagnostics disabled. The earlier broad selection rejection was premature: the corrected visible-face control passed before and after a native feature edit. V3 is now installed; see [the retest and promotion](../docs/ge-normal-retest.md) and [current operational review](../docs/operational-review.md). Global `QT_WIDGETS_RHI` forcing is outside this configuration.

The installed runtime environment contains exactly the two ARGB flags above, `QSG_RHI_BACKEND=opengl` and `WINE_X11_VULKAN_PRESENT_WAIT=1`. DXVK synchronization retains its default behavior. A prior cold comparison of the supported `DXVK_CONFIG=dxgi.syncInterval = 0` setting showed no measurable improvement: the default produced 115 canvas presentations in 2.561 seconds, with a 22 ms median interval and 21 ms median wait; interval zero produced 116 in 2.565 seconds, with the same 22 ms median interval and a 22 ms median wait. Both passed the first workplane and grid captures after a requested 350 ms settle; this is not a measured 350 ms latency bound. The setting was discarded, and no Wine presentation-mode patch is packaged. These historical presentation measurements are not an end-to-end frame-rate or latency benchmark of the final setup.

All manifest values apply only to the dedicated Fusion runtime. Changing a module or environment requires a cold restart. Wine filters Unix `QT_*`; diagnostics must use `WINEQT_*` and verify the Windows environment. `QSG_*` uses ordinary names. Compositor integration in `docs/hyprland.md` is separate.

## Reproduce both modules

Dependencies: Python 3.12+, Git, Bash, bubblewrap, patch and autoreconf. Source preparation here used Python 3.14 and Autoconf 2.73; compilation uses pinned SDK GCC 14.2.0-19. The script makes no global package, runner or prefix changes.

```bash
python3 runtime-patches/build-overlay.py \
  --runner-archive "$HOME/.cache/fusion360-for-omarchy/GE-Proton11-7-x86_64.tar.gz" \
  --output-dir "$HOME/.cache/fusion360-for-omarchy/ge-proton11-7-omarchy-x11-v3" \
  --work-dir "$HOME/.cache/fusion360-for-omarchy/builds/recipe-ge11-7-v3-new"
```

The work directory must be new or empty. The output directory must be new or already contain exactly both reviewed modules. Successful output contains only `winex11.so` and `win32u.so`. Schema 2 requires `--output-dir`; legacy schema 1 uses `--output FILE`.

The script verifies the official SDK's immutable OCI manifest and every layer before extraction. `--sdk-root /path/to/sdk-root` reuses a previously verified private SDK; its parent must contain the matching `sdk-manifest.json`. Do not substitute an arbitrary system root.

The build fetches [GE commit c191f35d](https://github.com/GloriousEggroll/proton-ge-custom/tree/c191f35dcebbeccfacd3b4c6f6eea026e588c1c2), verifies Wine/staging commits and runs the hash-checked Wine preparation, including WineOpenXR prerequisites and generated sources. Patches apply with zero fuzz. Compilation runs in a read-only SDK with fixed `/source` and `/work` paths, without display, profile or network access.

`compile.sh` builds both modules with Werror. Only the archive's verified `ntdll.so` is prebuilt; `win32u.so` is compiled and linked before `winex11.so`. Wayland/FFmpeg are disabled for this isolated build; their installed modules remain untouched. Each stripped output must match its manifest SHA256. Dynamic exports, exported data sizes and required libraries are compared with the official originals. Relocations are checked using the newly built pair together with pinned ntdll. Any mismatch stops output publication.

A fresh source checkout through this schema 2 recipe on 2026-09-26 reproduced both hashes exactly:

The version 3 configuration uses these unchanged version 2 build outputs; it changes the required Qt environment, not the compiled patch set.

| Module | SHA256 |
| --- | --- |
| winex11.so | `6b5f680717f8e1db59039eeb50a953ac7703d6a7e88cd1e891c345e372020f1f` |
| win32u.so | `201ef0e0f4d48dfc093a16ffdd221c0ef37427e35ec59238756e0dc54c134d38` |

The private work directory retains prepared corresponding source, logs, unstripped modules, debug symbols, official originals for comparison and `built-manifest.json`. The recipe does not install its output.

## Source regression tests

Optional tests compile actual patched functions with host stubs under AddressSanitizer and UndefinedBehaviorSanitizer. They need a host C compiler and completed build directory:

```bash
python3 runtime-patches/test-constant-alpha.py --work-dir /path/to/completed/build-work
python3 runtime-patches/test-present-wait.py --work-dir /path/to/completed/build-work
```

The alpha test covers all 65,536 channel/alpha pairs, reserved source alpha, zero/partial/full alpha, byte order, dirty rectangles, repeated uploads and fallback conditions. The present test extracts the real feature/wait helpers, pNext repacker and host submission block. It covers mixed host/managed ID2 mapping, preparation allocation failures, stale successful-looking caller results, failed host submission, disabled features, onscreen/retired/stale swapchains, missing IDs, wait2 flags and bounded failure handling. Neither starts Wine or replaces live acceptance.

## Installation, recovery and licenses

The lock's `runner_overlay` must repeat the manifest's id, ordered `modules`, required environment and manifest path. A missing or mismatched module fails closed. Promotion preserves both originals and the prior lock together; rollback restores their coupled state. Follow `docs/install.md` instead of replacing modules in a running runner.

The imported patch retains `LICENSE.Lolig4-MIT`. Wine and local alpha/presentation changes use LGPL-2.1-or-later; see `LICENSE.Wine-LGPL-2.1`. Redistributors must retain complete corresponding source, including prepared `source/wine` and its notices, rather than only these patches.
