#!/usr/bin/env python3
"""Authenticate the maintained HOME guards against the exact Sony 6.61 image."""

import re
import struct
import argparse
from common import ROOT, external_directory, run
from resolve_prx_rel2 import decode_prx

DRAW_OFFSETS = {
    0x5D4,
    0x5F4,
    0x5F8,
    0x5FC,
    0x600,
    0x604,
    0x608,
    0x614,
    0x61C,
    0x620,
    0x628,
    0x62C,
    0x630,
    0x638,
    0x650,
    0x654,
    0x1FA8,
    0x1FAC,
    0x1FCC,
    0x1FD0,
    0x1FE0,
    0x1FE4,
    0x1FE8,
    0x1FF0,
    0x1FF4,
    0x1FFC,
    0x2004,
    0x256C,
    0x2570,
    0x2574,
    0x6A88,
    0x6A98,
    0x6AA0,
    0x6AA4,
    0x7E54,
    0x7E58,
    0x7E5C,
    0x7E60,
    0x7E64,
    0x7E68,
}


def verify(image, records, groups):
    # decode_prx already returns relocation records without the TSV file header.
    relocations = {}
    for record in records:
        fields = record.split("\t")
        if len(fields) != 8:
            raise ValueError("Malformed relocation record")
        offset = int(fields[1], 16)
        if offset in relocations:
            raise ValueError("Duplicate relocation address")
        relocations[offset] = fields[2]
    kinds = {"NONE": 0, "LO16": 1, "HI16": 2, "J26": 3, "JAL26": 3}
    if len(groups) != 5 or tuple(map(len, groups)) != (57, 18, 40, 16, 44):
        raise ValueError("Incomplete or duplicate HOME signatures")
    if (
        any(len({s[0] for s in group}) != len(group) for group in groups)
        or {s[0] for s in groups[2]} != DRAW_OFFSETS
    ):
        raise ValueError("Incomplete or duplicate HOME signatures")
    if {s[0] for s in groups[3]} != {
        0x6A30,
        0x6A34,
        0x6A38,
        0x6A3C,
        0x6A40,
        0x6A6C,
        0x6A7C,
        0x6A80,
        0x6B90,
        0x6B94,
        0x6B98,
        0x6B9C,
        0x6BA0,
        0x6BA4,
        0x6BA8,
        0x6BB0,
    }:
        raise ValueError("Incomplete native cache signatures")
    if {s[0] for s in groups[4]} != (
        set(range(0x4790, 0x47D8, 4))
        | set(range(0x4B14, 0x4B24, 4))
        | set(range(0x6A44, 0x6A7C, 4))
        | set(range(0x8DA4, 0x8DBC, 4))
        | {0x8F34, 0x8F38}
    ):
        raise ValueError("Incomplete native event-path signatures")
    for offset, word, kind, target in sum(groups, []):
        if (
            struct.unpack_from("<I", image, offset)[0] != word
            or kinds.get(relocations.get(offset, "NONE")) != kind
        ):
            raise ValueError(f"HOME signature mismatch at +{offset:x}")
        expected = 0xA220 if offset == 0x1D50 else 0x3A68 if offset == 0x2118 else 0xA1D0
        if kind == 2 and target != expected:
            raise ValueError("Unexpected HOME HI16 target")
    return sum(map(len, groups))


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    source = external_directory("PSP_FIRMWARE_ROOT") / "F0/kd/impose_02g.prx"
    image, _, records, _ = decode_prx(source, 0)
    groups = []
    for name in ("dispatch", "return", "draw", "cache", "event"):
        text = (ROOT / f"src/home/signatures/{name}.h").read_text()
        groups.append(
            [
                tuple(int(v, 0) for v in fields)
                for fields in re.findall(
                    r"\{(0x[0-9a-f]+), (0x[0-9a-f]+), ([0-3]), (0x[0-9a-f]+|0)\}", text
                )
            ]
        )
    count = verify(image, records, groups)
    print(f"Authenticated HOME native guards passed: {count} exact words and relocation kinds")


if __name__ == "__main__":
    run(main)
