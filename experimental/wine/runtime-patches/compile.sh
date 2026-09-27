#!/bin/bash
set -euo pipefail
cd /work/obj64
export CC=gcc CXX=g++
export CFLAGS='-O2 -g -fno-strict-aliasing -ffile-prefix-map=/source=. -ffile-prefix-map=/work=.'
export CXXFLAGS="$CFLAGS"
/source/wine/configure --enable-archs=i386,x86_64 --disable-tests --enable-werror --prefix=/work/install
make -j6 -o dlls/ntdll/ntdll.so -o dlls/win32u/win32u.so dlls/winex11.drv/winex11.so
cp dlls/winex11.drv/winex11.so /work/candidate/winex11.so
objcopy --only-keep-debug /work/candidate/winex11.so /work/candidate/winex11.so.debug
strip --strip-unneeded /work/candidate/winex11.so
