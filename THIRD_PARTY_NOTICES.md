# Third-party notices

The plugin's original code is MIT-licensed; distribute `LICENSE` and this file
with PRX packages. Calling ARK/Sony runtime APIs does not bundle their firmware.

## PSPSDK import/header infrastructure

Source: <https://github.com/pspdev/pspsdk/blob/master/LICENSE>.
The pinned PSPDEV build uses PSPSDK headers, export/import generation and stubs.

Copyright (c) 2005  adresd
Copyright (c) 2005  Marcus R. Brown
Copyright (c) 2005  James Forshaw
Copyright (c) 2005  John Kelley
Copyright (c) 2005  Jesper Svennevid
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:
1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.
3. The names of the authors may not be used to endorse or promote products
   derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE AUTHORS ``AS IS'' AND ANY EXPRESS OR
IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

## Optional host research, not part of the PRX

- pspdecrypt 1.0: GPLv3, with additional component notices in its source tree.
- libLZR 0.11: BenHur, **CC BY-SA 3.0**, as stated in `libLZR.c/.h`;
  <https://creativecommons.org/licenses/by-sa/3.0/>. The project's wrapper does
  not relicense it. Decoder products and the patched RCOMage binary remain local.
- RCOMage: ZiNgA BuRgA / Youness Alaoui, LGPL-2.1 notices; the maintained patch
  retains those terms and introduces the separately licensed libLZR dependency.
- Capstone 5.0.6: retain its BSD notices and component licenses in the package.

The Python Rel2 research reader cites PPSSPP's format/algorithm as its reference.
No PPSSPP library is linked into the PRX.
Reference: <https://github.com/hrydgard/ppsspp/blob/master/Core/ELF/ElfReader.cpp>.
These statements do not authorize redistributing proprietary Sony firmware.
