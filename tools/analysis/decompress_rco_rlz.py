#!/usr/bin/env python3
"""Decode the RLZ-compressed table block in a PSP RCO using local pspdecrypt sources."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import struct
import subprocess
import platform
import tempfile
from pathlib import Path
from common import outputs, run
from prx_libraries import bounded_read


ROOT = Path(__file__).resolve().parents[2]
LZR_SOURCE = ROOT / ".deps/pspdecrypt-1.0/libLZR.c"
LZR_HEADER = ROOT / ".deps/pspdecrypt-1.0/libLZR.h"
RCO_SHA256 = "3da2042c7042faf1d810c970bdb500ce812ea31e548ee9d0d17e57483c1c71dd"
LZR_HASHES = (
    "cf3e094784557f0a0f47ebd4522f29e61461757883236eb202395ef13582ae6e",
    "20f7908e19e646b3c3e551a8e24c4e731b05c927fa4689b6ee4aa1319d98c0fc",
)
RCO_HEADER_SIZE = 0xA4
RCO_COMPRESSION_OFFSET = 0x0C
RCO_COMPRESSION_RLZ = 2


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def authenticated_resource(source):
    data = bounded_read(source, 34336)
    if sha256(data) != RCO_SHA256:
        raise ValueError("Only the authenticated standard Sony 6.61 system_plugin_fg.rco is supported")
    return data


def load_lzr() -> ctypes.CDLL:
    outputs(LZR_SOURCE)
    if not LZR_SOURCE.is_file() or not LZR_HEADER.is_file():
        raise SystemExit("Local pspdecrypt libLZR sources are missing under .deps/.")
    if platform.system() != "Darwin":
        raise ValueError("This verified LZR build recipe supports macOS only")
    # Verified sources and an isolated build product; no shared writable dylib
    # races. libLZR has no input bound, so callers MUST authenticate the complete
    # canonical resource before entering C. This is not a generic RCO decoder.
    source_hash = sha256(LZR_SOURCE.read_bytes())
    header_hash = sha256(LZR_HEADER.read_bytes())
    if (source_hash, header_hash) != LZR_HASHES:
        raise ValueError("Unexpected LZR source/header; use the documented pspdecrypt 1.0 input")
    directory = ROOT / "build/analysis"
    directory.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.TemporaryDirectory(prefix="lzr-", dir=directory)
    library_path = Path(temporary.name) / "liblzr.dylib"
    subprocess.run(
        [
            "clang",
            "-dynamiclib",
            "-fPIC",
            "-O2",
            "-o",
            str(library_path),
            str(LZR_SOURCE),
        ],
        check=True,
    )
    library = ctypes.CDLL(str(library_path))
    library._build_directory = temporary
    library.LZRDecompress.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    library.LZRDecompress.restype = ctypes.c_int
    return library


def decode(source: Path, output: Path) -> None:
    outputs(source, output)
    rco = authenticated_resource(source)
    if len(rco) < RCO_HEADER_SIZE + 12:
        raise SystemExit("Input is too short to contain an RCO header and RLZ metadata.")
    if rco[:4] != b"\x00PRF":
        raise SystemExit(f"Unexpected RCO signature: {rco[:4]!r}")

    compression_word = struct.unpack_from("<I", rco, RCO_COMPRESSION_OFFSET)[0]
    compression = compression_word >> 4
    if compression != RCO_COMPRESSION_RLZ:
        raise SystemExit(f"RCO header compression is {compression}, not RLZ (2).")

    packed_size, unpacked_size, longest_text = struct.unpack_from(
        "<III", rco, RCO_HEADER_SIZE
    )
    stream_offset = RCO_HEADER_SIZE + 12
    stream_end = stream_offset + packed_size
    if stream_end > len(rco):
        raise SystemExit("RLZ packed-size field extends beyond the RCO file.")
    if unpacked_size == 0 or unpacked_size > 32 * 1024 * 1024:
        raise SystemExit(f"Implausible unpacked table size: {unpacked_size} bytes.")

    compressed = rco[stream_offset:stream_end]
    # Padding is a decoder implementation accommodation, NOT an input bound.
    # Authentication above excludes malformed/unknown streams before native code.
    in_buffer = ctypes.create_string_buffer(compressed + bytes(64))
    out_buffer = ctypes.create_string_buffer(unpacked_size)
    consumed_ptr = ctypes.c_void_p()
    lzr = load_lzr()
    result = lzr.LZRDecompress(
        out_buffer,
        unpacked_size,
        in_buffer,
        ctypes.byref(consumed_ptr),
    )
    consumed = consumed_ptr.value - ctypes.addressof(in_buffer)
    if result != unpacked_size:
        raise SystemExit(
            f"LZR returned {result} bytes; RCO metadata requires {unpacked_size}."
        )
    if consumed < 5 or consumed > packed_size:
        raise SystemExit(
            f"LZR consumed {consumed} bytes, outside the {packed_size}-byte block."
        )

    tables = out_buffer.raw[:result]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as destination:
        destination.write(tables)
    print(f"input={source} size={len(rco)} sha256={sha256(rco)}")
    print(
        f"tables={output} size={len(tables)} sha256={sha256(tables)} "
        f"RLZ-packed={packed_size} LZR-consumed={consumed} "
        f"longest-text={longest_text}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="source .rco (left unmodified)")
    parser.add_argument("output", type=Path, help="destination for decompressed table block")
    args = parser.parse_args()
    outputs(args.input, args.output)
    decode(args.input, args.output)


if __name__ == "__main__":
    run(main)
