"""Residual ownership, exact restoration and refusal of unverified scene writes."""

from pathlib import Path
import unittest
from support import ROOT, C_TESTS, temporary_directory, compile_program, run_program


class HomeRecoveryTests(unittest.TestCase):
    def test_residual_ownership(self):
        with temporary_directory() as directory:
            binary = Path(directory) / "recovery"
            compile_program(
                binary,
                C_TESTS / "home_recovery.c",
                includes=[ROOT / "src/home"],
                flags=["-O3", "-fstrict-aliasing"],
            )
            run_program(binary)
