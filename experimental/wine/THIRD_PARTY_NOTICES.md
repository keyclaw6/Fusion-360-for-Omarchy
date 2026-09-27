# Notices

The standalone launcher reuses selected registry, process inspection and identity-readiness code from the local Test 1 integration. Its original Fusion180 attribution follows.

Fusion180's license notice is retained here:

> MIT License
>
> Copyright (c) 2026 KOTARO
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.


The separately downloaded Lolig4 Fusion-patched Wine runtime uses Wine LGPL-2.1-or-later and its included component licenses. No runtime binaries, Autodesk binaries, prefixes or designs are distributed in this repository. See docs/upstream-review.md for source and patch provenance.

The included Wine patch context and local alpha source modifications are
LGPL-2.1-or-later; `runtime-patches/LICENSE.Wine-LGPL-2.1` contains the license.
The included Lolig4 patch sources retain their MIT notice at
`runtime-patches/LICENSE.Lolig4-MIT`. Exact source URLs, ordered patch hashes and
reproduction inputs are in `runtime-patches/manifest.json` and its README.

Wine is Copyright (c) 1993–2026 the Wine project authors; its upstream notice is
retained in [LICENSE.Wine-Copyright](runtime-patches/LICENSE.Wine-Copyright).
The `symcrypt-rsa-exponent1.patch` includes Microsoft SymCrypt source context,
which retains Microsoft's MIT license and copyright notice in
[LICENSE.Microsoft-SymCrypt](runtime-patches/LICENSE.Microsoft-SymCrypt).
