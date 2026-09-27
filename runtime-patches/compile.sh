#!/bin/bash
# Executed only inside the pinned SDK by build-overlay.py.
set -euo pipefail
cd /work/obj64
export CC=x86_64-linux-gnu-gcc CXX=x86_64-linux-gnu-g++
export CFLAGS='-mcmodel=small -march=nocona -mtune=core-avx2 -mfpmath=sse -O2 -fwrapv -fno-strict-aliasing -ggdb -ffunction-sections -fdata-sections -fno-omit-frame-pointer -ffile-prefix-map=/source=. -ffile-prefix-map=/work=. -Wl,--exclude-libs=libstdc++.a -Wno-discarded-qualifiers'
export CXXFLAGS="$CFLAGS"
/source/wine/configure --enable-win64 --enable-archs=x86_64 --enable-werror --without-wayland --with-mingw=gcc --without-ffmpeg --disable-tests --prefix=/work/install
make -j4 -o dlls/ntdll/ntdll.so dlls/win32u/win32u.so dlls/winex11.drv/winex11.so
mkdir -p /work/candidate
cp dlls/win32u/win32u.so /work/candidate/win32u.so
cp dlls/winex11.drv/winex11.so /work/candidate/winex11.so
for module in win32u.so winex11.so; do
    objcopy --only-keep-debug "/work/candidate/$module" "/work/candidate/$module.debug"
    strip --strip-unneeded "/work/candidate/$module"
done
