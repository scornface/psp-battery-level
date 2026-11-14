"""Strict-aliasing transfers, complete mismatch preflight and physical aliases."""

from pathlib import Path
import unittest
from support import ROOT, C_TESTS, temporary_directory, compile_program, run_program


class HomeBarWordTests(unittest.TestCase):
    def test_word_transfers_and_all_halfword_mismatches(self):
        with temporary_directory() as directory:
            binary = Path(directory) / "words"
            compile_program(
                binary,
                C_TESTS / "home_bar_words.c",
                includes=[ROOT / "src/home"],
                flags=["-O3", "-fstrict-aliasing"],
            )
            run_program(binary)

    def test_target_alias_identity_without_dereferencing_fake_addresses(self):
        with temporary_directory() as directory:
            binary = Path(directory) / "alias"
            compile_program(
                binary,
                C_TESTS / "home_alias.c",
                includes=[ROOT / "src/home"],
                defines=["__mips__=1"],
            )
            run_program(binary)
