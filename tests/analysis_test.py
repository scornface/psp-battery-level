"""Research boundaries: reject unknown inputs/aliases before native execution."""

from pathlib import Path
import os
import sys
import tempfile
import types
import copy
import hashlib
import re
import struct
import io
import tarfile
import json
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/analysis"))
import common
import build_rcomage
import decompress_rco_rlz as rco
import resolve_prx_rel2 as rel2
import verify_assets
import verify_home
import dump_rco
from prx_fixture import user_prx


class AnalysisBoundaries(unittest.TestCase):
    def setUp(self):
        arguments = patch.object(sys, "argv", ["analysis-test"])
        arguments.start()
        self.addCleanup(arguments.stop)
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

    def test_nested_output_symlinks_and_mounts_are_rejected(self):
        directory = self.directory / "real"
        directory.mkdir()
        link = self.directory / "linked"
        link.symlink_to(directory, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "redirected"):
            common.outputs(self.source, link / "result.bin")
        with patch.object(Path, "is_mount", lambda p: p == directory):
            with self.assertRaisesRegex(ValueError, "mounted"):
                common.outputs(self.source, directory / "result.bin")
        self.assertFalse((directory / "result.bin").exists())

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

    def test_asset_verifier_rejects_redirected_work_directory_before_compiling(self):
        resource = bytearray(5000)
        struct.pack_into("<I", resource, 112, 128)
        struct.pack_into("<I", resource, 128, 4800)
        font = b"synthetic font"
        redirect = self.directory / "redirect"
        redirect.mkdir()
        (self.directory / "build").symlink_to(redirect, target_is_directory=True)
        with (
            patch.object(verify_assets, "ROOT", self.directory),
            patch.object(common, "ROOT", self.directory),
            patch.object(verify_assets, "external_directory", return_value=self.directory),
            patch.object(verify_assets, "bounded_read", side_effect=[bytes(resource), font]),
            patch.object(verify_assets, "RESOURCE_HASH", hashlib.sha256(resource).hexdigest()),
            patch.object(verify_assets, "FONT_HASH", hashlib.sha256(font).hexdigest()),
            patch.object(
                verify_assets.subprocess, "run", side_effect=AssertionError("compiler called")
            ),
            patch.object(sys, "argv", ["verify_assets.py"]),
        ):
            with self.assertRaisesRegex(ValueError, "redirected"):
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
                with (
                    patch.dict(os.environ, {"PSP_CAPSTONE_ROOT": external}, clear=True),
                    patch.dict(sys.modules, {"capstone": None}),
                ):
                    with self.assertRaisesRegex(ValueError, "Install Capstone"):
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

    def test_dump_rejects_bad_metadata_before_native_execution(self):
        tool = self.directory / "build/analysis/rcomage-tool"
        tool.mkdir(parents=True)
        (tool / "rcomage").write_bytes(b"synthetic tool")
        digest = hashlib.sha256(b"synthetic tool").hexdigest()
        for metadata in (None, {}, {"binary_sha256": digest, "data": {"../outside": digest}}):
            (tool / "manifest.json").write_text(json.dumps(metadata))
            with (
                self.subTest(metadata=metadata),
                patch.object(dump_rco, "ROOT", self.directory),
                patch.object(common, "ROOT", self.directory),
                patch.object(
                    dump_rco, "authenticated_resource", return_value=b"authenticated fixture"
                ),
                patch.object(
                    dump_rco.subprocess, "run", side_effect=AssertionError("native tool called")
                ),
                patch.object(
                    sys, "argv", ["dump_rco.py", str(self.source), str(tool.parent / "result.xml")]
                ),
            ):
                with self.assertRaisesRegex(ValueError, "manifest"):
                    dump_rco.main()

    def test_archive_extraction_accepts_files_but_rejects_aliases_and_traversal(self):
        for name, kind in (
            ("root/nested/file.txt", tarfile.REGTYPE),
            ("../outside", tarfile.REGTYPE),
            ("/absolute/file", tarfile.REGTYPE),
            ("root/link", tarfile.SYMTYPE),
        ):
            archive = self.directory / "synthetic.tar"
            with tarfile.open(archive, "w") as output:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.size = 2 if kind == tarfile.REGTYPE else 0
                member.linkname = "outside" if kind == tarfile.SYMTYPE else ""
                output.addfile(member, io.BytesIO(b"ok") if member.size else None)
            destination = self.directory / "extracted"
            if name == "root/nested/file.txt":
                build_rcomage.extract(archive, destination)
                self.assertEqual((destination / "nested/file.txt").read_bytes(), b"ok")
            else:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    build_rcomage.extract(archive, destination)

    def test_synthetic_rel2_decodes_and_rejects_truncated_stream(self):
        # Supply authenticated bytes only at the authentication seam. The real
        # ELF/PRX validator and relocation decoder both execute on this fixture.
        original = user_prx()
        data = original[:96] + bytes(32) + original[96:]
        struct.pack_into("<H", data, 44, 2)
        struct.pack_into("<I", data, 56, 128)
        struct.pack_into("<I", data, 64, 128 + 0x100)
        stream = bytes([0, 0, 2, 2, 3, 0, 1, 3, 2, 5]) + struct.pack(
            "<HH", 1, 2 | (1 << 3) | (0x80 << 5)
        )
        struct.pack_into("<8I", data, 84, 0x700000A1, len(data), 0, 0, len(stream), 0, 0, 1)
        data.extend(stream)
        with patch.object(rel2, "verified_source", return_value=bytes(data)):
            image, headers, records, report = rel2.decode_prx(self.source, 0)
        self.assertEqual(image, original[96:])
        self.assertEqual(len(headers), 2)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].split("\t")[1:3], ["00000080", "32"])
        self.assertEqual(report["command_count"], 2)
        for length in (0, 1, 4, 11, len(stream) - 1):
            bad = data[: len(data) - len(stream) + length]
            struct.pack_into("<I", bad, 84 + 16, length)
            with (
                self.subTest(length=length),
                patch.object(rel2, "verified_source", return_value=bytes(bad)),
            ):
                with self.assertRaises(ValueError):
                    rel2.decode_prx(self.source, 0)


class HomeGuardChecks(unittest.TestCase):
    """Synthetic consistency checks, not independent firmware authentication."""

    def setUp(self):
        self.groups = []
        for name in ("dispatch", "return", "draw", "cache", "event"):
            text = (ROOT / f"src/home/signatures/{name}.h").read_text()
            self.groups.append(
                [
                    tuple(int(v, 0) for v in fields)
                    for fields in re.findall(
                        r"\{(0x[0-9a-f]+), (0x[0-9a-f]+), ([0-3]), (0x[0-9a-f]+|0)\}", text
                    )
                ]
            )
        self.image = bytearray(0xA598)
        self.records = []
        relocated = set()
        for offset, word, kind, target in sum(self.groups, []):
            struct.pack_into("<I", self.image, offset, word)
            if kind and offset not in relocated:
                relocated.add(offset)
                name = {1: "LO16", 2: "HI16", 3: "J26"}[kind]
                self.records.append(f"1\t{offset:08x}\t{name}\t0\t0\t00\t00000000\t00000000")

    def test_all_relocation_records_are_consumed_without_skipping_header(self):
        self.assertEqual(verify_home.verify(self.image, self.records, self.groups), 175)
        with self.assertRaisesRegex(ValueError, "signature mismatch"):
            verify_home.verify(self.image, self.records[11:], self.groups)

    def test_duplicate_missing_and_changed_guards_are_rejected(self):
        for change in ("duplicate", "missing", "word", "target"):
            groups = copy.deepcopy(self.groups)
            offset, word, kind, target = groups[0][0]
            if change == "duplicate":
                groups[0][1] = groups[0][0]
            if change == "missing":
                groups.pop()
            if change == "word":
                groups[0][0] = (offset, word ^ 1, kind, target)
            if change == "target":
                i = next(i for i, s in enumerate(groups[0]) if s[2] == 2)
                o, w, k, t = groups[0][i]
                groups[0][i] = (o, w, k, t ^ 4)
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify_home.verify(self.image, self.records, groups)

    def test_malformed_duplicate_and_changed_relocations_are_rejected(self):
        for records in (
            ["malformed"],
            self.records + [self.records[0]],
            [
                self.records[0]
                .replace("\tHI16\t", "\tNONE\t")
                .replace("\tLO16\t", "\tNONE\t")
                .replace("\tJ26\t", "\tNONE\t"),
                *self.records[1:],
            ],
        ):
            with self.subTest(records=records[:1]), self.assertRaises(ValueError):
                verify_home.verify(self.image, records, self.groups)


if __name__ == "__main__":
    unittest.main()
