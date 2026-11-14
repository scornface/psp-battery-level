"""Research boundaries: reject unknown inputs/aliases before native execution."""

from pathlib import Path
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/analysis"))
import common
import build_rcomage
import decompress_rco_rlz as rco
import resolve_prx_rel2 as rel2
import verify_assets


class AnalysisBoundaries(unittest.TestCase):
    def setUp(self):
        (ROOT / "build/analysis").mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(
            prefix="analysis-test-", dir=ROOT / "build/analysis"
        )
        self.directory = Path(self.temporary.name)
        self.source = self.directory / "input.rco"
        self.source.write_bytes(b"not a verified resource")

    def tearDown(self):
        self.temporary.cleanup()

    def test_unknown_resource_never_enters_native_decoder(self):
        with patch.object(rco, "load_lzr", side_effect=AssertionError("native decoder called")):
            with self.assertRaises(ValueError):
                rco.decode(self.source, self.directory / "result.bin")
        self.assertFalse((self.directory / "result.bin").exists())

    def test_input_alias_existing_output_and_outside_destination(self):
        with self.assertRaises(ValueError):
            common.outputs(self.source, self.source)
        link = self.directory / "alias.rco"
        link.symlink_to(self.source)
        with self.assertRaises(ValueError):
            common.outputs(self.source, link)
        with self.assertRaises(ValueError):
            common.outputs(self.source, ROOT / "src/never-write.bin")
        hard = self.directory / "hard-link.rco"
        os.link(self.source, hard)
        with self.assertRaises(ValueError):
            common.outputs(self.source, hard)

    def test_nonzero_relocation_base_rejected(self):
        with self.assertRaises(ValueError):
            rel2.decode_prx(self.source, 0x08800000)

    def test_impose_scope_is_exact_and_unknown_input_never_parses(self):
        self.assertEqual(
            common.FIRMWARE["impose_02g"],
            "4ad1f9c292eb88f7ea137ddb965c0a9ce7551251948f87e1b97534e5a2d542f0",
        )
        self.assertNotIn("impose_01g", common.FIRMWARE)
        with patch.object(
            rel2.Prx, "parse", side_effect=AssertionError("unauthenticated ELF parsed")
        ):
            with self.assertRaises(ValueError):
                rel2.decode_prx(self.source, 0)

    def test_verification_rejects_unknown_assets_before_compiling(self):
        font = self.directory / "F0/font/ltn8.pgf"
        resource = self.directory / "F0/kd/resource/impose.rsc"
        font.parent.mkdir(parents=True)
        resource.parent.mkdir(parents=True)
        font.write_bytes(b"unknown font")
        resource.write_bytes(b"unknown resource")
        with (
            patch.object(verify_assets, "external_directory", return_value=self.directory),
            patch.object(
                verify_assets.subprocess, "run", side_effect=AssertionError("compiler called")
            ),
        ):
            with self.assertRaisesRegex(ValueError, "Unrecorded Sony"):
                verify_assets.main()

    def test_external_directory_requires_explicit_existing_absolute_input(self):
        for value in (
            None,
            "",
            " ",
            "relative/path",
            str(self.directory / "missing"),
            str(self.source),
            str(self.directory),
        ):
            environment = {} if value is None else {"PSP_FIRMWARE_ROOT": value}
            with patch.dict(os.environ, environment, clear=True):
                with self.assertRaises(ValueError):
                    common.external_directory("PSP_FIRMWARE_ROOT")
        with tempfile.TemporaryDirectory() as external:
            with patch.dict(os.environ, {"PSP_FIRMWARE_ROOT": external}, clear=True):
                self.assertEqual(
                    common.external_directory("PSP_FIRMWARE_ROOT"), Path(external).resolve()
                )

    def test_capstone_checks_version_and_package_location(self):
        with tempfile.TemporaryDirectory() as external:
            fake = types.SimpleNamespace(
                __version__="5.0.6", __file__=str(Path(external) / "capstone/__init__.py")
            )
            original_path = sys.path[:]
            try:
                with (
                    patch.dict(os.environ, {"PSP_CAPSTONE_ROOT": external}, clear=True),
                    patch.dict(sys.modules, {"capstone": fake}),
                ):
                    self.assertIs(common.capstone_module(), fake)
                    fake.__version__ = "5.0.5"
                    with self.assertRaises(ValueError):
                        common.capstone_module()
                    fake.__version__ = "5.0.6"
                    fake.__file__ = str(self.source)
                    with self.assertRaises(ValueError):
                        common.capstone_module()
            finally:
                sys.path[:] = original_path

    def test_wrong_lzr_hash_never_compiles(self):
        with tempfile.TemporaryDirectory() as external:
            for name in ("libLZR.c", "libLZR.h"):
                (Path(external) / name).write_text("unknown source")
            with (
                patch.dict(os.environ, {"PSP_PSPDECRYPT_ROOT": external}, clear=True),
                patch.object(rco.platform, "system", return_value="Darwin"),
                patch.object(rco.subprocess, "run", side_effect=AssertionError("compiler called")),
            ):
                with self.assertRaisesRegex(ValueError, "Unexpected LZR"):
                    rco.load_lzr()

    def test_missing_lzr_sources_never_compile(self):
        with tempfile.TemporaryDirectory() as external:
            with (
                patch.dict(os.environ, {"PSP_PSPDECRYPT_ROOT": external}, clear=True),
                patch.object(rco.subprocess, "run", side_effect=AssertionError("compiler called")),
            ):
                with self.assertRaisesRegex(ValueError, "must contain"):
                    rco.load_lzr()

    def test_wrong_archive_hash_never_extracts(self):
        with tempfile.TemporaryDirectory() as external:
            (Path(external) / "pspdecrypt-1.0.tar.gz").write_bytes(b"unknown archive")
            with (
                patch.dict(os.environ, {"PSP_ARCHIVES_ROOT": external}, clear=True),
                patch.object(build_rcomage.platform, "system", return_value="Darwin"),
                patch.object(
                    build_rcomage, "extract", side_effect=AssertionError("extraction called")
                ),
            ):
                with self.assertRaisesRegex(SystemExit, "Unexpected archive hash"):
                    build_rcomage.main()


if __name__ == "__main__":
    unittest.main()
