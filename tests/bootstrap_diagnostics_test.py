"""Worker-only diagnostics: retries and finite budget, not renderer lifecycle."""

from pathlib import Path
import unittest
from support import ROOT, TESTS, C_TESTS, temporary_directory, compile_program, run_program


class BootstrapDiagnosticsTests(unittest.TestCase):
    def test_worker_snapshots_retry_and_budget(self):
        with temporary_directory() as directory:
            binary = Path(directory) / "diagnostics"
            compile_program(
                binary,
                C_TESTS / "bootstrap_diagnostics.c",
                ROOT / "src/bootstrap/diagnostics.c",
                includes=[TESTS / "stubs", ROOT / "src/bootstrap"],
                defines=["BATTERY_DIAGNOSTICS=1"],
            )
            run_program(binary)
