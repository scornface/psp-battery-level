"""Mutate the maintained kernel/payload gate without requiring a PSP toolchain."""
from pathlib import Path
import copy
import struct
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import check_build as gate
from prx_libraries import Prx
from prx_checks import hook_template, symbol_extent, elf_function_bytes
from prx_fixture import Runtime, user_prx


class IntegratedChecks(unittest.TestCase):
    def setUp(self):
        self.prepare()
    def prepare(self, diagnostic=False):
        self.diagnostic=diagnostic
        self.payload=bytes(user_prx(diagnostic));self.child=Prx.parse(self.payload)
        self.runtime=Runtime(self.payload,diagnostic)
    def check(self):
        m=self.runtime
        with patch.object(gate.Prx,'open',return_value=self.child),patch.object(gate,'symbols',return_value=m.symbols), \
             patch.object(gate,'bounded_read',return_value=self.payload), \
             patch.object(gate,'symbol_extent',side_effect=lambda elf,name:(m.symbols[name],4)), \
             patch.object(gate,'elf_function_bytes',return_value=struct.pack('<I',0x03e00008)):
            return gate.check(Path('runtime'),Path('elf'),Path('payload'),self.diagnostic,module=m)
    def test_valid_in_both_modes(self):
        for diagnostic in (False,True):
            self.prepare(diagnostic)
            with self.subTest(diagnostic=diagnostic):
                self.assertEqual(self.check(),'diagnostic' if diagnostic else 'release')
    def test_wrong_build_identity_rejected(self):
        identity=b'PSPBatteryRuntime release deadbeef\0'
        self.runtime.image[0x120:0x120+len(identity)]=identity
        with self.assertRaises(ValueError):self.check()

    def test_dependency_and_mode_boundaries(self):
        for diagnostic in (False,True):
            for change in ('extra_write','missing_read','missing_library','logger_marker','timestamp'):
                self.prepare(diagnostic)
                io=next(r for r in self.runtime.records if r['name']=='IoFileMgrForKernel')
                thread=next(r for r in self.runtime.records if r['name']=='ThreadManForKernel')
                if change=='extra_write':io['nids'].append(0xdeadbeef if diagnostic else 0x42ec03ac);io['func_count']+=1
                if change=='missing_read':io['nids'].remove(0x6a638d83);io['func_count']-=1
                if change=='missing_library':self.runtime.records.pop(0)
                if change=='logger_marker':
                    path=b'ms0:/SEPLUGINS/battery-level-runtime.log\0'
                    self.runtime.image[0x900:0x900+len(path)]=bytes(len(path)) if diagnostic else path
                if change=='timestamp':
                    if diagnostic:thread['nids'].remove(0x369ed59d);thread['func_count']-=1
                    else:thread['nids'].append(0x369ed59d);thread['func_count']+=1
                with self.subTest(diagnostic=diagnostic,change=change),self.assertRaises(ValueError):self.check()

    def test_import_and_export_mutations(self):
        original=copy.deepcopy(self.runtime)
        for change in ('write','duplicate','attribute','variable','export'):
            self.runtime=copy.deepcopy(original)
            if change=='write':self.runtime.records[8]['nids'].append(0x42ec03ac)
            if change=='duplicate':self.runtime.records.append(self.runtime.records[0])
            if change=='attribute':self.runtime.records[0]['attribute']=0
            if change=='variable':self.runtime.records[0]['var_count']=1
            if change=='export':self.runtime.system['addresses'][2]+=4
            with self.subTest(change=change),self.assertRaises(ValueError):self.check()
    def test_payload_and_helper_mutations(self):
        original=copy.deepcopy(self.runtime)
        for change in ('payload','alignment','extent','float','helper_bytes'):
            self.runtime=copy.deepcopy(original)
            if change=='payload':self.runtime.image[0x1000]^=1
            if change=='alignment':self.runtime.symbols['battery_vsh_image']+=1
            if change=='extent':self.runtime.symbols['battery_vsh_image_end']-=1
            if change=='float':struct.pack_into('<I',self.runtime.image,0x600,0x46000000)
            if change=='helper_bytes':self.runtime.image[0x700]^=1
            with self.subTest(change=change),self.assertRaises(ValueError):self.check()
    def test_every_wrapper_instruction(self):
        original=copy.deepcopy(self.runtime)
        for i in range(len(hook_template()[0])):
            self.runtime=copy.deepcopy(original);at=0x400+i*4
            struct.pack_into('<I',self.runtime.image,at,self.runtime.u32(at)^1)
            with self.subTest(instruction=i),self.assertRaises(ValueError):self.check()

    def test_companion_extents_are_bounded_and_file_backed(self):
        data=bytearray(512);data[:7]=b'\x7fELF\x01\x01\x01'
        struct.pack_into('<HHI',data,16,2,8,1);struct.pack_into('<II',data,28,52,0x120)
        struct.pack_into('<HHHH',data,42,32,1,40,3)
        struct.pack_into('<8I',data,52,1,0x100,0x600,0x600,4,4,5,4)
        struct.pack_into('<I',data,0x100,0x03e00008);names=b'\0home_after\0'
        struct.pack_into('<10I',data,0x148,0,2,0,0,0x1a0,32,2,0,4,16)
        struct.pack_into('<10I',data,0x170,0,3,0,0,0x1c0,len(names),0,0,1,0)
        struct.pack_into('<IIIBBH',data,0x1b0,1,0x600,4,0x12,0,1)
        data[0x1c0:0x1c0+len(names)]=names
        with patch('prx_checks.bounded_read',return_value=bytes(data)):
            self.assertEqual(symbol_extent(Path('elf'),'home_after'),(0x600,4))
            self.assertEqual(elf_function_bytes(Path('elf'),0x600,4),struct.pack('<I',0x03e00008))
            with self.assertRaises(ValueError):elf_function_bytes(Path('elf'),0x600,8)
            with self.assertRaises(ValueError):symbol_extent(Path('elf'),'other')
