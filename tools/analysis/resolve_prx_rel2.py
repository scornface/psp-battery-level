#!/usr/bin/env python3
"""Apply PSP PT_PSPREL2 relocations to a local ELF32 MIPS PRX analysis image."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from common import verified_source, outputs, Prx


PT_LOAD = 1
PT_PSPREL2 = 0x700000A1
TYPE_NAMES = {
    0: "NONE",
    1: "LO16_ALT",
    2: "32",
    3: "26",
    4: "HI16",
    5: "LO16",
    6: "J26",
    7: "JAL26",
}


@dataclass(frozen=True)
class ProgramHeader:
    index: int
    kind: int
    offset: int
    vaddr: int
    paddr: int
    filesz: int
    memsz: int
    flags: int
    align: int


class Cursor:
    def __init__(self, data: bytes, description: str):
        self.data = data
        self.pos = 0
        self.description = description

    def take(self, size: int) -> bytes:
        if size < 0 or self.pos + size > len(self.data):
            raise ValueError(f"truncated {self.description} at +0x{self.pos:x}")
        result = self.data[self.pos : self.pos + size]
        self.pos += size
        return result

    def u8(self) -> int:
        return self.take(1)[0]

    def u16(self) -> int:
        return struct.unpack("<H", self.take(2))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.take(4))[0]


def decode_prx(path: Path, load_base: int) -> tuple[bytearray, list[ProgramHeader], list[str], dict[str, object]]:
    if load_base != 0:
        raise ValueError("Only zero-base research images are supported")
    elf = verified_source(path)
    Prx.parse(elf)  # Validate loads, image bounds and ELF identity before allocation.
    if len(elf) < 52 or elf[:4] != b"\x7fELF":
        raise ValueError("input is not an ELF file")
    if elf[4:6] != b"\x01\x01":
        raise ValueError("expected ELF32 little-endian input")

    header = struct.unpack_from("<16sHHIIIIIHHHHHH", elf, 0)
    _, elf_type, machine, _, entry, phoff, shoff, flags, ehsize, phentsize, phnum, shentsize, shnum, _ = header
    if machine != 8:
        raise ValueError(f"expected MIPS machine (8), got {machine}")
    if phentsize < 32 or phoff + phentsize * phnum > len(elf):
        raise ValueError("invalid or truncated program-header table")

    phdrs: list[ProgramHeader] = []
    for i in range(phnum):
        values = struct.unpack_from("<IIIIIIII", elf, phoff + i * phentsize)
        phdrs.append(ProgramHeader(i, *values))

    loads = [p for p in phdrs if p.kind == PT_LOAD]
    relocs = [p for p in phdrs if p.kind == PT_PSPREL2]
    if not loads or len(relocs) != 1:
        raise ValueError(f"expected PT_LOAD and exactly one PT_PSPREL2; got {len(loads)} and {len(relocs)}")

    image_end = max(p.vaddr + p.memsz for p in loads)
    image = bytearray(image_end)
    for p in loads:
        if p.offset + p.filesz > len(elf) or p.filesz > p.memsz:
            raise ValueError(f"invalid PT_LOAD segment {p.index}")
        image[p.vaddr : p.vaddr + p.filesz] = elf[p.offset : p.offset + p.filesz]

    reloc_segment = relocs[0]
    if reloc_segment.offset + reloc_segment.filesz > len(elf):
        raise ValueError("PT_PSPREL2 segment extends past end of PRX")
    cur = Cursor(elf[reloc_segment.offset : reloc_segment.offset + reloc_segment.filesz], "PT_PSPREL2")
    if cur.u16() != 0:
        raise ValueError("PT_PSPREL2 reserved prefix is nonzero")
    flag_bits = cur.u8()
    type_bits = cur.u8()
    seg_bits = max(1, (reloc_segment.index - 1).bit_length())
    if not flag_bits or not type_bits or flag_bits + type_bits + seg_bits > 16:
        raise ValueError(f"invalid Rel2 bit widths: flag={flag_bits} type={type_bits} segment={seg_bits}")

    flag_table_size = cur.u8()
    if not flag_table_size:
        raise ValueError("empty Rel2 flag table")
    flag_table = bytes([flag_table_size]) + cur.take(flag_table_size - 1)
    type_table_size = cur.u8()
    if not type_table_size:
        raise ValueError("empty Rel2 type table")
    type_table = bytes([type_table_size]) + cur.take(type_table_size - 1)

    segment_vaddrs = {p.index: load_base + p.vaddr for p in loads}
    rel_base = 0
    off_segment = 0
    lo16 = 0
    last_type = -1
    counts: collections.Counter[int] = collections.Counter()
    base_records = 0
    reloc_records: list[str] = []
    command_count = 0

    while cur.pos < len(cur.data):
        cmd = cur.u16()
        command_count += 1
        flag_index = cmd & ((1 << flag_bits) - 1)
        segment = (cmd >> flag_bits) & ((1 << seg_bits) - 1)
        type_index = (cmd >> (flag_bits + seg_bits)) & ((1 << type_bits) - 1)
        if flag_index >= len(flag_table) or type_index >= len(type_table):
            raise ValueError(f"Rel2 command {command_count}: table index out of range")
        flag = flag_table[flag_index]
        reloc_type = type_table[type_index]

        if not flag & 1:
            off_segment = segment
            if flag & 0x06 == 0:
                rel_base = cmd >> (seg_bits + flag_bits)
            elif flag & 0x06 == 0x04:
                rel_base = cur.u32()
            else:
                raise ValueError(f"Rel2 command {command_count}: invalid base flag 0x{flag:x}")
            base_records += 1
            continue

        if segment not in segment_vaddrs or off_segment not in segment_vaddrs:
            raise ValueError(
                f"Rel2 command {command_count}: references unloaded segment offset={off_segment}, target={segment}"
            )

        shift = type_bits + seg_bits + flag_bits
        encoded = cmd >> shift
        encoded_bits = 16 - shift
        if cmd & 0x8000:
            encoded -= 1 << encoded_bits
        if flag & 0x06 == 0:
            rel_base += encoded
        elif flag & 0x06 == 0x02:
            rel_base += (encoded << 16) | cur.u16()
        elif flag & 0x06 == 0x04:
            rel_base = cur.u32()
        else:
            raise ValueError(f"Rel2 command {command_count}: invalid relocation flag 0x{flag:x}")

        patch_va = rel_base + segment_vaddrs[off_segment]
        patch_offset = patch_va - load_base
        selected = next(p for p in loads if p.index == off_segment)
        if rel_base < 0 or rel_base + 4 > selected.memsz or patch_offset & 3:
            raise ValueError(f"Rel2 command {command_count}: patch address 0x{patch_va:08x} is outside image")

        lo_kind = flag & 0x38
        if lo_kind == 0:
            lo16 = 0
        elif lo_kind == 0x08:
            if last_type != 4:
                lo16 = 0
        elif lo_kind == 0x10:
            lo16 = cur.u16()
            if lo16 & 0x8000:
                lo16 -= 0x10000
        else:
            raise ValueError(f"Rel2 command {command_count}: invalid LO16 mode 0x{flag:x}")

        op = struct.unpack_from("<I", image, patch_offset)[0]
        before = op
        relocate_to = segment_vaddrs[segment]
        if reloc_type == 0:
            pass
        elif reloc_type == 2:  # R_MIPS_32
            op = (op + relocate_to) & 0xFFFFFFFF
        elif reloc_type in (3, 6, 7):  # R_MIPS_26 / PSP J26 / PSP JAL26
            op = (op & 0xFC000000) | (((op & 0x03FFFFFF) + (relocate_to >> 2)) & 0x03FFFFFF)
            if reloc_type == 6:
                op = (op & 0x03FFFFFF) | 0x08000000
            elif reloc_type == 7:
                op = (op & 0x03FFFFFF) | 0x0C000000
        elif reloc_type == 4:  # R_MIPS_HI16
            address = (((op & 0xFFFF) << 16) + lo16 + relocate_to) & 0xFFFFFFFF
            if address & 0x8000:
                address = (address + 0x10000) & 0xFFFFFFFF
            op = (op & 0xFFFF0000) | ((address >> 16) & 0xFFFF)
        elif reloc_type in (1, 5):  # LO16 variants
            op = (op & 0xFFFF0000) | ((op + relocate_to) & 0xFFFF)
        else:
            raise ValueError(f"Rel2 command {command_count}: unsupported relocation type {reloc_type}")

        struct.pack_into("<I", image, patch_offset, op)
        counts[reloc_type] += 1
        reloc_records.append(
            f"{command_count}\t{patch_va:08x}\t{TYPE_NAMES.get(reloc_type, str(reloc_type))}\t"
            f"{off_segment}\t{segment}\t{flag:02x}\t{before:08x}\t{op:08x}"
        )
        last_type = reloc_type

    report = {
        "input_sha256": hashlib.sha256(elf).hexdigest(),
        "elf_type": elf_type,
        "entry": entry,
        "elf_flags": flags,
        "section_table": {"offset": shoff, "entry_size": shentsize, "count": shnum},
        "load_base": load_base,
        "image_size": len(image),
        "reloc_segment_index": reloc_segment.index,
        "reloc_segment_size": reloc_segment.filesz,
        "rel2_header": {"flag_bits": flag_bits, "type_bits": type_bits, "segment_bits": seg_bits},
        "command_count": command_count,
        "base_commands": base_records,
        "relocations_by_type": {TYPE_NAMES.get(k, str(k)): v for k, v in sorted(counts.items())},
        "relocation_records": reloc_records,
    }
    return image, phdrs, reloc_records, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("image", type=Path, help="destination for the relocated memory image")
    parser.add_argument("report", type=Path, help="destination for the relocation report")
    args = parser.parse_args()

    try:
        manifest_path = args.image.with_suffix(args.image.suffix + ".json")
        outputs(args.input, args.image, args.report, manifest_path)
        image, phdrs, records, report = decode_prx(args.input, 0)
    except (OSError, ValueError, struct.error) as exc:
        raise SystemExit(f"error: {exc}") from exc

    args.image.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.image.open("xb") as output:
        output.write(image)
    report_lines = [
        f"input={args.input}",
        f"input_sha256={report['input_sha256']}",
        f"elf_type=0x{report['elf_type']:x} entry=0x{report['entry']:08x} flags=0x{report['elf_flags']:08x}",
        f"section_table=off:0x{report['section_table']['offset']:x} count:{report['section_table']['count']}",
        f"load_base=0x{report['load_base']:08x} image_size=0x{report['image_size']:x}",
        f"PT_PSPREL2=index:{report['reloc_segment_index']} size:0x{report['reloc_segment_size']:x}",
        f"Rel2_bits=flag:{report['rel2_header']['flag_bits']} type:{report['rel2_header']['type_bits']} segment:{report['rel2_header']['segment_bits']}",
        f"commands={report['command_count']} base_commands={report['base_commands']} relocations={len(records)}",
        "relocations_by_type=" + ", ".join(f"{k}:{v}" for k, v in report["relocations_by_type"].items()),
        "",
        "command\tpatch_va\ttype\toffset_segment\ttarget_segment\tflag\tbefore\tafter",
        *records,
    ]
    with args.report.open("x", encoding="utf-8") as output:
        output.write("\n".join(report_lines) + "\n")
    with manifest_path.open("x", encoding="utf-8") as output:
        output.write(json.dumps({
            "input_sha256": report["input_sha256"], "image_sha256": hashlib.sha256(image).hexdigest(),
            "load_base": 0,
        }, indent=2) + "\n")
    print("\n".join(report_lines[:9]))
    print(f"image={args.image}")
    print(f"report={args.report}")


if __name__ == "__main__":
    main()
