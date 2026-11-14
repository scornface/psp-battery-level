"""Mutate the maintained kernel/payload gate without requiring a PSP toolchain."""

from pathlib import Path
import copy
import struct
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_build as gate
from prx_checks import CompanionElf, hook_template
from prx_fixture import Runtime, user_prx


class IntegratedChecks(unittest.TestCase):
    def setUp(self):
        self.prepare()

    def prepare(self, diagnostic=False):
        self.diagnostic = diagnostic
        self.payload = bytes(user_prx(diagnostic))
        self.runtime = Runtime(self.payload, diagnostic)

    def check(self):
        m = self.runtime
        companion = Mock(spec=CompanionElf, symbols=m.symbols)
        companion.function_extent.side_effect = lambda name: (m.symbols[name], 4)
        companion.function_bytes.return_value = struct.pack("<I", 0x03E00008)
        with (
            patch.object(gate.CompanionElf, "open", return_value=companion) as open_elf,
            patch.object(gate, "bounded_read", return_value=self.payload) as read_payload,
        ):
            result = gate.check(
                Path("runtime"), Path("elf"), Path("payload"), self.diagnostic, module=m
            )
            read_payload.assert_called_once_with(Path("payload"), 512 * 1024)
            open_elf.assert_called_once_with(Path("elf"))
            return result

    def test_valid_in_both_modes(self):
        for diagnostic in (False, True):
            self.prepare(diagnostic)
            with self.subTest(diagnostic=diagnostic):
                self.assertEqual(self.check(), "diagnostic" if diagnostic else "release")

    def test_wrong_build_identity_rejected(self):
        identity = b"PSPBatteryRuntime release deadbeef\0"
        self.runtime.image[0x120 : 0x120 + len(identity)] = identity
        with self.assertRaises(ValueError):
            self.check()

    def test_dependency_and_mode_boundaries(self):
        for diagnostic in (False, True):
            for change in (
                "extra_write",
                "missing_read",
                "missing_library",
                "logger_marker",
                "timestamp",
            ):
                self.prepare(diagnostic)
                io = next(r for r in self.runtime.records if r["name"] == "IoFileMgrForKernel")
                thread = next(r for r in self.runtime.records if r["name"] == "ThreadManForKernel")

                if change == "extra_write":
                    io["nids"].append(0xDEADBEEF if diagnostic else 0x42EC03AC)
                    io["func_count"] += 1
                if change == "missing_read":
                    io["nids"].remove(0x6A638D83)
                    io["func_count"] -= 1
                if change == "missing_library":
                    self.runtime.records.pop(0)
                if change == "logger_marker":
                    path = b"ms0:/SEPLUGINS/battery-level-runtime.log\0"
                    self.runtime.image[0x900 : 0x900 + len(path)] = (
                        bytes(len(path)) if diagnostic else path
                    )
                if change == "timestamp":
                    if diagnostic:
                        thread["nids"].remove(0x369ED59D)
                        thread["func_count"] -= 1
                    else:
                        thread["nids"].append(0x369ED59D)
                        thread["func_count"] += 1

                with (
                    self.subTest(diagnostic=diagnostic, change=change),
                    self.assertRaises(ValueError),
                ):
                    self.check()

    def test_import_and_export_mutations(self):
        original = copy.deepcopy(self.runtime)
        for change in ("write", "duplicate", "attribute", "variable", "export"):
            self.runtime = copy.deepcopy(original)
            if change == "write":
                self.runtime.records[8]["nids"].append(0x42EC03AC)
            if change == "duplicate":
                self.runtime.records.append(self.runtime.records[0])
            if change == "attribute":
                self.runtime.records[0]["attribute"] = 0
            if change == "variable":
                self.runtime.records[0]["var_count"] = 1
            if change == "export":
                self.runtime.system["addresses"][2] += 4

            with self.subTest(change=change), self.assertRaises(ValueError):
                self.check()

    def test_payload_and_helper_mutations(self):
        original = copy.deepcopy(self.runtime)
        for change in ("payload", "alignment", "extent", "float", "helper_bytes"):
            self.runtime = copy.deepcopy(original)
            if change == "payload":
                self.runtime.image[0x1000] ^= 1
            if change == "alignment":
                self.runtime.symbols["battery_vsh_image"] += 1
            if change == "extent":
                self.runtime.symbols["battery_vsh_image_end"] -= 1
            if change == "float":
                struct.pack_into("<I", self.runtime.image, 0x600, 0x46000000)
            if change == "helper_bytes":
                self.runtime.image[0x700] ^= 1

            with self.subTest(change=change), self.assertRaises(ValueError):
                self.check()

    def test_every_wrapper_instruction(self):
        original = copy.deepcopy(self.runtime)
        for i in range(len(hook_template()[0])):
            self.runtime = copy.deepcopy(original)
            at = 0x400 + i * 4
            struct.pack_into("<I", self.runtime.image, at, self.runtime.u32(at) ^ 1)
            with self.subTest(instruction=i), self.assertRaises(ValueError):
                self.check()


class CompanionChecks(unittest.TestCase):
    def setUp(self):
        data = bytearray(512)
        data[:7] = b"\x7fELF\x01\x01\x01"
        struct.pack_into("<HHI", data, 16, 2, 8, 1)
        struct.pack_into("<H", data, 40, 52)
        struct.pack_into("<II", data, 28, 52, 0x120)
        struct.pack_into("<HHHH", data, 42, 32, 1, 40, 3)
        struct.pack_into("<8I", data, 52, 1, 0x100, 0x600, 0x600, 4, 4, 5, 4)
        struct.pack_into("<I", data, 0x100, 0x03E00008)
        names = b"\0home_after\0"
        struct.pack_into("<10I", data, 0x148, 0, 2, 0, 0, 0x1A0, 32, 2, 0, 4, 16)
        struct.pack_into("<10I", data, 0x170, 0, 3, 0, 0, 0x1C0, len(names), 0, 0, 1, 0)
        struct.pack_into("<IIIBBH", data, 0x1B0, 1, 0x600, 4, 0x12, 0, 1)
        data[0x1C0 : 0x1C0 + len(names)] = names
        self.data = data

    def test_companion_extents_are_bounded_and_file_backed(self):
        with patch("prx_checks.bounded_read", return_value=bytes(self.data)) as read:
            companion = CompanionElf.open(Path("elf"))
            self.assertEqual(companion.symbols["home_after"], 0x600)
            self.assertEqual(companion.function_extent("home_after"), (0x600, 4))
            self.assertEqual(companion.function_bytes(0x600, 4), struct.pack("<I", 0x03E00008))
            with self.assertRaises(ValueError):
                companion.function_bytes(0x600, 8)
            with self.assertRaises(ValueError):
                companion.function_extent("other")
            read.assert_called_once_with(Path("elf"), CompanionElf.MAX_SIZE)

    def test_invalid_headers_tables_and_names(self):
        for offset, layout, value in (
            (16, "<H", 1),
            (18, "<H", 0),
            (40, "<H", 0),
            (28, "<I", 0xFFFFFFFF),
            (32, "<I", 0xFFFFFFFF),
            (44, "<H", 17),
            (48, "<H", 1025),
            (42, "<H", 31),
            (46, "<H", 39),
            (52 + 4, "<I", 511),
            (52 + 16, "<I", 5),
            (0x148 + 16, "<I", 0x1F0),
            (0x148 + 24, "<I", 3),
            (0x148 + 36, "<I", 15),
            (0x170 + 4, "<I", 1),
            (0x170 + 20, "<I", 0xFFFFFFFF),
            (0x1B0, "<I", 12),
        ):
            data = self.data[:]
            struct.pack_into(layout, data, offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaises(ValueError):
                CompanionElf(data)
        for length in (0, 51, 80, 0x1C8):
            with self.subTest(length=length), self.assertRaises(ValueError):
                CompanionElf(self.data[:length])
        data = self.data[:]
        data[0x1CB] = ord("x")
        with self.assertRaises(ValueError):
            CompanionElf(data)

    def test_duplicate_function_and_conflicting_global_symbols(self):
        # Reuse the null symbol slot to keep the fixture's section extents fixed.
        data = self.data[:]
        data[0x1A0:0x1B0] = data[0x1B0:0x1C0]
        with self.assertRaisesRegex(ValueError, "ambiguous helper"):
            CompanionElf(data).function_extent("home_after")
        struct.pack_into("<I", data, 0x1A4, 0x604)
        with self.assertRaisesRegex(ValueError, "Ambiguous symbol"):
            CompanionElf(data)

    def test_helper_cannot_use_bss_nonexecutable_or_ambiguous_segments(self):
        for flags, filesz, count in ((4, 4, 1), (5, 0, 1), (5, 4, 2)):
            data = self.data[:]
            struct.pack_into("<I", data, 52 + 16, filesz)
            struct.pack_into("<I", data, 52 + 24, flags)
            struct.pack_into("<H", data, 44, count)
            if count == 2:
                data[84:116] = data[52:84]
            with (
                self.subTest(flags=flags, filesz=filesz, count=count),
                self.assertRaises(ValueError),
            ):
                CompanionElf(data).function_bytes(0x600, 4)

    def test_snapshot_does_not_follow_mutation_of_input(self):
        companion = CompanionElf(self.data)
        self.data[0x100] ^= 1
        self.assertEqual(companion.function_bytes(0x600, 4), struct.pack("<I", 0x03E00008))
