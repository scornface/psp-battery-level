"""Tool entrypoints reject bad requests without firmware, Docker or a console."""

import os
from pathlib import Path
import subprocess
import sys
import unittest
from support import ROOT, temporary_directory


class ToolCliTests(unittest.TestCase):
    def run_tool(self, script, *arguments):
        environment = {
            key: value for key, value in os.environ.items() if not key.startswith("PSP_")
        }
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, str(ROOT / "tools" / script), *map(str, arguments)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def test_all_python_entrypoints_have_help_without_external_inputs(self):
        helpers = {"prx_checks.py", "analysis/common.py"}
        for path in sorted((ROOT / "tools").rglob("*.py")):
            script = str(path.relative_to(ROOT / "tools"))
            if script in helpers:
                continue
            with self.subTest(script=script):
                result = self.run_tool(script, "--help")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)

    def test_analysis_arguments_are_rejected_before_external_dependency_lookup(self):
        for script, arguments in (
            ("analysis/verify_home.py", ["--candidate"]),
            ("analysis/verify_assets.py", ["--candidate"]),
            ("analysis/build_rcomage.py", ["--candidate"]),
            ("analysis/inspect_battery_resource.py", ["--candidate"]),
            ("analysis/inspect_paf.py", ["--range", "3:8"]),
            ("analysis/inspect_paf.py", ["--range", "invalid"]),
            ("analysis/prx_string_xrefs.py", ["missing", "missing", "--context", "33"]),
        ):
            with self.subTest(script=script, arguments=arguments):
                result = self.run_tool(script, *arguments)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertNotIn("Set PSP_", result.stderr)

    def test_invalid_inspection_and_log_inputs_report_errors_without_tracebacks(self):
        with temporary_directory() as directory:
            source = Path(directory) / "invalid"
            source.write_bytes(b"\xff")
            for script, arguments in (
                ("inspect_deployed.py", [source, "--reference", source]),
                ("summarize_log.py", [source]),
                ("summarize_runtime.py", [source]),
            ):
                with self.subTest(script=script):
                    result = self.run_tool(script, *arguments)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("Traceback", result.stderr)

    def test_both_log_readers_reject_oversized_inputs(self):
        with temporary_directory() as directory:
            source = Path(directory) / "oversized.log"
            with source.open("wb") as stream:
                stream.truncate(8 * 1024 * 1024 + 1)
            for script in ("summarize_log.py", "summarize_runtime.py"):
                with self.subTest(script=script):
                    result = self.run_tool(script, source)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Input exceeds", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_shell_entrypoints_reject_extra_arguments_without_invoking_docker(self):
        with temporary_directory() as directory:
            directory = Path(directory)
            docker = directory / "docker"
            marker = directory / "docker-called"
            docker.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 1\n')
            docker.chmod(0o755)
            environment = {**os.environ, "PATH": str(directory) + os.pathsep + os.environ["PATH"]}
            for script, arguments in (
                ("build.sh", ["release", "extra"]),
                ("test.sh", ["--sanitize", "extra"]),
            ):
                with self.subTest(script=script):
                    result = subprocess.run(
                        ["sh", str(ROOT / "tools" / script), *arguments],
                        cwd=ROOT,
                        env=environment,
                        capture_output=True,
                        text=True,
                        timeout=20,
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertFalse(marker.exists())
