"""Ensure the cleaner cannot delete sources, dependencies or local evidence."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import clean


class CleanupTest(unittest.TestCase):
    def setUp(self):
        (ROOT / "build").mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="battery-clean-", dir=ROOT / "build")
        self.root = Path(self.temporary.name)
        self.previous_root = clean.ROOT
        clean.ROOT = self.root
        for mode in ("release", "diagnostic"):
            directory = self.root / "build" / mode
            directory.mkdir(parents=True)
            for name in ("main.o", "exports.c", "battery_level.prx", "battery_level.elf", "notes.txt"):
                (directory / name).write_bytes(b"fixture")
        for directory, name in (("src", "main.c"), (".deps", "external.o"),
                                ("data", "evidence.log"), ("build/custom", "custom.o")):
            path = self.root / directory
            path.mkdir(parents=True, exist_ok=True)
            (path / name).write_bytes(b"preserve")

    def tearDown(self):
        clean.ROOT = self.previous_root
        self.temporary.cleanup()

    def assert_preserved(self):
        for relative in ("src/main.c", ".deps/external.o", "data/evidence.log", "build/custom/custom.o"):
            self.assertEqual((self.root / relative).read_bytes(), b"preserve")

    def test_default_preserves_outputs_and_unrelated_files(self):
        clean.clean_builds()
        for mode in ("release", "diagnostic"):
            self.assertEqual({p.name for p in (self.root / "build" / mode).iterdir()},
                             {"battery_level.prx", "battery_level.elf", "notes.txt"})
        self.assert_preserved()

    def test_all_is_scoped_and_idempotent(self):
        clean.clean_builds(True)
        clean.clean_builds(True)
        for mode in ("release", "diagnostic"):
            self.assertEqual({p.name for p in (self.root / "build" / mode).iterdir()}, {"notes.txt"})
        self.assert_preserved()

    def test_mode_directory_symlink_rejected_before_any_deletion(self):
        import shutil
        mode = self.root / "build/diagnostic"
        shutil.rmtree(mode)
        mode.symlink_to(self.root / ".deps", target_is_directory=True)
        with self.assertRaises(ValueError):
            clean.clean_builds(True)
        self.assertTrue((self.root / "build/release/main.o").exists())
        self.assert_preserved()

    def test_build_directory_symlink_rejected(self):
        import shutil
        shutil.rmtree(self.root / "build")
        (self.root / "build").symlink_to(self.root / "src", target_is_directory=True)
        with self.assertRaises(ValueError):
            clean.clean_builds(True)
        for relative in ("src/main.c", ".deps/external.o", "data/evidence.log"):
            self.assertEqual((self.root / relative).read_bytes(), b"preserve")

    def test_file_symlink_is_not_followed(self):
        link = self.root / "build/release/shared.o"
        link.symlink_to(self.root / ".deps/external.o")
        clean.clean_builds(True)
        self.assertTrue(link.is_symlink())
        self.assert_preserved()

    def test_active_build_lock_preserves_all_outputs(self):
        (self.root / "build/.build-release.lock").mkdir()
        with self.assertRaises(ValueError): clean.clean_builds(True)
        self.assertTrue((self.root / "build/release/main.o").exists())


if __name__ == "__main__":
    unittest.main()
