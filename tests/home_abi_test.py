"""Final pre/Sony/post ABI and integer-only helpers, independent of old candidates."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from prx_checks import check_helper,hook_template


class Helper:
    def __init__(self,word):self.word=word
    def require_range(self,address,size,executable=False):
        if address!=0x600 or size!=4 or not executable:raise ValueError('range')
    def u32(self,address):return self.word
    def imports(self):return [dict(name='InterruptManagerForKernel',stubs=[0x900])]


class HomeAbiTests(unittest.TestCase):
    def test_helper_instruction_and_call_restrictions(self):
        for word in (0x46000000,0x60000000,0x0320f809,0x10000004,0x0c000080,0x04110000):
            with self.subTest(word=word),self.assertRaises(ValueError):check_helper(Helper(word),0x600,4)
        for word in (0x0110800a,0x0110800b,0x03e00008,0x0c000240):check_helper(Helper(word),0x600,4)

    def test_inputs_native_results_and_per_frame_token(self):
        for token in (0,123):
            words,refs=hook_template()
            destinations=dict(home_before=0x600,home_after=0x700,original=0x1800)
            for hi,lo,name in refs:words[lo]|=destinations[name]
            regs=[0x12000000+i for i in range(32)];regs[0]=0;regs[29]=0x880ff000
            initial=regs[:];memory={0x1800:0x88104790};hi,lo=1,2;calls=[];returned=None
            for word in words:
                op,rs,rt,imm=word>>26,(word>>21)&31,(word>>16)&31,word&0xffff
                signed=imm-0x10000 if imm&0x8000 else imm
                if op==15:regs[rt]=imm<<16
                elif op==9:regs[rt]=(regs[rs]+signed)&0xffffffff
                elif op==43:memory[(regs[rs]+signed)&0xffffffff]=regs[rt]
                elif op==35:regs[rt]=memory[(regs[rs]+signed)&0xffffffff]
                elif word==0x00004010:regs[8]=hi
                elif word==0x00004012:regs[8]=lo
                elif word==0x01000011:hi=regs[8]
                elif word==0x01000013:lo=regs[8]
                elif word==0x0320f809:
                    calls.append(regs[25]);regs[31]=0xdead
                    if len(calls)==1:
                        self.assertEqual(regs[4],initial[31])
                        for i in range(2,16):regs[i]=0xbad
                        regs[2]=token;hi,lo=0xbad,0xbad
                    elif len(calls)==2:
                        self.assertEqual(regs[2:10],initial[2:10]);self.assertEqual(regs[28],initial[28])
                        self.assertEqual((hi,lo),(1,2));regs[2:4]=[55,66];hi,lo=77,88
                    else:
                        self.assertEqual(regs[4:6],[initial[31],token])
                        for i in range(2,16):regs[i]=0xbad
                        hi,lo=0xbad,0xbad
                    for at in range(0,16,4):memory[regs[29]+at]=0xbad
                    regs[28]=0xbad
                elif word==0x03e00008:returned=regs[31]
                elif word!=0:self.fail(f'Unknown instruction {word:08x}')
            self.assertEqual(calls,[0x600,0x88104790,0x700])
            self.assertEqual(returned,initial[31]);self.assertEqual(regs[2:4],[55,66])
            self.assertEqual((hi,lo),(77,88))
            for i in [16,17,18,19,20,21,22,23,26,27,28,29,30,31]:self.assertEqual(regs[i],initial[i])
