"""Bounded read-only startup acquisition and transactional preparation."""

from pathlib import Path
import unittest
from support import ROOT, TESTS, C_TESTS, temporary_directory, compile_program, run_program


class HomeAssetsTests(unittest.TestCase):
    def test_read_only_authentication_and_transactional_preparation(self):
        with temporary_directory() as directory:
            binary = Path(directory) / "assets"
            compile_program(
                binary,
                C_TESTS / "home_assets.c",
                ROOT / "src/home/assets.c",
                ROOT / "src/home/sprite.c",
                includes=[TESTS / "stubs", ROOT / "src/home"],
            )
            run_program(binary)
