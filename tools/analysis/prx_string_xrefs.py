#!/usr/bin/env python3
"""Find MIPS LUI/low-immediate references to strings in a relocated PSP PRX."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from common import analysis_module, capstone_module, run
capstone_module()

from capstone import (  # noqa: E402
    CS_ARCH_MIPS,
    CS_MODE_LITTLE_ENDIAN,
    CS_MODE_MIPS32,
    CS_OP_IMM,
    CS_OP_REG,
    Cs,
)


def find_strings(image: bytes, pattern: re.Pattern[bytes]) -> dict[int, bytes]:
    strings: dict[int, bytes] = {}
    for match in re.finditer(rb"[\x20-\x7e]{4,}\x00", image):
        text = match.group()[:-1]
        if pattern.search(text):
            strings[match.start()] = text
    return strings


def signed16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prx", type=Path)
    parser.add_argument("relocated_image", type=Path)
    parser.add_argument("--pattern", default="battery|clock|charge|topmenu_plugin")
    parser.add_argument("--context", type=int, default=8)
    args = parser.parse_args()

    if not 0 <= args.context <= 32:
        parser.error("context must be between 0 and 32")
    module = analysis_module(args.prx, args.relocated_image)
    phdrs, image = module.phdrs, module.image
    strings = find_strings(image, re.compile(args.pattern.encode("ascii"), re.IGNORECASE))
    if not strings:
        print("no matching strings")
        return

    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    instructions = []
    for p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align in phdrs:
        if p_type == 1 and p_flags & 1:
            for address in range(p_vaddr, p_vaddr + p_filesz - 3, 4):
                instructions.extend(md.disasm(image[address:address + 4], address))
    address_to_string = {address: text for address, text in strings.items()}

    matches: list[tuple[int, int, bytes]] = []
    for i, insn in enumerate(instructions):
        if insn.mnemonic != "lui" or len(insn.operands) < 2:
            continue
        if insn.operands[0].type != CS_OP_REG or insn.operands[1].type != CS_OP_IMM:
            continue
        source_reg = insn.operands[0].reg
        high = (insn.operands[1].imm & 0xFFFF) << 16
        previous_address = insn.address
        for low_insn in instructions[i + 1 : i + 9]:
            if low_insn.address != previous_address + 4 or low_insn.address - insn.address > 32:
                break
            previous_address = low_insn.address
            if low_insn.group(1) or low_insn.group(2) or low_insn.mnemonic in ("jr", "jalr"):
                break
            if low_insn.mnemonic not in ("addiu", "addi", "ori") or len(low_insn.operands) < 3:
                if low_insn.mnemonic not in ("sw", "sh", "sb", "swl", "swr", "sdc1", "swc1") \
                        and low_insn.operands and low_insn.operands[0].type == CS_OP_REG \
                        and low_insn.operands[0].reg == source_reg:
                    break
                continue
            if any(op.type != CS_OP_REG for op in low_insn.operands[:2]):
                continue
            if low_insn.operands[1].reg != source_reg or low_insn.operands[2].type != CS_OP_IMM:
                continue
            imm = low_insn.operands[2].imm & 0xFFFF
            address = (
                (high | imm) if low_insn.mnemonic == "ori" else (high + signed16(imm))
            ) & 0xFFFFFFFF
            if address in address_to_string:
                matches.append((insn.address, low_insn.address, address_to_string[address]))
            if low_insn.operands[0].reg == source_reg:
                break

    if not matches:
        print("no LUI+low-immediate matches for selected strings")
        print("strings:")
        for address, text in strings.items():
            print(f"  {address:08x} {text.decode('ascii', 'replace')}")
        return

    insn_by_address = {insn.address: index for index, insn in enumerate(instructions)}
    for lui_addr, low_addr, text in matches:
        print(f"candidate xref {lui_addr:08x}/{low_addr:08x} -> {text.decode('ascii', 'replace')!r}")
        center = insn_by_address[lui_addr]
        start = max(0, center - args.context)
        end = min(len(instructions), insn_by_address[low_addr] + args.context + 1)
        for insn in instructions[start:end]:
            marker = ">" if insn.address in (lui_addr, low_addr) else " "
            print(f" {marker} {insn.address:08x}: {insn.mnemonic:8} {insn.op_str}")


if __name__ == "__main__":
    run(main)
