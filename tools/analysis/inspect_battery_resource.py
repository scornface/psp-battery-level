#!/usr/bin/env python3
"""Inspect the standard 6.61 battery image locally without rewriting its RCO."""
import ctypes
import struct
import hashlib
from decompress_rco_rlz import ROOT, load_lzr, authenticated_resource


def main():
    rco = authenticated_resource(ROOT / "data/ofw-661/F0/vsh/resource/system_plugin_fg.rco")
    source = ctypes.create_string_buffer(rco[0x6a8:0xe37] + bytes(64))
    output = ctypes.create_string_buffer(4304)
    end = ctypes.c_void_p()
    size = load_lzr().LZRDecompress(output, len(output), source, ctypes.byref(end))
    if size != len(output) or end.value - ctypes.addressof(source) > 0xe37 - 0x6a8:
        raise SystemExit("Unexpected battery RLZ result")
    data = output.raw
    if data[:16] != b"MIG.00.1PSP\0\0\0\0\0":
        raise SystemExit("Unexpected GIM signature")
    # This exact standard resource: RGBA8888 palette, INDEX8 image, PSP swizzle.
    if struct.unpack_from("<HHHH", data, 0x44) != (3, 0, 256, 1) or \
            struct.unpack_from("<HHHHH", data, 0x494) != (5, 1, 44, 64, 8):
        raise SystemExit("Unexpected GIM format or dimensions")
    print(f"battery_gim_sha256={hashlib.sha256(data).hexdigest()}")
    print("image=44x64 INDEX8 swizzled; RGBA8888 palette; stride=48 bytes")
    for start_y in range(0, 64, 16):
        points = []
        for y in range(start_y, start_y + 16):
            for x in range(44):
                offset = 0x4d0 + ((y // 8) * 3 + x // 16) * 128 + (y % 8) * 16 + x % 16
                index = data[offset]
                if data[0x80 + index * 4 + 3]:
                    points.append((x, y - start_y))
        if not points:
            raise SystemExit("Empty battery slice")
        print(f"rows={start_y}..{start_y + 15} alpha_bounds="
              f"{min(x for x, y in points)},{min(y for x, y in points)}.."
              f"{max(x for x, y in points)},{max(y for x, y in points)}")


if __name__ == "__main__":
    main()
