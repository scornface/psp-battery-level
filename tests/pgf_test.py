"""Bounded PGF decoder tests with synthetic data, not distributed Sony glyphs."""
import ctypes
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


class Glyph(ctypes.Structure):
    _fields_ = [("width", ctypes.c_uint), ("height", ctypes.c_uint),
                ("left", ctypes.c_int), ("top", ctypes.c_int), ("advance", ctypes.c_int),
                ("pixels", ctypes.c_ubyte * 1024)]


def synthetic():
    d = bytearray(444)
    struct.pack_into("<H", d, 2, 392); d[4:8] = b"PGF0"
    struct.pack_into("<I", d, 8, 2)
    struct.pack_into("<4I", d, 16, 1, 1, 1, 1)
    struct.pack_into("<H", d, 182, ord("%"))
    pos = 400 * 8
    def put(v, n):
        nonlocal pos
        for i in range(n):
            if v & (1 << i): d[pos // 8] |= 1 << (pos % 8)
            pos += 1
    for v, n in [(44,14),(1,7),(1,7),(0,7),(1,7),(1,6),(0,7),(0,9)]: put(v,n)
    for v in (0,0,0,0,0,0,64,0): put(v,32)
    put(0,4); put(15,4)
    return d


class FontProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT / "build/tests")
        binary = Path(cls.temp.name) / "pgf.so"
        subprocess.run([os.environ.get("CC", "cc"), "-std=c99", "-Wall", "-Wextra", "-Werror",
                         "-shared", "-fPIC", str(ROOT / "src/home/pgf.c"), "-o", str(binary)],
                       check=True, capture_output=True)
        cls.lib = ctypes.CDLL(str(binary))
        cls.decode = cls.lib.pgf_glyph
        cls.decode.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint, ctypes.POINTER(Glyph)]

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def result(self, d, char=ord("%")):
        b = ctypes.create_string_buffer(bytes(d)); g = Glyph()
        return self.decode(b, len(d), char, ctypes.byref(g)), g

    def test_glyph(self):
        r,g = self.result(synthetic())
        self.assertEqual(r, 0)
        self.assertEqual((g.width,g.height,g.left,g.top,g.advance,g.pixels[0]), (1,1,0,1,64,15))

    def test_bounds(self):
        d = synthetic()
        for length in (0, 391, 392, 400, 439):
            self.assertLess(self.result(d[:length])[0], 0)
        for offset, value in ((8,3),(24,32),(16,0xffffffff),(20,0xffffffff),(364,0xffffffff)):
            bad=d[:];struct.pack_into("<I",bad,offset,value)
            self.assertLess(self.result(bad)[0], 0)
        self.assertLess(self.result(d,ord("9"))[0],0)
        bad=d[:];bad[400:402]=b"\xff\x3f"
        self.assertLess(self.result(bad)[0],0)
