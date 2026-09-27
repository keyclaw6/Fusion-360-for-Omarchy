#!/usr/bin/env python3
"""Exercise the actual Wine 11.17 surface flush with an X Shape/upload simulation."""
import argparse
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--work-dir', required=True, type=Path)
base = parser.parse_args().work_dir.expanduser().resolve()
source = base / 'source/wine/dlls/winex11.drv'
body = (source / 'bitblt.c').read_text()
start = body.index('static BOOL x11drv_surface_flush(')
end = body.index('\n/***********************************************************************', start)
function = body[start:end]
stub = r'''
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "constant_alpha.h"
#define HAVE_LIBXSHAPE 1
#define TRUE 1
#define FALSE 0
#define BI_RGB 0
#define ShapeBounding 0
#define ShapeInput 2
#define ShapeSet 0
#define None 0
#define DIB_RGB_COLORS 0
typedef unsigned int UINT, DWORD;
typedef uint32_t ULONG;
typedef unsigned char BYTE;
typedef int BOOL, Pixmap;
typedef struct { int left, top, right, bottom; } RECT;
typedef struct { int biWidth, biBitCount, biCompression; } BITMAPINFOHEADER;
typedef struct { BITMAPINFOHEADER bmiHeader; DWORD bmiColors[3]; } BITMAPINFO;
typedef struct { int bytes_per_line, depth, bits_per_pixel; char *data; } XImage;
typedef struct { int depth; } XVisualInfo;
struct gdi_image_bits { void *ptr; };
struct window_surface { UINT alpha_mask, alpha_bits; };
struct image { XImage *ximage; int shminfo; };
struct x11drv_window_surface {
    struct window_surface header;
    struct image *image;
    int byteswap, constant_alpha, window, gc;
};
static int gdi_display, bounding, input, calls, pixmap_live;
static UINT backing[2];
static XVisualInfo default_visual = {24};
static struct x11drv_window_surface *get_x11_surface(struct window_surface *p)
{ return (struct x11drv_window_surface *)p; }
static int get_dib_stride(int width, int bits) { return ((width * bits + 31) >> 3) & ~3; }
static UINT RtlUlongByteSwap(UINT value) { return __builtin_bswap32(value); }
static int *get_window_surface_mapping(int bits, int *map) { return NULL; }
static void copy_image_byteswap(const BITMAPINFO *info, const unsigned char *src,
    unsigned char *dst, int src_stride, int dst_stride, int height, BOOL swap,
    int *mapping, UINT pad, UINT alpha)
{ memcpy(dst, src, height * src_stride); }
static Pixmap create_pixmap_from_image(int d, XVisualInfo *v, const BITMAPINFO *info,
    struct gdi_image_bits *bits, int colors)
{ assert(v->depth == 1); assert(bits->ptr); pixmap_live++; return 42; }
static void XShapeCombineMask(int d, int w, int kind, int x, int y, Pixmap mask, int op)
{
    assert(x == 0 && y == 0 && op == ShapeSet);
    assert(mask == None || (mask == 42 && pixmap_live));
    calls++;
    if (kind == ShapeBounding) bounding = mask;
    else { assert(kind == ShapeInput); input = mask; }
}
static void XFreePixmap(int d, Pixmap p) { assert(p == 42); pixmap_live--; }
static int put_shm_image(XImage *im, int *shm, int w, int gc, const RECT *r, const RECT *dirty)
{
    /* The test's shape keeps only pixel 0; input shape never clips an upload. */
    const UINT *pixels = (const UINT *)im->data;
    for (int x = dirty->left; x < dirty->right; x++)
        if (!bounding || x == 0) backing[x] = pixels[x];
    return TRUE;
}
static void XPutImage(int d, int w, int gc, XImage *im, int sx, int sy, int dx, int dy, int w2, int h) {}
static void XFlush(int d) {}
'''
tests = r'''
static void reset(void)
{ bounding = input = calls = pixmap_live = 0; backing[0] = backing[1] = 0xff000000; }
int main(void)
{
    UINT src[2] = {0xffffffff, 0x00000000}, dst[2] = {0}, shape = 1;
    XImage image = {8, 32, 32, (char *)dst};
    struct image holder = {&image, 0};
    struct x11drv_window_surface surface = {{0xff000000, 0}, &holder, 0, 0, 1, 1};
    BITMAPINFO info = {{2, 32, BI_RGB}, {0xff0000, 0x00ff00, 0x0000ff}};
    RECT rect = {0, 0, 2, 1}, dirty = {0, 0, 2, 1};

    unsetenv("WINE_X11_ARGB_SHAPE_INPUT"); reset();
    x11drv_surface_flush(&surface.header, &rect, &dirty, &info, src, TRUE, &info, &shape);
    assert(calls == 1 && bounding == 42 && input == 0 && !pixmap_live);
    assert(backing[1] == 0xff000000); /* Demonstrate old bounding upload clip. */

    setenv("WINE_X11_ARGB_SHAPE_INPUT", "1", 1); reset(); bounding = 42;
    x11drv_surface_flush(&surface.header, &rect, &dirty, &info, src, TRUE, &info, &shape);
    assert(calls == 2 && bounding == 0 && input == 42 && !pixmap_live);
    assert(backing[0] == 0xffffffff && backing[1] == 0);
    assert(src[1] == 0); /* No modification of producer alpha pixels. */

    calls = 0;
    x11drv_surface_flush(&surface.header, &rect, &dirty, &info, src, TRUE, NULL, NULL);
    assert(calls == 2 && bounding == 0 && input == 0);

    reset(); input = 42; image.depth = 24;
    x11drv_surface_flush(&surface.header, &rect, &dirty, &info, src, TRUE, &info, &shape);
    assert(calls == 2 && bounding == 42 && input == 0);
    image.depth = 32; surface.header.alpha_mask = 0;
    reset(); input = 42;
    x11drv_surface_flush(&surface.header, &rect, &dirty, &info, src, TRUE, &info, &shape);
    assert(calls == 2 && bounding == 42 && input == 0);

    surface.header.alpha_mask = 0xff000000;
    setenv("WINE_X11_ARGB_SHAPE_INPUT", "true", 1); reset();
    x11drv_surface_flush(&surface.header, &rect, &dirty, &info, src, TRUE, &info, &shape);
    assert(calls == 1 && bounding == 42 && input == 0);

    setenv("WINE_X11_ARGB_SHAPE_INPUT", "1", 1); reset();
    x11drv_surface_flush(&surface.header, &rect, &dirty, &info, src, FALSE, &info, &shape);
    assert(calls == 0);
    puts("PASS: real flush preserves transparent backing and input mask; shape removal; depth24/non-alpha fallback; exact opt-in; unchanged-shape path");
    return 0;
}
'''
harness = base / 'test-input-shape.c'
harness.write_text(stub + function + tests)
subprocess.run(['cc', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-Wno-unused-parameter', '-Wno-sign-compare',
                '-fsanitize=address,undefined', '-I' + str(source), str(harness),
                '-o', str(base / 'test-input-shape')], check=True)
subprocess.run([str(base / 'test-input-shape')], check=True)
