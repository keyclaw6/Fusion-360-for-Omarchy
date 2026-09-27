# Upstream reference

[Fusion180](https://github.com/Kotya31415/Fusion180) by KOTARO, at commit
`04ff7ad901e3e6aab34fd342cabcca2b31ea523a`, was the principal implementation
reference. This integration initially followed its OpenGL Core recommendation
and retains its identity-startup approach with a separate umu launcher. The
current candidate now uses a DirectX 11 canvas. The source review and adaptations
are recorded in [docs/upstream-review.md](docs/upstream-review.md).

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

Autodesk Fusion, GE-Proton, umu and Steam Linux Runtime are obtained separately
and retain their respective licenses. Their binaries are not part of this
repository.

The runtime source patches have separate notices and provenance in
[runtime-patches/manifest.json](runtime-patches/manifest.json). The owned-tool-window
patch is from Lolig4's Autodesk Fusion 360 on Linux project, under the retained
[MIT notice](runtime-patches/LICENSE.Lolig4-MIT). The ARGB input-shape and
constant-alpha patches modify Wine code and are provided under
[LGPL-2.1-or-later](runtime-patches/LICENSE.Wine-LGPL-2.1). These patch licenses
are separate from the integration code's root MIT license. The build recipe
records exact source revisions and reproduces the reviewed module; no compiled
Wine module is committed here.

Wine is Copyright (c) 1993–2026 the Wine project authors. Its upstream
[copyright notice](runtime-patches/LICENSE.Wine-Copyright) is retained alongside
the LGPL text. The unfinished standalone Wine subtree retains its own
[notices](experimental/wine/THIRD_PARTY_NOTICES.md), including Microsoft's MIT
notice for the SymCrypt source context in one upstream patch.

The README artwork depicts Autodesk Fusion and Omarchy marks to identify the
software involved. Those marks are not licensed by this project's MIT license
and imply no endorsement. See [artwork provenance](assets/README.md).
