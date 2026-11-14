"""Actual loader and parent lifecycle against explicit host service contracts."""
from pathlib import Path
import unittest
from support import ROOT, TESTS, C_TESTS, temporary_directory, compile_program, run_program


class BootstrapTests(unittest.TestCase):
    def test_user_payload_abi_placement_and_failure_ownership(self):
        scenarios = ("success", "load", "name", "kernel_segment", "kernel_attribute", "start",
                     "stop", "unload", "stop_status", "start_status", "failed_cleanup", "duplicate")
        with temporary_directory() as directory:
            binary = Path(directory) / "loader"
            compile_program(binary, C_TESTS / "bootstrap_loader.c", C_TESTS / "bootstrap_payload.S",
                            ROOT / "src/bootstrap/vsh.c", includes=[TESTS / "stubs", ROOT / "src/bootstrap"])
            for mode, name in enumerate(scenarios):
                with self.subTest(scenario=name):
                    run_program(binary, mode)

    def test_dispatch_and_refusal_to_unload_live_game(self):
        scenarios = ("vsh", "game", "pops", "create", "start", "stop_before_run", "join", "child_stop")
        with temporary_directory() as directory:
            binary = Path(directory) / "lifecycle"
            compile_program(binary, C_TESTS / "bootstrap_lifecycle.c", ROOT / "src/bootstrap/main.c",
                            includes=[TESTS / "stubs", ROOT / "src/bootstrap"], defines=["BATTERY_DIAGNOSTICS=0"])
            for mode, name in enumerate(scenarios):
                with self.subTest(scenario=name):
                    run_program(binary, mode)

    def test_context_guards_and_explicit_pops_refusal(self):
        with temporary_directory() as directory:
            binary = Path(directory) / "context"
            compile_program(binary, C_TESTS / "bootstrap_context.c", includes=[ROOT / "src/bootstrap"])
            run_program(binary)
