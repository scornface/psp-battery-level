"""Mutation fixtures verify the PRX gate, rather than trusting compiler success."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from prx_libraries import Prx
from check_vsh import check_module, nid
from prx_fixture import user_prx as fixture
from prx_checks import check_helper


class PrxChecks(unittest.TestCase):
    def setUp(self):
        self.elf = fixture()

    def check(self):
        return check_module(Prx.parse(bytes(self.elf)), "release")

    def test_valid_and_mode(self):
        self.assertEqual(self.check(), ("release", "0001000a"))
        with self.assertRaises(ValueError):
            check_module(Prx.parse(bytes(self.elf)), "diagnostic")

    def test_valid_diagnostic_and_wrong_mode(self):
        module=Prx.parse(bytes(fixture(True)))
        self.assertEqual(check_module(module,"diagnostic"),("diagnostic","0001000b"))
        with self.assertRaises(ValueError):check_module(module,"release")

    def test_wrong_machine_and_large_memory(self):
        struct.pack_into("<H", self.elf, 18, 62)
        with self.assertRaises(ValueError): self.check()
        self.elf = fixture()
        struct.pack_into("<I", self.elf, 52 + 20, 0xffffffff)
        with self.assertRaises(ValueError): self.check()

    def test_export_category_not_just_nid_set(self):
        struct.pack_into("<III", self.elf, 96 + 0x240, nid("module_info"), nid("module_start"), nid("module_stop"))
        with self.assertRaises(ValueError): self.check()

    def test_export_function_and_module_info_target(self):
        struct.pack_into("<I", self.elf, 96 + 0x240 + 16, 0x2000000)
        with self.assertRaises(ValueError): self.check()
        self.elf = fixture()
        struct.pack_into("<I", self.elf, 96 + 0x240 + 20, 0x104)
        with self.assertRaises(ValueError): self.check()

    def test_swapped_function_targets_and_bad_entry(self):
        struct.pack_into("<II", self.elf, 96 + 0x240 + 12, 0xa0, 0x80)
        with self.assertRaises(ValueError): self.check()
        self.elf = fixture(); struct.pack_into("<I", self.elf, 24, 0x100000)
        with self.assertRaises(ValueError): self.check()

    def test_duplicate_library_variable_import_and_bad_stub(self):
        first = struct.unpack_from("<I", self.elf, 96 + 0x300)[0]
        struct.pack_into("<I", self.elf, 96 + 0x314, first)
        with self.assertRaises(ValueError): self.check()
        self.elf = fixture(); self.elf[96 + 0x300 + 9] = 1
        with self.assertRaises(ValueError): self.check()
        self.elf = fixture(); struct.pack_into("<I", self.elf, 96 + 0x300 + 16, 0xfffffffc)
        with self.assertRaises(ValueError): self.check()

    def test_unknown_utility_nid_rejected(self):
        pointer = struct.unpack_from("<I", self.elf, 96 + 0x300 + 7 * 20 + 12)[0]
        struct.pack_into("<I", self.elf, 96 + pointer, 0x12345678)
        with self.assertRaises(ValueError): self.check()

    def test_truncated_elf(self):
        for length in (0, 4, 20, 51, 70, 95, len(self.elf) - 1):
            with self.subTest(length=length), self.assertRaises(ValueError):
                Prx.parse(bytes(self.elf[:length]))


class Helper:
    def __init__(self,word):self.word=word
    def require_range(self,address,size,executable=False):
        if address!=0x600 or size!=4 or not executable:raise ValueError('range')
    def u32(self,address):return self.word
    def imports(self):return [dict(name='InterruptManagerForKernel',stubs=[0x900])]


class HelperChecks(unittest.TestCase):
    def test_instruction_and_call_restrictions(self):
        for word in (0x46000000,0x60000000,0x0320f809,0x10000004,0x0c000080,0x04110000):
            with self.subTest(word=word),self.assertRaises(ValueError):check_helper(Helper(word),0x600,4)
        for word in (0x0110800a,0x0110800b,0x03e00008,0x0c000240):check_helper(Helper(word),0x600,4)


if __name__ == "__main__":
    unittest.main()
