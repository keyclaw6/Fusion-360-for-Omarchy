#!/usr/bin/env python3
"""Compile the actual upload function against read-only X11 stubs and exercise pixels."""
import argparse
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--work-dir', required=True, type=Path, help='Prepared Wine 11.17 build work directory')
base = parser.parse_args().work_dir.expanduser().resolve()
source = base / 'source/wine/dlls/winex11.drv'
bitblt = (source / 'bitblt.c').read_text()
start = bitblt.index('static BOOL x11drv_surface_flush(')
end = bitblt.index('\n/***********************************************************************', start)
function = bitblt[start:end]
stub = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "constant_alpha.h"
typedef unsigned int UINT, DWORD;
typedef uint32_t ULONG;
typedef unsigned char BYTE;
typedef int BOOL;
typedef struct { int left, top, right, bottom; } RECT;
typedef struct { int biWidth, biBitCount, biCompression; } BITMAPINFOHEADER;
typedef struct { BITMAPINFOHEADER bmiHeader; DWORD bmiColors[3]; } BITMAPINFO;
typedef struct { int bytes_per_line, depth, bits_per_pixel; char *data; } XImage;
struct window_surface { UINT alpha_mask, alpha_bits; };
struct image { XImage *ximage; int shminfo; };
struct x11drv_window_surface {
    struct window_surface header;
    struct image *image;
    int x_offset, y_offset, byteswap, constant_alpha, window, gc;
};
#define TRUE 1
#define FALSE 0
#define BI_RGB 0
static int gdi_display, normal_copy_count, upload_count;
static struct x11drv_window_surface *get_x11_surface(struct window_surface *p)
{ return (struct x11drv_window_surface *)p; }
static int get_dib_stride(int width, int bits) { return ((width * bits + 31) >> 3) & ~3; }
static UINT RtlUlongByteSwap(UINT value) { return __builtin_bswap32(value); }
static int *get_window_surface_mapping(int bits, int *map) { return NULL; }
static void copy_image_byteswap(const BITMAPINFO *info, const unsigned char *src,
    unsigned char *dst, int src_stride, int dst_stride, int height, BOOL swap,
    int *mapping, UINT pad, UINT alpha)
{ normal_copy_count++; memcpy(dst, src, height * src_stride); }
static int put_shm_image(XImage *img, int *shm, int window, int gc, const RECT *rect, const RECT *dirty)
{ upload_count++; return TRUE; }
static void XPutImage(int d, int w, int gc, XImage *im, int sx, int sy, int dx, int dy, int w2, int h) {}
static void XFlush(int d) {}
'''
tests = r'''
int main(void)
{
    UINT src[8] = {0xffffffff, 0x00804020, 0xdeadbeef, 0x11111111,
                   0x00123456, 0xffffffff, 0xff000000, 0x22222222};
    UINT saved[8], dst[8], first[8];
    XImage image = {16, 32, 32, (char *)dst};
    struct image holder = {&image, 0};
    struct x11drv_window_surface surface = {{0, 76u << 24}, &holder, 0, 0, 0, 1, 1, 1};
    BITMAPINFO info = {{4, 32, BI_RGB}, {0xff0000, 0x00ff00, 0x0000ff}};
    RECT rect = {0, 0, 4, 2}, dirty = {0, 0, 2, 2};
    unsigned int a, channel;

    assert(x11drv_premultiply_constant_alpha(0xff000000, 76) == 0x4c000000);
    assert(x11drv_premultiply_constant_alpha(0xffffffff, 76) == 0x4c4c4c4c);
    assert(x11drv_premultiply_constant_alpha(0x00804020, 76) == 0x4c26130a);
    assert(x11drv_premultiply_constant_alpha(0x80804020, 76) == 0x4c26130a);
    for (a = 0; a < 256; a++)
        for (channel = 0; channel < 256; channel++)
        {
            UINT value = x11drv_premultiply_constant_alpha(channel * 0x010101, a);
            UINT expected = (unsigned int)((channel / 255.0) * a + 0.5);
            assert((value >> 24) == a);
            assert((value & 255) == expected);
            assert(((value >> 8) & 255) == expected);
            assert(((value >> 16) & 255) == expected);
        }

    memcpy(saved, src, sizeof(src));
    for (a = 0; a < 8; a++) dst[a] = 0xa5a5a5a5;
    assert(x11drv_surface_flush(&surface.header, &rect, &dirty, &info, src, FALSE, NULL, NULL));
    assert(dst[0] == 0x4c4c4c4c && dst[1] == 0x4c26130a);
    assert(dst[2] == 0xa5a5a5a5 && dst[3] == 0xa5a5a5a5);
    assert(dst[5] == 0x4c4c4c4c && dst[6] == 0xa5a5a5a5 && dst[7] == 0xa5a5a5a5);
    memcpy(first, dst, sizeof(dst));
    for (a = 0; a < 100; a++)
        assert(x11drv_surface_flush(&surface.header, &rect, &dirty, &info, src, FALSE, NULL, NULL));
    assert(!memcmp(src, saved, sizeof(src)));
    assert(!memcmp(dst, first, sizeof(dst)));
    assert(normal_copy_count == 0);

    surface.header.alpha_bits = 0;
    x11drv_surface_flush(&surface.header, &rect, &dirty, &info, src, FALSE, NULL, NULL);
    assert(dst[0] == 0 && dst[1] == 0);
    surface.header.alpha_bits = 255u << 24;
    x11drv_surface_flush(&surface.header, &rect, &dirty, &info, src, FALSE, NULL, NULL);
    assert(dst[0] == 0xffffffff && dst[1] == 0xff804020);
    surface.header.alpha_bits = ~0u;
    x11drv_surface_flush(&surface.header, &rect, &dirty, &info, src, FALSE, NULL, NULL);
    assert(dst[1] == 0xff804020);
    surface.header.alpha_bits = 76u << 24;
    surface.byteswap = 1;
    x11drv_surface_flush(&surface.header, &rect, &dirty, &info, src, FALSE, NULL, NULL);
    assert(dst[1] == 0x0a13264c);

    surface.byteswap = 0;
    surface.constant_alpha = 0;
    surface.header.alpha_mask = 0xff000000;
    x11drv_surface_flush(&surface.header, &rect, &dirty, &info, src, FALSE, NULL, NULL);
    assert(normal_copy_count == 1);
    assert(!memcmp(src, saved, sizeof(src)));
    printf("PASS: 65,536 channel/alpha pairs; source alpha ignored; dirty bounds; 100 stable repaints; 0/76/255/reset; byteswap; preserved per-pixel branch; %d uploads\n", upload_count);
    return 0;
}
'''
harness = base / 'test-constant-alpha.c'
harness.write_text(stub + function + tests)
subprocess.run(['cc', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-Wno-unused-parameter', '-Wno-sign-compare',
                '-fsanitize=address,undefined', '-I' + str(source), str(harness),
                '-o', str(base / 'test-constant-alpha')], check=True)
subprocess.run([str(base / 'test-constant-alpha')], check=True)

window = (source / 'window.c').read_text()
start = window.index('BOOL use_argb_constant_alpha(')
end = window.index('\n/***********************************************************************', start)
function = window[start:end]
stub = r'''
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef unsigned int UINT, DWORD, COLORREF;
typedef unsigned char BYTE;
typedef int BOOL, HWND, Window;
typedef struct { unsigned long visualid; int depth; unsigned long red_mask, green_mask, blue_mask; } XVisualInfo;
struct x11drv_win_data { int embedded, client_window, whole_window, argb_constant_alpha, display, layered; };
#define TRUE 1
#define FALSE 0
#define LWA_COLORKEY 1
#define LWA_ALPHA 2
#define FIXME(...) do {} while(0)
static BOOL client_side_graphics = TRUE;
static Window root_window = 1;
static int gdi_display;
static XVisualInfo default_visual = {0x6e, 24, 0xff0000, 0x00ff00, 0x0000ff};
static XVisualInfo argb_visual = {0x9e, 32, 0xff0000, 0x00ff00, 0x0000ff};
static struct x11drv_win_data data = {0, 0, 2, 0, 0, 0};
static const XVisualInfo *selected;
static UINT opacity_flags, opacity_alpha;
static struct x11drv_win_data *get_win_data(HWND hwnd) { return &data; }
static void release_win_data(struct x11drv_win_data *data) {}
static void set_window_visual(struct x11drv_win_data *data, const XVisualInfo *visual, BOOL alpha) { selected = visual; }
static Window X11DRV_get_whole_window(HWND hwnd) { return 0; }
static void XFlush(int d) {}
static void sync_window_opacity(int d, Window w, BYTE alpha, DWORD flags)
{ opacity_flags = flags; opacity_alpha = alpha; }
'''
tests = r'''
static void original_path(DWORD flags)
{
    X11DRV_SetLayeredWindowAttributes(1, 0, 76, flags);
    assert(!data.argb_constant_alpha);
    assert(selected == &default_visual);
    assert(opacity_alpha == 76 && opacity_flags == flags);
}
int main(void)
{
    unsetenv("WINE_X11_ARGB_CONSTANT_ALPHA");
    original_path(LWA_ALPHA);
    setenv("WINE_X11_ARGB_CONSTANT_ALPHA", "0", 1);
    original_path(LWA_ALPHA);
    setenv("WINE_X11_ARGB_CONSTANT_ALPHA", "true", 1);
    original_path(LWA_ALPHA);
    setenv("WINE_X11_ARGB_CONSTANT_ALPHA", "1", 1);
    X11DRV_SetLayeredWindowAttributes(1, 0, 76, LWA_ALPHA);
    assert(data.argb_constant_alpha && selected == &argb_visual && opacity_flags == 0);
    X11DRV_SetLayeredWindowAttributes(1, 0, 255, LWA_ALPHA);
    assert(data.argb_constant_alpha && opacity_flags == 0);
    original_path(LWA_ALPHA | LWA_COLORKEY);
    original_path(LWA_COLORKEY);
    original_path(0);
    data.embedded = 1; original_path(LWA_ALPHA); data.embedded = 0;
    data.client_window = 3; original_path(LWA_ALPHA); data.client_window = 0;
    data.whole_window = root_window; original_path(LWA_ALPHA); data.whole_window = 2;
    client_side_graphics = 0; original_path(LWA_ALPHA); client_side_graphics = 1;
    argb_visual.depth = 24; original_path(LWA_ALPHA); argb_visual.depth = 32;
    argb_visual.red_mask = 0x0000ff; original_path(LWA_ALPHA); argb_visual.red_mask = 0xff0000;
    argb_visual.visualid = 0; original_path(LWA_ALPHA); argb_visual.visualid = 0x9e;
    puts("PASS: exact opt-in; property suppressed only for baked GDI alpha; alpha changes; original path for missing/invalid flag, color key, embedded/client producer, root, disabled GDI, unavailable/incompatible visual");
    return 0;
}
'''
harness = base / 'test-constant-alpha-attributes.c'
harness.write_text(stub + function + tests)
subprocess.run(['cc', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-Wno-unused-parameter', '-fsanitize=address,undefined',
                str(harness), '-o', str(base / 'test-constant-alpha-attributes')], check=True)
subprocess.run([str(base / 'test-constant-alpha-attributes')], check=True)
