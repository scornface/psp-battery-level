# Native interfaces

All addresses below are module-relative offsets for the supported standard Sony 6.61 modules. Discover the loaded module bases before using them. [Architecture](architecture.md) describes runtime ownership and synchronization; [dependencies](dependencies.md#optional-firmware-research) covers the research environment.

## Inputs and reproduction

Use a locally obtained standard non-Go Sony 6.61 updater, MD5 `6be8878f475ac5b1a499b95ab2f7d301`. Set `PSP_UPDATER` to its absolute EBOOT.PBP path and configure the external directories from the dependency guide, then extract it with pspdecrypt 1.0:

```sh
"$PSP_PSPDECRYPT_ROOT/pspdecrypt" -A -O "$PSP_FIRMWARE_ROOT" "$PSP_UPDATER"
```

The analysis tools accept recorded module identities, not arbitrary firmware with a matching version string:

| Decrypted PRX | SHA-256 |
| --- | --- |
| `paf.prx` | `699413b667199732af0b3cc2379ea65df0c4e2daa7727c6d1bbb757df0160417` |
| `vshmain.prx` | `dd283103f78db14a8bd08c8aa03ecc01807850baed54fb77b3c38ba7ffff712f` |
| `dialogmain.prx` | `c3602b6c63f559318af51390bff21babbd68371cf505e6dffa20ad670ee86578` |
| `impose_02g.prx` | `4ad1f9c292eb88f7ea137ddb965c0a9ce7551251948f87e1b97534e5a2d542f0` |
| `display_02g.prx` | `8e0a42ad82095e61c2e67bb68d140dd8f64c003c8172749cb98bc7eee5cf2b9a` |

Relocation supports base zero only. Consumers check the generated `.bin.json` manifest against the source and relocated image. Use new output paths under `build/analysis/`; commands refuse overwrites.

```sh
python3 tools/analysis/resolve_prx_rel2.py "$PSP_FIRMWARE_ROOT/F0/vsh/module/paf.prx" build/analysis/paf.relocated.bin build/analysis/paf.relocations.tsv
python3 tools/prx_libraries.py "$PSP_FIRMWARE_ROOT/F0/vsh/module/paf.prx" --relocated-image build/analysis/paf.relocated.bin
python3 tools/analysis/inspect_paf.py --range 0x105aa0:0x105b80
python3 tools/analysis/decompress_rco_rlz.py "$PSP_FIRMWARE_ROOT/F0/vsh/resource/system_plugin_fg.rco" build/analysis/system_plugin_fg_tables.bin
python3 tools/analysis/dump_rco.py "$PSP_FIRMWARE_ROOT/F0/vsh/resource/system_plugin_fg.rco" build/analysis/system_plugin_fg.xml
python3 tools/analysis/verify_home.py
python3 tools/analysis/verify_assets.py
```

`dump_rco.py` requires the recorded RCOMage build. Repeat relocation for VSH/Dialogmain when inspecting their callsites. Disassembly and string-reference results are candidates for inspection, not proof of complete call coverage.

## XMB resource and object layout

`system_plugin_fg.rco`, page `page_indicator`, defines the status objects:

| Object | Native definition |
| --- | --- |
| `Plane battery` | Position (223,124), dimensions 44×16 |
| `Plane battery_shadow` | Position (225,122), dimensions 44×16 |
| `Text clock` | Position (203,123), text size 7.6, icon offset 2 |

There is no percentage Text in the resource. The clock's resource string is a placeholder; VSH formats the actual UTF-16 date/time. The plugin creates independent PAF Text instances. The battery texture has four stacked 44×16 slices. Connecting DC, the charging API flag and Sony's visual charging animation are separate states; the plugin does not drive that animation.

The resource SHA-256 is `3da2042c7042faf1d810c970bdb500ce812ea31e548ee9d0d17e57483c1c71dd`. RLZ metadata occupies three words at `+0xa4`, with payload at `+0xb0`. The table decoder consumes `0x5f5` bytes and produces `0x20ac` bytes, SHA-256 `8983cb43c0bc17c9fa443a951191ab592c9834368c712f6b1c78052dba78fae3`.

### Creation, registration and calls

VSH `+0x35a64` creates the indicator page using PAF NID `0x3876721b`. Lookups at `+0x35a94/+0x35aac/+0x35ac4`, NID `0xb94ad2a4`, resolve battery, shadow and clock into globals `+0x5caac/+0x5cab0/+0x5cab4`. Clock event 100 is registered at `+0x35bc4`, with callback `+0x30ba8` and native float argument 1000. The preserved layout callback is `+0x3113c`.

| Interface or structure | Address or offset |
| --- | --- |
| Text allocation / constructor | PAF `+0x13a4e0` / `+0x105aa0`; node size `0x340` |
| Text / Page / Plane vtable | PAF `+0x18b578` / `+0x18b218` / `+0x18b068` |
| Text string setter | Node vtable `+0xb4` → PAF `+0x105e20` |
| Text subobject | Node `+0x1e8`; vtable PAF `+0x18c118`, size `0x20` |
| Backend pointer / size | Subobject `+0x1c` / `0x1c0` |
| Backend string setter | Subobject slot `+0x78` → PAF `+0x11a5c8` → `+0xe47ac` |
| Parent pointer | Node `+0x1d4` |
| Parent child vectors | `+0x1b4` and `+0x1d8`; pointer/count/capacity triples |
| Position / scale | Node `+0x220` / `+0x230` |
| Plane visibility flag | Node byte `+0x1fd`; not page visibility |
| Text destructor/free | Slot `+0x0c` → PAF `+0x159004` |
| Clock/hold/mute reflow | VSH `+0x31038`, float in `f12` |

The string setter takes `{pointer, character_count}`, excluding the terminator, and copies the UTF-16 data internally. The caller's temporary buffer need not survive asynchronous layout. Native destruction removes both parent registrations and may defer backend destruction; do not add a second free. Sony constructors contain unchecked internal allocations, so the plugin's 64 KiB preflight reduces memory pressure but cannot guarantee recovery.

### Locking, style and metrics

The clock callback runs with return address PAF `+0xdeac4` and the PAF lightweight mutex at `+0x190640` held by its thread. Dispatch follows `+0xe3104 → +0xdaad8 → +0xdec4c → +0xdea1c`; callback records begin at `node+0x1a0`, with function pointer at record `+0x30` and dispatch at `+0xdeabc`. The mutex workarea begins with lock level and owner thread ID.

Text style follows Sony's resource-loader sequence: transforms, color, dimensions, integer properties `0x0e/0x0f/0x25`, size `0x1c`, color records `0x26/0x27`, scalars `0x1d..0x21`, properties `0x22/0x23/0x24/0x2d` and records `0x2e/0x2f`. Vector records are passed by pointer; scalar float calls use the `f12` adapter in `src/vsh/abi.S`. Font contexts are constructed natively, not copied from the clock. Unnamed property IDs and the concrete font-file selection remain uninterpreted.

Sony's worker prepares the backend. Glyph advance flows through PAF `+0xe8d00 → +0xdc814`, selector 0 target `+0xd2ce8`; `+0xe4a30` applies the 1/64 scale and backend font scale. Backend fields are glyph width `+0x130`, native box `+0x120`, format `+0x144`, readiness `+0x148` and pending work `+0x188`. The count at `+0x148` is not a width. The plugin brackets metric reads with readiness checks and requires two stable samples.

The percentage's right anchor is X=236; the gap is 7 native layout units. Example native boxes for `9%`, `10%`, `99%` and `100%` are 25/36/36/47, with shifts 32/43/43/54. These examples must not replace measurement or be treated as display-pixel dimensions. Verified unshifted clock reset positions are X=203 or X=235, depending on battery visibility.

Discovery uses KUBridge's `0xa0`-byte SceModule2 descriptor: text base/size at `+0x6c/+0x70`, segment addresses/sizes at `+0x80/+0x90`. Expected PAF/VSH text sizes are `0x18c518/0x556c0`; six mapping checks yield `0x3f`. ARK APIs report 4/20/69, not r206. The observed 6.61 user devkit value is `0x06060010`; native signatures remain necessary.

## GAME HOME interfaces

The zero-base `impose_02g` image SHA-256 is `995e9ecbab57c90090a9e097983cd2975bdb413ad1d8d1969e7d88a34e7ad291`. Its text size is `0xa1c8`, the second segment starts at `+0xa1d0`, and the image size is `0xa598`.

| Interface or structure | Module/state offset |
| --- | --- |
| State global / expected state | Module `+0xa1d0` / `+0xa220` |
| Dispatch / callback slot / original callback | Module `+0x894/+0x898` / state `+0x1bc` / module `+0x4790` |
| Bar composition call / routine | Module `+0x47b4` / `+0x6a1c` |
| FPL ID / cached allocation / uncached draw alias | State `+0x10/+0x14/+0x1b8` |
| Stride / height | State `+0x18/+0x1c`; exactly 512 / 272 |
| Scene / cache flags / native left boundary | State `+0xa4/+0xb8/+0xd0` |
| Vertical offset / transition | State `+0x158/+0x170` |

The allocation is one occupied 512×272×2-byte FPL block in PSP-2000 extra RAM. Its draw address must be the exact uncached alias, not a guessed VRAM address. Visible width is 480, not stride 512. The native battery occupies x=450..477; plugin composition is bounded to x=250..477, y=5..21 and preserves odd alignment columns.

All 175 records in `src/home/signatures/` are required: dispatch 57, return 18, draw/allocation 40, cache 16 and event path 44. A firmware version match does not authenticate these interfaces.

Cache bit 0 selects the native full rebuild at `+0x6a7c`; `+0x6b98..+0x6ba8` publishes completion and battery invalidation. Partial battery updates require exact canonical restoration before Sony runs. Do not force full redraws: the result from `+0x6a1c` budgets other HOME work at `+0x47d0`.

The ownership regression covers `3bf → 3b9 → 3bb → 3bf → 33f → 3bf` and a direct `3bb → 33f` return. Residual presentation must be restored before the partial battery copy. Recovery rules are in [architecture](architecture.md#pixel-ownership-and-recovery); executable regressions are in `tests/c/home_recovery.c`.

### Assets and sprite reference

Startup accepts only these fixed files, checking their exact sizes and SHA-1 before decoding. An extra read rejects trailing bytes. SHA-256 values below are the offline references.

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `impose.rsc` | 113676 | `504a9327fc845ba449f7494d90d857096b3d2020d1501c45a127031388194f5e` |
| `ltn8.pgf` | 41000 | `3c842878632fae835f78f83aee6f74a91d255fc5fdb32b163340033645e6b17f` |

Resource table entry 25 points to the 4800-byte digit atlas. Digits are copied without raster changes. The bounded revision-2 PGF reader extracts the original 11×11 `%` and bottom-aligns it with the digit foreground.

`src/home/sprite.c` applies a compact shadow, flattens overlaps and leaves one blank bright column between the digits and percent. The percent shadow uses a 3×3 box centered at (+1,+2), opacity 991386/1000000, clipped to the 16×15 tile. This matches the approved sprite reference; it is not a reconstruction of Sony's shadow algorithm or the PGF companion shadow.

The approved 0..100% series SHA-256 is `20d3a7efb382d548dccc507a7827a20259b866259bf63c24b8e3ba0fb778cb34`. The series concatenates little-endian percent/width pairs and the SHA-1 of each complete 960-word sprite. `verify_assets.py` checks all 101 results. This is a pixel regression check, not optical validation.

## Embedded user-loader ABI

Use `sceKernelLoadModuleBufferForKernel(size, buffer, flags, option)`. The pinned SDK's generic `sceKernelLoadModuleBuffer` declaration reverses the firmware's first two arguments. Sony `modulemgr.prx`, SHA-256 `ea80b96d82d897d15774658e209d2a3a1c26c730a3b3f9b9aa49e668d180179a`, export NID `4e62c48a`, confirms size in `a0` and buffer in `a1`.

Preserve user partitions and parent ownership of the loaded child. Linking that renderer into the kernel is not equivalent to loading it for user-mode PAF execution.

## References

- [PSPSDK power API](https://github.com/pspdev/pspsdk/blob/master/src/power/psppower.h)
- [ARK KUBridge](https://github.com/PSP-Archive/ARK-4/blob/main/core/systemctrl/src/kubridge.c)
- [ARK xmbctrl](https://github.com/PSP-Archive/ARK-4/blob/main/extras/modules/xmbctrl/main.c)
- [DayViewer](https://github.com/PSP-Archive/Dayviewer/blob/main/user/main.c), a clock-hook reference rather than this plugin's independent-text design
- [RCOMage resource reader](https://github.com/kakaroto/RCOMage/blob/master/src/rcoreader.c)
- [pspdecrypt LZR](https://github.com/John-K/pspdecrypt/blob/1.0/libLZR.c)
- [PPSSPP Rel2 reader](https://github.com/hrydgard/ppsspp/blob/master/Core/ELF/ElfReader.cpp)
