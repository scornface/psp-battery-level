#!/usr/bin/env python3
"""Inspect selected RVA ranges and direct callers in the local relocated PAF."""

import argparse
from common import ROOT, analysis_module, capstone_module, external_directory, run


def instruction_range(value):
    try:
        start, end = (int(s, 0) for s in value.split(":"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected START:END instruction addresses") from exc
    if start < 0 or start & 3 or end & 3 or end <= start:
        raise argparse.ArgumentTypeError("Expected an aligned, increasing instruction range")
    return start, end


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", choices=("paf", "vshmain"), default="paf")
    parser.add_argument(
        "--range", action="append", default=[], type=instruction_range, metavar="START:END"
    )
    parser.add_argument("--caller", action="append", default=[], type=lambda s: int(s, 0))
    parser.add_argument("--import-stub", action="append", default=[], type=lambda s: int(s, 0))
    parser.add_argument(
        "--field",
        action="append",
        default=[],
        type=lambda s: int(s, 0),
        help="Find memory accesses to an offset in node/event code",
    )
    parser.add_argument("--word", action="append", default=[], type=lambda s: int(s, 0))
    args = parser.parse_args()
    capstone = capstone_module()
    module = analysis_module(
        external_directory("PSP_FIRMWARE_ROOT") / f"F0/vsh/module/{args.module}.prx",
        ROOT / f"build/analysis/{args.module}.relocated.bin",
    )
    image = module.image
    for address in args.word:
        if address < 0 or address + 4 > len(image):
            parser.error(f"Word outside image: {address:#x}")
        print(f"word {address:#x} = {int.from_bytes(image[address : address + 4], 'little'):#x}")
    if args.import_stub:
        for library in module.imports():
            for nid, stub in zip(library["nids"], library["stubs"]):
                if stub in args.import_stub:
                    print(f"import {library['name']} stub={stub:#x} NID={nid:#x}")
    md = capstone.Cs(
        capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS32 | capstone.CS_MODE_LITTLE_ENDIAN
    )
    if args.field:
        md.detail = True
        start, end = (0xDB000, 0xEF000) if args.module == "paf" else (0, 0x3F000)
        for address in range(start, end, 4):
            for ins in md.disasm(image[address : address + 4], address):
                if any(
                    op.type == capstone.CS_OP_MEM and op.mem.disp in args.field
                    for op in ins.operands
                ):
                    print(f"{ins.address:08x}: {ins.mnemonic:8} {ins.op_str}")
    for start, end in args.range:
        module.require_range(start, end - start, executable=True)
        for address in range(start, end, 4):
            decoded = list(md.disasm(image[address : address + 4], address))
            if decoded:
                ins = decoded[0]
                print(f"{ins.address:08x}: {ins.mnemonic:8} {ins.op_str}")
            else:
                print(f"{address:08x}: <undecoded word>")
    if args.caller:
        # Decode each word independently: data/unsupported opcodes must not
        # terminate the scan. Results are candidates until code is inspected.
        for p in module.phdrs:
            if p[0] != 1 or not p[6] & 1:
                continue
            for address in range(p[2], p[2] + p[4] - 3, 4):
                word = int.from_bytes(image[address : address + 4], "little")
                if word >> 26 in (2, 3):
                    target = ((address + 4) & 0xF0000000) | ((word & 0x3FFFFFF) << 2)
                    if target in args.caller:
                        print(f"candidate caller {address:#x} -> {target:#x}")


if __name__ == "__main__":
    run(main)
