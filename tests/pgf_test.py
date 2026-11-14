"""PGF foreground parsing with synthetic row/column, RLE and metric records."""
import ctypes
from pathlib import Path
import struct
import unittest
from home_types import Glyph
from pgf_fixture import glyph
from support import ROOT, C_TESTS, temporary_directory, compile_library, compile_program, run_program


class PgfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = temporary_directory()
        binary = Path(cls.temp.name) / "pgf.so"
        compile_library(binary, ROOT / "src/home/pgf.c")
        cls.lib = ctypes.CDLL(str(binary))
        cls.decode = cls.lib.pgf_glyph
        cls.decode.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint, ctypes.POINTER(Glyph)]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def result(self, data, character=ord("%")):
        buffer = ctypes.create_string_buffer(bytes(data))
        out = Glyph()
        return self.decode(buffer, len(data), character, ctypes.byref(out)), out

    def test_original_coverage_and_metrics(self):
        result, out = self.result(glyph())
        self.assertEqual(result, 0)
        self.assertEqual((out.width, out.height, out.left, out.top, out.advance, out.pixels[0]),
                         (1, 1, 0, 1, 64, 15))

    def test_literal_and_repeated_runs_in_both_orders(self):
        for order, expected in ((1, [1, 2, 3, 4]), (2, [1, 3, 2, 4])):
            with self.subTest(order=order):
                result, out = self.result(glyph(2, 2, order, runs=[[1, 2, 3, 4]]))
                self.assertEqual(result, 0)
                self.assertEqual(list(out.pixels[:4]), expected)
                result, out = self.result(glyph(2, 2, order, runs=[(4, 7)]))
                self.assertEqual(result, 0)
                self.assertEqual(list(out.pixels[:4]), [7] * 4)

    def test_run_cannot_exceed_dimensions(self):
        self.assertEqual(self.result(glyph(runs=[(8, 15)]))[0], -8)

    def test_indirect_advance_and_invalid_index(self):
        result, out = self.result(glyph(advance_index=0, advance=128))
        self.assertEqual(result, 0)
        self.assertEqual(out.advance, 128)
        self.assertEqual(out.pixels[0], 15)
        self.assertEqual(self.result(glyph(advance_index=1))[0], -7)
        for advance in (0, 2049):
            self.assertEqual(self.result(glyph(advance=advance))[0], -7)

    def test_header_table_and_record_bounds(self):
        data = glyph()
        for length in (0, 391, 392, 400, len(data) - 1):
            with self.subTest(length=length):
                self.assertLess(self.result(data[:length])[0], 0)
        for offset, value in ((8, 3), (24, 32), (16, 0xffffffff), (20, 0xffffffff), (364, 0xffffffff)):
            bad = data[:]
            struct.pack_into("<I", bad, offset, value)
            with self.subTest(offset=offset):
                self.assertLess(self.result(bad)[0], 0)
        self.assertLess(self.result(data, ord("9"))[0], 0)
        bad = data[:]
        bad[400:402] = b"\xff\x3f"
        self.assertLess(self.result(bad)[0], 0)
        # The file contains bitmap bytes, but the glyph span excludes them.
        bad = data[:]
        bad[400] = 40
        bad[401] &= 0xc0
        self.assertEqual(self.result(bad)[0], -9)
        for order in (0, 3):
            self.assertEqual(self.result(glyph(order=order))[0], -6)

    def test_all_prefixes_and_single_bit_mutations_preserve_bounds(self):
        with temporary_directory() as directory:
            path = Path(directory)
            sample = path / "synthetic.pgf"
            sample.write_bytes(glyph())
            binary = path / "bounds"
            compile_program(binary, C_TESTS / "pgf_bounds.c", ROOT / "src/home/pgf.c",
                            includes=[ROOT / "src/home"])
            run_program(binary, sample)
