#!/usr/bin/env python3
"""Authenticate the maintained HOME guards against the exact Sony 6.61 image."""
import re
import struct
import sys
from common import ROOT, external_directory, run
from resolve_prx_rel2 import decode_prx

DRAW_OFFSETS = {
    0x5d4,0x5f4,0x5f8,0x5fc,0x600,0x604,0x608,0x614,0x61c,0x620,
    0x628,0x62c,0x630,0x638,0x650,0x654,0x1fa8,0x1fac,0x1fcc,0x1fd0,
    0x1fe0,0x1fe4,0x1fe8,0x1ff0,0x1ff4,0x1ffc,0x2004,0x256c,0x2570,0x2574,
    0x6a88,0x6a98,0x6aa0,0x6aa4,0x7e54,0x7e58,0x7e5c,0x7e60,0x7e64,0x7e68,
}


def main():
    source = external_directory("PSP_FIRMWARE_ROOT") / "F0/kd/impose_02g.prx"
    image, _, report, _ = decode_prx(source, 0)
    relocations = {int(f[1], 16): f[2] for f in (line.split("\t") for line in report[11:])}
    kinds = {"NONE":0,"LO16":1,"HI16":2,"J26":3,"JAL26":3}
    groups = []
    if len(sys.argv) != 1:raise ValueError('This verifier has no candidate modes')
    names=["src/home/signatures/dispatch.h", "src/home/signatures/return.h", "src/home/signatures/draw.h",
           "src/home/signatures/cache.h", "src/home/signatures/event.h"]
    for name in names:
        groups.append([tuple(int(v,0) for v in fields) for fields in re.findall(
            r"\{(0x[0-9a-f]+), (0x[0-9a-f]+), ([0-3]), (0x[0-9a-f]+|0)\}", (ROOT/name).read_text())])
    if len(groups[0]) != 57 or len(groups[1]) != 18 or len(groups[2]) != 40 \
            or {s[0] for s in groups[2]} != DRAW_OFFSETS:
        raise ValueError("Incomplete or duplicate HOME signatures")
    if len(groups)>=4 and (len(groups[3])!=16 or {s[0] for s in groups[3]}!={
        0x6a30,0x6a34,0x6a38,0x6a3c,0x6a40,0x6a6c,0x6a7c,0x6a80,
        0x6b90,0x6b94,0x6b98,0x6b9c,0x6ba0,0x6ba4,0x6ba8,0x6bb0}):
        raise ValueError('Incomplete native cache signatures')
    if len(groups)>=5 and (len(groups[4])!=44 or {s[0] for s in groups[4]} !=
            set(range(0x4790,0x47d8,4)) | set(range(0x4b14,0x4b24,4)) |
            set(range(0x6a44,0x6a7c,4)) | set(range(0x8da4,0x8dbc,4)) | {0x8f34,0x8f38}):
        raise ValueError('Incomplete native event-path signatures')
    for offset,word,kind,target in sum(groups, []):
        if struct.unpack_from("<I",image,offset)[0] != word \
                or kinds.get(relocations.get(offset,"NONE")) != kind:
            raise ValueError(f"HOME signature mismatch at +{offset:x}")
        expected = 0xa220 if offset == 0x1d50 else 0x3a68 if offset == 0x2118 else 0xa1d0
        if kind == 2 and target != expected:
            raise ValueError("Unexpected HOME HI16 target")
    print(f"Authenticated HOME native guards passed: {sum(map(len,groups))} exact words and relocation kinds")


if __name__ == "__main__":
    run(main)
