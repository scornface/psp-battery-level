"""Construct tiny revision-2 PGFs from explicit synthetic coverage runs."""
import struct


def glyph(width=1, height=1, order=1, runs=None, advance_index=None, advance=64):
    record = bytearray()
    position = 0

    def put(value, count):
        nonlocal position
        for bit in range(count):
            if position // 8 == len(record):
                record.append(0)
            record[position // 8] |= ((value >> bit) & 1) << (position % 8)
            position += 1

    flags = order | (32 if advance_index is not None else 0)
    for value, count in ((0, 14), (width, 7), (height, 7), (0, 7), (1, 7),
                         (flags, 6), (0, 7), (0, 9)):
        put(value, count)
    for _ in range(3):
        put(0, 32)
        put(0, 32)
    if advance_index is None:
        put(advance, 32)
        put(0, 32)
    else:
        put(advance_index, 8)
    for run in runs if runs is not None else [(width * height, 15)]:
        if isinstance(run, tuple):
            count, coverage = run
            assert 1 <= count <= 8
            put(count - 1, 4)
            put(coverage, 4)
        else:
            assert 1 <= len(run) <= 8
            put(16 - len(run), 4)
            for coverage in run:
                put(coverage, 4)
    length = len(record)
    record[0] = length & 255
    record[1] = (record[1] & 0xc0) | (length >> 8)
    header = bytearray(392)
    struct.pack_into("<H", header, 2, 392)
    header[4:8] = b"PGF0"
    struct.pack_into("<I", header, 8, 2)
    struct.pack_into("<4I", header, 16, 1, 1, 1, 1)
    struct.pack_into("<H", header, 182, ord("%"))
    if advance_index is not None:
        header[261] = 1
        header.extend(struct.pack("<ii", advance, 0))
    return header + bytes(8) + record
