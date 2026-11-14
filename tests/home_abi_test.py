"""Final pre/Sony/post ABI and integer-only helpers, independent of old candidates."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from prx_checks import hook_template
from support import ROOT, C_TESTS, temporary_directory, compile_program, run_program


class HomeAbiTests(unittest.TestCase):
    def test_nested_expired_and_wrapped_refresh_tokens(self):
        with temporary_directory() as directory:
            binary = Path(directory) / "refresh"
            compile_program(binary, C_TESTS / "home_refresh.c", includes=[ROOT / "src/home"])
            run_program(binary)

    def test_inputs_native_results_and_per_frame_token(self):
        for token in (0, 123):
            words, refs = hook_template()
            destinations = dict(home_before=0x600, home_after=0x700, original=0x1800)
            for hi, lo, name in refs:
                words[lo] |= destinations[name]
            regs = [0x12000000 + i for i in range(32)]
            regs[0] = 0
            regs[29] = 0x880FF000
            initial = regs[:]
            memory = {0x1800: 0x88104790}
            hi, lo = 1, 2
            calls = []
            returned = None
            for word in words:
                op, rs, rt, imm = word >> 26, (word >> 21) & 31, (word >> 16) & 31, word & 0xFFFF
                signed = imm - 0x10000 if imm & 0x8000 else imm
                if op == 15:
                    regs[rt] = imm << 16
                elif op == 9:
                    regs[rt] = (regs[rs] + signed) & 0xFFFFFFFF
                elif op == 43:
                    memory[(regs[rs] + signed) & 0xFFFFFFFF] = regs[rt]
                elif op == 35:
                    regs[rt] = memory[(regs[rs] + signed) & 0xFFFFFFFF]
                elif word == 0x00004010:
                    regs[8] = hi
                elif word == 0x00004012:
                    regs[8] = lo
                elif word == 0x01000011:
                    hi = regs[8]
                elif word == 0x01000013:
                    lo = regs[8]
                elif word == 0x0320F809:
                    calls.append(regs[25])
                    regs[31] = 0xDEAD
                    if len(calls) == 1:
                        self.assertEqual(regs[4], initial[31])
                        for i in range(2, 16):
                            regs[i] = 0xBAD
                        regs[2] = token
                        hi, lo = 0xBAD, 0xBAD
                    elif len(calls) == 2:
                        self.assertEqual(regs[2:10], initial[2:10])
                        self.assertEqual(regs[28], initial[28])
                        self.assertEqual((hi, lo), (1, 2))
                        regs[2:4] = [55, 66]
                        hi, lo = 77, 88
                    else:
                        self.assertEqual(regs[4:6], [initial[31], token])
                        for i in range(2, 16):
                            regs[i] = 0xBAD
                        hi, lo = 0xBAD, 0xBAD
                    for at in range(0, 16, 4):
                        memory[regs[29] + at] = 0xBAD
                    regs[28] = 0xBAD
                elif word == 0x03E00008:
                    returned = regs[31]
                elif word != 0:
                    self.fail(f"Unknown instruction {word:08x}")
            self.assertEqual(calls, [0x600, 0x88104790, 0x700])
            self.assertEqual(returned, initial[31])
            self.assertEqual(regs[2:4], [55, 66])
            self.assertEqual((hi, lo), (77, 88))
            for i in [16, 17, 18, 19, 20, 21, 22, 23, 26, 27, 28, 29, 30, 31]:
                self.assertEqual(regs[i], initial[i])
