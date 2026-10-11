# Native XMB interface: evidence and reproduction

This is a technical reference, not a development diary. Runtime design is in
[architecture.md](architecture.md); host setup is in [dependencies.md](dependencies.md).
All offsets below are **module-relative addresses for standard Sony 6.61**.
Always discover current module bases before using them.

## Inputs and resource layout

Analysis used the standard non-Go Sony 6.61 updater (MD5
`6be8878f475ac5b1a499b95ab2f7d301`) extracted locally with pspdecrypt 1.0:

```sh
.deps/pspdecrypt-1.0/pspdecrypt -A -O data/ofw-661 data/661/EBOOT.PBP
```

No flash0 modification was used. Firmware copies are local, not distributed.
The status objects are in `system_plugin_fg.rco`, page `page_indicator`:

| Object | Native definition |
| --- | --- |
| `Plane battery` | Position (223,124), dimensions 44×16 |
| `Plane battery_shadow` | Position (225,122), dimensions 44×16 |
| `Text clock` | Position (203,123), text size 7.6, icon offset 2 |

There is no percentage Text in the resource. `clock`'s RCO string is a placeholder;
VSH formats its actual UTF-16 date/time at runtime. The percentage uses separate
PAF Text instances, not a font imitation or a replacement date/time string.
The battery texture has four stacked 44×16 slices. `OnChargeBattery` and resource
animations update Sony's icon; connecting DC, the charging API flag and visual
animation are distinct observations. Property ID `0x17` was traced through the
Plane backend, but its full semantics are not established and it is not hooked.

The RCO RLZ metadata begins at `0xa4` (three words); payload starts at `0xb0`.
`system_plugin_fg.rco` SHA-256:
`3da2042c7042faf1d810c970bdb500ce812ea31e548ee9d0d17e57483c1c71dd`.
Its table decoder consumes `0x5f5` bytes and produces `0x20ac` bytes, SHA-256
`8983cb43c0bc17c9fa443a951191ab592c9834368c712f6b1c78052dba78fae3`.

## Creation, registration and update chain

VSH `+0x35a64` creates the indicator page using PAF NID `0x3876721b`.
Lookups at `+0x35a94/+0x35aac/+0x35ac4` (NID `0xb94ad2a4`) resolve battery,
shadow and clock into globals `+0x5caac/+0x5cab0/+0x5cab4`. Clock event 100 is
registered at `+0x35bc4`, with callback `+0x30ba8` and native float argument 1000.
The plugin preserves that original callback and the layout handler `+0x3113c`.

| Interface / structure | Verified address or offset |
| --- | --- |
| Text allocation / constructor | PAF `+0x13a4e0` / `+0x105aa0`, node size `0x340` |
| Text / Page / Plane vtable | PAF `+0x18b578` / `+0x18b218` / `+0x18b068` |
| Text string setter | Node vtable `+0xb4` → PAF `+0x105e20` |
| Text subobject | Node `+0x1e8`; vtable PAF `+0x18c118`, size `0x20` |
| Backend pointer / size | Subobject `+0x1c` / `0x1c0` |
| Backend string setter | Subobject slot `+0x78` → PAF `+0x11a5c8` → `+0xe47ac` |
| Parent pointer | Node `+0x1d4` |
| Parent child vectors | `+0x1b4` and `+0x1d8`: pointer/count/capacity triples |
| Position / scale | Node `+0x220` / `+0x230` |
| Plane visibility flag | Node byte `+0x1fd`; not page-level visibility |
| Full Text destructor/free | Slot `+0x0c` → PAF `+0x159004` |
| Native clock/hold/mute reflow | VSH `+0x31038`, float in `f12` |

The UTF-16 descriptor is `{pointer, character_count}`, excluding the terminator.
The native setter copies string storage internally; the temporary caller buffer
need not survive asynchronous layout. Native destruction removes both parent
registrations and may defer backend destruction; never add a manual second free.
Sony constructors have unchecked internal allocations: the plugin's 64 KiB free
memory preflight reduces pressure but does not guarantee allocation recovery.

## Serialization, style and metrics

The clock callback was observed with return address PAF `+0xdeac4` and the
PAF lightweight mutex `+0x190640` held by the callback's thread. The dispatcher
chain `+0xe3104 → +0xdaad8 → +0xdec4c → +0xdea1c` traverses callback records
at `node+0x1a0`; function pointer is at record `+0x30`, dispatch at `+0xdeabc`.
The mutex workarea starts with lock level and owner thread ID. Installation
also guards its mapped range; callbacks verify ownership and clock/page identity.

Style follows the native RCO loader sequence, not just its 7.6 size: transforms,
color, dimensions, integer properties `0x0e/0x0f/0x25`, size `0x1c`, color records
`0x26/0x27`, scalars `0x1d..0x21`, properties `0x22/0x23/0x24/0x2d` and records
`0x2e/0x2f`. Unnamed IDs retain observed ABI values; do not invent semantics.
Vector records are passed by pointer; scalar float calls require the `f12`
adapter in `src/abi.S`. Font contexts are constructed natively, never copied
from the clock. Concrete font-file selection is not identified.

Backend preparation runs on Sony's own worker. Glyph advance flows through
PAF `+0xe8d00 → +0xdc814`, selector 0 target `+0xd2ce8`; `+0xe4a30` applies
the 1/64 scale and backend font scale. Glyph width is at backend `+0x130`;
the native box at `+0x120`, format at `+0x144`, readiness at `+0x148`, pending
work at `+0x188`. The count at `+0x148` is not itself a width. The plugin checks
these together and requires two stable width/box samples before commit. Repeated
reads reject observed changes; Sony's full publication protocol remains unproven.

Hardware Text trials exercised `9% → 10% → 99% → 100%`: native boxes
25/36/36/47 and shifts 32/43/43/54 respectively. Text right anchor is X=236;
gap is 7 native layout units. Do not replace measurement with those example
constants or equate internal units/timestamps with display pixels/frame timing.

Discovery uses KUBridge's `0xa0`-byte SceModule2 descriptor: text base/size at
`+0x6c/+0x70`, segment addresses/sizes at `+0x80/+0x90`. Expected PAF/VSH text
sizes are `0x18c518/0x556c0`; six mapping checks yield `0x3f`. ARK version APIs
report 4/20/69 but do not expose r206; instruction, vtable and geometry guards
remain essential. The observed 6.61 user devkit value is `0x06060010`.

## Implementation notes

- **Clock reset:** Sony can reset the clock after native size notifications.
  Recognize only verified baseline positions (203 or 235, depending on battery
  visibility), then reflow from baseline. Do not repeatedly subtract from live X.
- **DC recovery:** invalid power samples can briefly hide the percentage. Keep
  the front's string/box and restore without setter/warmup.
- **USB timeout:** the indicator page may be hidden while the battery Plane flag
  remains set. Query USB state from the verified update callback, pause metric
  preparation/commit, and reset its wait budget. Outside USB, retain the bounded
  readiness timeout; retry terminal diagnostic snapshots after USB.

## Reproduction and references

```sh
python3 tools/analysis/resolve_prx_rel2.py data/ofw-661/F0/vsh/module/paf.prx build/analysis/paf.relocated.bin build/analysis/paf.relocations.tsv
python3 tools/prx_libraries.py data/ofw-661/F0/vsh/module/paf.prx --relocated-image build/analysis/paf.relocated.bin
python3 tools/analysis/inspect_paf.py --range 0x105aa0:0x105b80
python3 tools/analysis/decompress_rco_rlz.py data/ofw-661/F0/vsh/resource/system_plugin_fg.rco build/analysis/system_plugin_fg_tables.bin
python3 tools/analysis/dump_rco.py data/ofw-661/F0/vsh/resource/system_plugin_fg.rco build/analysis/system_plugin_fg.xml
```

Repeat relocation for `vshmain`/`dialogmain` when inspecting their callsites.
The current analysis image hashes are:

| Decrypted PRX | SHA-256 |
| --- | --- |
| `paf.prx` | `699413b667199732af0b3cc2379ea65df0c4e2daa7727c6d1bbb757df0160417` |
| `vshmain.prx` | `dd283103f78db14a8bd08c8aa03ecc01807850baed54fb77b3c38ba7ffff712f` |
| `dialogmain.prx` | `c3602b6c63f559318af51390bff21babbd68371cf505e6dffa20ad670ee86578` |

References: [PSPSDK power](https://github.com/pspdev/pspsdk/blob/master/src/power/psppower.h),
[ARK KUBridge](https://github.com/PSP-Archive/ARK-4/blob/main/core/systemctrl/src/kubridge.c),
[ARK xmbctrl](https://github.com/PSP-Archive/ARK-4/blob/main/extras/modules/xmbctrl/main.c),
[DayViewer XMB](https://github.com/PSP-Archive/Dayviewer/blob/main/user/main.c),
[RCOMage RCO reader](https://github.com/kakaroto/RCOMage/blob/master/src/rcoreader.c),
[pspdecrypt LZR](https://github.com/John-K/pspdecrypt/blob/1.0/libLZR.c), and
[PPSSPP Rel2 reader](https://github.com/hrydgard/ppsspp/blob/master/Core/ELF/ElfReader.cpp).
DayViewer replaces the clock formatting; it is a hook reference, not this
plugin's native independent-text/layout implementation.
