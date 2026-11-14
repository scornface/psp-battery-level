#!/usr/bin/env python3
"""Authenticate external Sony assets and compare the complete approved sprite series."""

import ctypes
import argparse
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile
from common import ROOT, bounded_read, external_directory, outputs, run

FONT_HASH = "3c842878632fae835f78f83aee6f74a91d255fc5fdb32b163340033645e6b17f"
RESOURCE_HASH = "504a9327fc845ba449f7494d90d857096b3d2020d1501c45a127031388194f5e"
SERIES_HASH = "20d3a7efb382d548dccc507a7827a20259b866259bf63c24b8e3ba0fb778cb34"


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    firmware = external_directory("PSP_FIRMWARE_ROOT")
    resource = bounded_read(firmware / "F0/kd/resource/impose.rsc", 131072)
    font = bounded_read(firmware / "F0/font/ltn8.pgf", 131072)
    if (
        hashlib.sha256(resource).hexdigest() != RESOURCE_HASH
        or hashlib.sha256(font).hexdigest() != FONT_HASH
    ):
        raise ValueError("Unrecorded Sony font/resource")

    # Authentication precedes compilation/decoding. No resources or previews are
    # emitted, copied into the source tree or included in distributable builds.
    class Glyph(ctypes.Structure):
        _fields_ = [
            ("width", ctypes.c_uint),
            ("height", ctypes.c_uint),
            ("left", ctypes.c_int),
            ("top", ctypes.c_int),
            ("advance", ctypes.c_int),
            ("pixels", ctypes.c_ubyte * 1024),
        ]

    class Tiles(ctypes.Structure):
        _fields_ = [
            ("pixels", (ctypes.c_uint16 * 240) * 11),
            ("left", ctypes.c_uint * 11),
            ("right", ctypes.c_uint * 11),
            ("ready", ctypes.c_uint),
        ]

    class Sprite(ctypes.Structure):
        _fields_ = [
            ("pixels", ctypes.c_uint16 * 960),
            ("width", ctypes.c_uint),
            ("height", ctypes.c_uint),
            ("percent", ctypes.c_uint),
        ]

    start = struct.unpack_from("<I", resource, 112)[0]
    if start > len(resource) - 4804 or struct.unpack_from("<I", resource, start)[0] != 4800:
        raise ValueError("Unexpected digit atlas layout")
    raw = struct.unpack_from("<2400H", resource, start + 4)
    outputs(firmware / "F0/kd/resource/impose.rsc")
    (ROOT / "build/analysis").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="assets-", dir=ROOT / "build/analysis") as directory:
        binary = Path(directory) / "assets.so"
        subprocess.run(
            [
                os.environ.get("CC", "cc"),
                "-std=c99",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-shared",
                "-fPIC",
                str(ROOT / "src/home/sprite.c"),
                str(ROOT / "src/home/pgf.c"),
                "-o",
                str(binary),
            ],
            check=True,
        )
        lib = ctypes.CDLL(str(binary))
        glyph = Glyph()
        tiles = Tiles()
        lib.pgf_glyph.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_uint,
            ctypes.POINTER(Glyph),
        ]
        lib.home_tiles_prepare.argtypes = [
            ctypes.POINTER(Tiles),
            ctypes.POINTER(ctypes.c_uint16),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        lib.home_sprite_compose.argtypes = [
            ctypes.POINTER(Tiles),
            ctypes.c_uint,
            ctypes.POINTER(Sprite),
        ]
        data = ctypes.create_string_buffer(font)
        if lib.pgf_glyph(data, len(font), ord("%"), ctypes.byref(glyph)):
            raise ValueError("Percent decode failed")
        atlas = (ctypes.c_uint16 * 2400)(*raw)
        if lib.home_tiles_prepare(
            ctypes.byref(tiles), atlas, 2400, glyph.pixels, glyph.width, glyph.height
        ):
            raise ValueError("Asset preparation failed")
        if bytes(tiles.pixels)[:4800] != struct.pack("<2400H", *raw):
            raise ValueError("Original digits changed")
        series = bytearray()
        for value in range(101):
            sprite = Sprite()
            if lib.home_sprite_compose(ctypes.byref(tiles), value, ctypes.byref(sprite)):
                raise ValueError("Sprite composition failed")
            pixels = struct.pack("<960H", *sprite.pixels)
            series.extend(struct.pack("<II", value, sprite.width) + hashlib.sha1(pixels).digest())
        if hashlib.sha256(series).hexdigest() != SERIES_HASH:
            raise ValueError("Approved 0..100% sprite series changed")
    print("Authenticated assets passed: original digits and all 101 approved compact sprites match")


if __name__ == "__main__":
    run(main)
