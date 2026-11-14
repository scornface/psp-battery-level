"""Host-only VSH policies and controller guards, without a Sony renderer."""

from pathlib import Path
import unittest
from support import ROOT, TESTS, C_TESTS, temporary_directory, compile_program, run_program


class VshPolicyTests(unittest.TestCase):
    def test_clock_recovery_and_usb_policy(self):
        with temporary_directory() as directory:
            binary = Path(directory) / "policy"
            compile_program(binary, C_TESTS / "vsh_policy.c", includes=[ROOT / "src/vsh"])
            run_program(binary)

    def test_real_controller_guards_and_teardown(self):
        with temporary_directory() as directory:
            binary = Path(directory) / "controller"
            compile_program(binary, C_TESTS / "vsh_controller.c", includes=[TESTS])
            run_program(binary)
