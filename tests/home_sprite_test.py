"""Portable owned-memory composition; synthetic assets, no Sony dependencies."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
from home_types import Tiles, Sprite, load_library


class HomeSpriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / "build/tests").mkdir(parents=True, exist_ok=True)
        cls.directory = tempfile.TemporaryDirectory(dir=ROOT / "build/tests")
        binary = Path(cls.directory.name) / "sprite.so"
        subprocess.run([os.environ.get("CC", "cc"), "-std=c99", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
                        str(ROOT / "src/home/sprite.c"), "-o", str(binary)], check=True, capture_output=True)
        cls.lib = load_library(binary)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def assets(self):
        atlas = (ctypes.c_uint16 * 2400)(*([0x9ce7] * 2400))
        for digit in range(10):
            width = 6 if digit == 1 else 11
            for x in range(width):
                atlas[digit * 240 + x] = 0xffff
                atlas[digit * 240 + 2 * 16 + x + 2] = 0x8c63
        coverage = (ctypes.c_ubyte * 121)()
        for i in range(11):
            coverage[i * 11 + i] = 15
        tiles = Tiles()
        self.assertEqual(self.lib.home_tiles_prepare(ctypes.byref(tiles), atlas, 2400, coverage, 11, 11), 0)
        return tiles, atlas, coverage

    def test_all_percentages_and_original_digit_preservation(self):
        tiles, atlas, coverage = self.assets()
        for digit in range(10):
            self.assertEqual(list(tiles.pixels[digit]), list(atlas[digit * 240:(digit + 1) * 240]))
        before = bytes(tiles)
        for percent in range(101):
            sprite = Sprite()
            self.assertEqual(self.lib.home_sprite_compose(ctypes.byref(tiles), percent, ctypes.byref(sprite)), 0)
            self.assertEqual((sprite.percent, sprite.height), (percent, 15))
            self.assertGreater(sprite.width, 0)
            self.assertLessEqual(sprite.width, 64)
            self.assertTrue(all(p & 0x8000 for p in sprite.pixels))
            for row in range(15):
                self.assertEqual(list(sprite.pixels[row * 64 + sprite.width:(row + 1) * 64]),
                                 [0x9ce7] * (64 - sprite.width))
        self.assertEqual(bytes(tiles), before)
        # Endpoints have no leading zeros; only 100 has three digit tiles.
        widths = []
        for value in (0, 9, 10, 100):
            sprite = Sprite()
            self.lib.home_sprite_compose(ctypes.byref(tiles), value, ctypes.byref(sprite))
            widths.append(sprite.width)
        self.assertEqual(widths[0], widths[1])
        self.assertGreater(widths[2], widths[0])
        self.assertGreater(widths[3], widths[2])

    def test_compact_overlap_retains_bright_foreground(self):
        tiles, atlas, coverage = self.assets()
        tiles.pixels[1][8] = 0x8c63
        out = Sprite()
        self.assertEqual(self.lib.home_sprite_compose(ctypes.byref(tiles), 11, ctypes.byref(out)), 0)
        self.assertEqual(out.pixels[8], 0xffff)
        self.assertEqual(out.pixels[9], 0xffff)

    def test_prepare_prevalidates_without_publishing_partial_output(self):
        tiles, atlas, coverage = self.assets()
        before = bytes(tiles)
        for size, width, height in ((2399, 11, 11), (2400, 12, 11), (2400, 11, 12)):
            self.assertLess(self.lib.home_tiles_prepare(ctypes.byref(tiles), atlas, size, coverage, width, height), 0)
            self.assertEqual(bytes(tiles), before)
        coverage[120] = 16
        self.assertEqual(self.lib.home_tiles_prepare(ctypes.byref(tiles), atlas, 2400, coverage, 11, 11), -2)
        self.assertEqual(bytes(tiles), before)
        coverage[120] = 15
        atlas[2399] = 0x001f
        self.assertEqual(self.lib.home_tiles_prepare(ctypes.byref(tiles), atlas, 2400, coverage, 11, 11), -2)
        self.assertEqual(bytes(tiles), before)

    def test_compose_refuses_conflicts_and_invalid_state_transactionally(self):
        tiles, atlas, coverage = self.assets()
        out = Sprite()
        ctypes.memset(ctypes.byref(out), 0x5a, ctypes.sizeof(out))
        before = bytes(out)
        self.assertEqual(self.lib.home_sprite_compose(ctypes.byref(tiles), 101, ctypes.byref(out)), -1)
        self.assertEqual(bytes(out), before)
        tiles.right[1] = 16
        self.assertEqual(self.lib.home_sprite_compose(ctypes.byref(tiles), 11, ctypes.byref(out)), -2)
        self.assertEqual(bytes(out), before)
        tiles.ready = 0
        self.assertEqual(self.lib.home_sprite_compose(ctypes.byref(tiles), 1, ctypes.byref(out)), -1)
        self.assertEqual(bytes(out), before)
        self.assertEqual(self.lib.home_sprite_compose(None, 1, ctypes.byref(out)), -1)
        self.assertEqual(self.lib.home_sprite_compose(ctypes.byref(tiles), 1, None), -1)
