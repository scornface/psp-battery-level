"""Mutation fixtures verify the PRX gate, rather than trusting compiler success."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from prx_libraries import Prx
from check_build import check_module, nid
from summarize_log import parse_snapshots, completions


def fixture():
    image = bytearray(4096)
    identity = b"PSPBatteryLevel release 0001000a\0"
    image[0x40:0x40 + len(identity)] = identity
    libraries = {
        "KUBridge": ["kuKernelFindModuleByName", "kuKernelGetModel", "kuKernelInitKeyConfig"],
        "SystemCtrlForUser": ["sctrlSEGetVersion", "sctrlHENGetVersion", "sctrlHENGetMinorVersion"],
        "scePower": ["scePowerGetBatteryLifePercent", "scePowerIsBatteryExist"],
        "sceUsb": ["sceUsbGetDrvState"],
        "Kernel_Library": ["sceKernelLockLwMutex", "sceKernelUnlockLwMutex", "sceKernelTryLockLwMutex"],
        "SysMemUserForUser": ["sceKernelDevkitVersion", "sceKernelTotalFreeMemSize"],
        "ThreadManForUser": ["sceKernelCreateThread", "sceKernelStartThread", "sceKernelDeleteThread",
                             "sceKernelWaitThreadEnd", "sceKernelDelayThread", "sceKernelGetThreadId"],
        "UtilsForUser": ["sceKernelDcacheWritebackRange"],
    }
    cursor = 0x600
    for i, (name, functions) in enumerate(libraries.items()):
        names = name.encode() + b"\0"
        nameptr = cursor; image[cursor:cursor + len(names)] = names
        cursor = (cursor + len(names) + 3) & ~3
        nids = cursor
        for f in functions:
            struct.pack_into("<I", image, cursor, nid(f)); cursor += 4
        stubs = cursor; cursor += len(functions) * 8
        attr = 9 if name == "Kernel_Library" else 0x4008 if name == "SysMemUserForUser" else 0x4009
        struct.pack_into("<IHHBBHII", image, 0x300 + i * 20, nameptr, 0, attr, 5, 0, len(functions), nids, stubs)
    struct.pack_into("<HBB28sIIIII", image, 0x100, 0, 9, 0, b"PSPBatteryLevel", 0, 0x200, 0x210, 0x300, 0x3a0)
    struct.pack_into("<IHHBBHI", image, 0x200, 0, 0, 0x8000, 4, 1, 2, 0x240)
    struct.pack_into("<IIIIII", image, 0x240, nid("module_start"), nid("module_stop"), nid("module_info"), 0x80, 0xa0, 0x100)
    elf = bytearray(96) + image
    ident = b"\x7fELF\x01\x01\x01" + bytes(9)
    struct.pack_into("<16sHHIIIIIHHHHHH", elf, 0, ident, 0xffa0, 8, 1, 0x80, 52, 0, 0, 52, 32, 1, 0, 0, 0)
    struct.pack_into("<IIIIIIII", elf, 52, 1, 96, 0, 96 + 0x100, len(image), len(image), 5, 16)
    return elf


class PrxChecks(unittest.TestCase):
    def setUp(self):
        self.elf = fixture()

    def check(self):
        return check_module(Prx.parse(bytes(self.elf)), "release")

    def test_valid_and_mode(self):
        self.assertEqual(self.check(), ("release", "0001000a"))
        with self.assertRaises(ValueError):
            check_module(Prx.parse(bytes(self.elf)), "diagnostic")

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


class Logs(unittest.TestCase):
    @staticmethod
    def record(entry=0, desired=50, displayed=49, build=10, time=1):
        return dict(build_id=build, entry=entry, desired=desired, displayed=displayed, outcome=0, time_us=time)

    def test_partial_duplicate_malformed_and_crlf(self):
        complete = self.record()
        text = "\r\n".join(f"{k}={v:08x}" for k, v in complete.items()) + "\r\n"
        records, warnings = parse_snapshots(text + "build_id=0000000a\nentry=00000001\n")
        self.assertEqual(records, [complete]); self.assertTrue(warnings)
        for tail in ("outcome=xyz\n", "outcome=00000000\n"):
            self.assertFalse(parse_snapshots(text + tail)[0])

    def test_cancellation_build_boundary_and_wrap(self):
        a = self.record(time=0xfffffff0)
        b = self.record(entry=1, displayed=50, time=0x10)
        self.assertEqual(list(completions([a, b])), [(50, 32 / 1_000_000)])
        invalid = self.record(entry=1, desired=0xffffffff, displayed=0xffffffff)
        self.assertEqual(list(completions([a, invalid, self.record(entry=2, displayed=50)])), [])
        b["build_id"] += 1
        self.assertEqual(list(completions([a, b])), [])
        b["build_id"] = a["build_id"]; b["entry"] = 2
        self.assertEqual(list(completions([a, b])), [])


if __name__ == "__main__":
    unittest.main()
