"""Actual-width anchoring, canonical reuse and whole-frame write boundaries."""

from pathlib import Path
import unittest
from support import ROOT, C_TESTS, temporary_directory, compile_program, run_program


class HomeAnchorTests(unittest.TestCase):
    def test_geometry_and_session(self):
        with temporary_directory() as directory:
            binary = Path(directory) / "anchor"
            compile_program(
                binary,
                C_TESTS / "home_anchor.c",
                includes=[ROOT / "src/home"],
                flags=["-O3", "-fstrict-aliasing"],
            )
            run_program(binary)
