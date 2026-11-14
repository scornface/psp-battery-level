"""Shared bounded ELF access and the verified integer-only HOME callback ABI."""

import struct
from prx_libraries import bounded_read


def target(words, hi, lo):
    low = words[lo] & 0xFFFF
    return ((words[hi] & 0xFFFF) << 16) + (low - 0x10000 if low & 0x8000 else low)


def hook_template():
    words = [0x27BDFFA0, 0xAFBF0010, 0xAFBC0014]
    refs = []
    for reg, offset in ((2, 24), (3, 28), (4, 32), (5, 36), (6, 40), (7, 44), (8, 48), (9, 52)):
        words.append(0xAFA00000 | reg << 16 | offset)
    words += [0x00004010, 0xAFA8003C, 0x00004012, 0xAFA80040, 0x8FA40010]

    def reference(name, lo):
        refs.append((len(words), len(words) + 1, name))
        words.extend([0x3C190000, lo])

    reference("home_before", 0x27390000)
    words += [0x0320F809, 0, 0xAFA20044, 0x8FA8003C, 0x01000011, 0x8FA80040, 0x01000013]
    for reg, offset in (
        (2, 24),
        (3, 28),
        (4, 32),
        (5, 36),
        (6, 40),
        (7, 44),
        (8, 48),
        (9, 52),
        (28, 20),
    ):
        words.append(0x8FA00000 | reg << 16 | offset)
    reference("original", 0x8F390000)
    words += [
        0x0320F809,
        0,
        0xAFA20018,
        0xAFA3001C,
        0x00004010,
        0xAFA8003C,
        0x00004012,
        0xAFA80040,
        0x8FA40010,
        0x8FA50044,
    ]
    reference("home_after", 0x27390000)
    words += [
        0x0320F809,
        0,
        0x8FA8003C,
        0x01000011,
        0x8FA80040,
        0x01000013,
        0x8FA20018,
        0x8FA3001C,
        0x8FBC0014,
        0x8FBF0010,
        0x03E00008,
        0x27BD0060,
    ]
    return words, refs


def check_helper(module, address, size):
    if address & 3 or size < 4 or size & 3:
        raise ValueError("Invalid helper extent")
    module.require_range(address, size, executable=True)
    calls = {
        stub
        for lib in module.imports()
        if lib["name"] == "InterruptManagerForKernel"
        for stub in lib["stubs"]
    }
    integer_ops = {
        1,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
        20,
        21,
        22,
        23,
        32,
        33,
        35,
        36,
        37,
        40,
        41,
        43,
    }
    special = {
        0,
        2,
        3,
        4,
        6,
        7,
        10,
        11,
        15,
        16,
        17,
        18,
        19,
        24,
        25,
        26,
        27,
        32,
        33,
        34,
        35,
        36,
        37,
        38,
        39,
        42,
        43,
    }
    for at in range(address, address + size, 4):
        w = module.u32(at)
        op = w >> 26
        if op in (2, 3):
            destination = (w & 0x3FFFFFF) * 4
            if destination not in calls and not (
                op == 2 and address <= destination < address + size
            ):
                raise ValueError("Helper calls outside interrupt primitives")
        elif op == 0:
            if w & 63 == 8:
                if w != 0x03E00008:
                    raise ValueError("Unexpected indirect helper jump")
            elif w & 63 not in special:
                raise ValueError("Unexpected helper special instruction")
        elif op == 31:
            if w & 63 not in (0, 4):
                raise ValueError("Unexpected helper SPECIAL3 instruction")
        elif op not in integer_ops:
            raise ValueError("Non-integer or unsupported helper instruction")
        if op == 1 and (w >> 16) & 31 not in (0, 1, 2, 3):
            raise ValueError("Unexpected helper REGIMM instruction")
        if op in (1, 4, 5, 6, 7, 20, 21, 22, 23):
            low = w & 0xFFFF
            destination = at + 4 + (low - 0x10000 if low & 0x8000 else low) * 4
            if not address <= destination < address + size:
                raise ValueError("Helper branch escapes its extent")


class CompanionElf:
    """One bounded snapshot for symbol lookup and executable helper bytes.

    The companion is an offline ELF, not a PRX module. Its sections locate
    symbols; only executable, file-backed load segments may supply helper code.
    """

    MAX_SIZE = 8 * 1024 * 1024

    @classmethod
    def open(cls, path):
        return cls(bounded_read(path, cls.MAX_SIZE))

    def __init__(self, data):
        self.data = bytes(data)
        data = self.data
        if len(data) < 52 or len(data) > self.MAX_SIZE or data[:7] != b"\x7fELF\x01\x01\x01":
            raise ValueError("Expected bounded ELF32 companion")
        if struct.unpack_from("<HHI", data, 16) not in ((2, 8, 1), (0xFFA0, 8, 1)):
            raise ValueError("Unexpected companion ELF type/machine")
        if struct.unpack_from("<H", data, 40)[0] != 52:
            raise ValueError("Invalid companion ELF header size")
        sections = self._table(32, 46, 40, 1024, "<10I")
        self.loads = tuple(p for p in self._table(28, 42, 32, 16, "<8I") if p[0] == 1)
        if not self.loads:
            raise ValueError("No companion load segments")
        for _, offset, _, _, filesz, memsz, _, _ in self.loads:
            if filesz > memsz or offset + filesz > len(data):
                raise ValueError("Invalid companion segment")

        self.symbols = {}
        functions = {}
        for section in sections:
            if section[1] != 2:
                continue
            start, size, link, entry = section[4], section[5], section[6], section[9]
            if entry != 16 or size % 16 or start + size > len(data) or link >= len(sections):
                raise ValueError("Invalid symbol table")
            strings = sections[link]
            if strings[1] != 3 or strings[4] + strings[5] > len(data):
                raise ValueError("Invalid symbol strings")
            names = data[strings[4] : strings[4] + strings[5]]
            for at in range(start, start + size, 16):
                n, value, length, info, _, index = struct.unpack_from("<IIIBBH", data, at)
                if n >= len(names) or (end := names.find(b"\0", n)) < 0:
                    raise ValueError("Invalid or unterminated symbol name")
                name = names[n:end].decode("ascii")
                if not index or not name:
                    continue
                if info >> 4 in (1, 2):
                    if name in self.symbols and self.symbols[name] != value:
                        raise ValueError("Ambiguous symbol")
                    self.symbols[name] = value
                if info & 15 == 2:
                    functions.setdefault(name, []).append((value, length))
        self.functions = functions

    def _table(self, offset_field, size_field, expected_size, maximum_count, layout):
        offset = struct.unpack_from("<I", self.data, offset_field)[0]
        entry, count = struct.unpack_from("<HH", self.data, size_field)
        if (
            entry != expected_size
            or not 0 < count <= maximum_count
            or offset < 52
            or offset + count * entry > len(self.data)
        ):
            raise ValueError("Invalid companion ELF table")
        return tuple(
            struct.unpack_from(layout, self.data, offset + i * entry) for i in range(count)
        )

    def function_extent(self, name):
        found = self.functions.get(name, ())
        if len(found) != 1:
            raise ValueError("Missing or ambiguous helper symbol")
        return found[0]

    def function_bytes(self, address, size):
        if address < 0 or size <= 0:
            raise ValueError("Invalid companion helper range")
        candidates = []
        for _, offset, vaddr, _, filesz, _, flags, _ in self.loads:
            if flags & 1 and vaddr <= address and address + size <= vaddr + filesz:
                at = offset + address - vaddr
                candidates.append(self.data[at : at + size])
        if len(candidates) != 1:
            raise ValueError("Companion helper is not uniquely executable/file-backed")
        return candidates[0]
