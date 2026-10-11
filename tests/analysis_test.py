"""Research boundaries: reject unknown inputs/aliases before native execution."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/analysis"))
import common
import decompress_rco_rlz as rco
import resolve_prx_rel2 as rel2


class AnalysisBoundaries(unittest.TestCase):
    def setUp(self):
        (ROOT / "build/analysis").mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="analysis-test-", dir=ROOT / "build/analysis")
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
        with self.assertRaises(ValueError): common.outputs(self.source, self.source)
        link = self.directory / "alias.rco"
        link.symlink_to(self.source)
        with self.assertRaises(ValueError): common.outputs(self.source, link)
        with self.assertRaises(ValueError): common.outputs(self.source, ROOT / "src/never-write.bin")
        hard = self.directory / "hard-link.rco"
        import os
        os.link(self.source, hard)
        with self.assertRaises(ValueError): common.outputs(self.source, hard)

    def test_nonzero_base_and_unknown_firmware_rejected(self):
        with self.assertRaises(ValueError): rel2.decode_prx(self.source, 0x08800000)
        with self.assertRaises(ValueError): rel2.decode_prx(self.source, 0)


if __name__ == "__main__":
    unittest.main()
