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
from tooling_test import fixture


class Runtime:
    name='PSPBatteryRuntime';info_address=0x100;entry=0x200
    def __init__(self,payload):
        self.image=bytearray(0x4000)
        struct.pack_into('<I',self.image,0x100,0xa1000)
        identity=b'PSPBatteryRuntime release 00030003\0';self.image[0x120:0x120+len(identity)]=identity
        self.image[0x1000:0x1000+len(payload)]=payload
        for address,path in ((0xa00,b'flash0:/kd/resource/impose.rsc\0'),(0xb00,b'flash0:/font/ltn8.pgf\0')):
            self.image[address:address+len(path)]=path
        self.symbols=dict(battery_vsh_image=0x1000,battery_vsh_image_end=0x1000+len(payload),
                          home_callback=0x400,home_before=0x600,home_after=0x700,home_original=0x800)
        words,refs=hook_template()
        for hi,lo,name in refs:words[lo]|=self.symbols['home_original' if name=='original' else name]
        self.image[0x400:0x400+len(words)*4]=struct.pack(f'<{len(words)}I',*words)
        for at in (0x600,0x700):struct.pack_into('<I',self.image,at,0x03e00008)
        self.records=[];stub=0x3000
        for name,(version,attribute,nids) in gate.IMPORTS.items():
            ns=sorted(nids);stubs=list(range(stub,stub+len(ns)*8,8));stub+=len(ns)*8
            self.records.append(dict(name=name,words=5,version=version,attribute=attribute,
                                     var_count=0,func_count=len(ns),nids=ns,stubs=stubs))
        self.system=dict(name='<module-table>',version=0,attribute=0x8000,func_count=2,var_count=1,
                         nids=[gate.nid('module_start'),gate.nid('module_stop'),gate.nid('module_info')],
                         addresses=[0x200,0x240,0x100])
    def imports(self):return self.records
    def exports(self):return [self.system]
    def u32(self,at):return struct.unpack_from('<I',self.image,at)[0]
    def require_range(self,address,size,executable=False):
        if address<0 or size<0 or address+size>len(self.image):raise ValueError('range')
        if executable and not (0x200<=address and address+size<=0x900):raise ValueError('executable range')


class IntegratedChecks(unittest.TestCase):
    def setUp(self):
        self.payload=bytes(fixture());self.child=Prx.parse(self.payload);self.runtime=Runtime(self.payload)
    def check(self):
        m=self.runtime
        with patch.object(gate.Prx,'open',return_value=self.child),patch.object(gate,'symbols',return_value=m.symbols), \
             patch.object(gate,'bounded_read',return_value=self.payload), \
             patch.object(gate,'symbol_extent',side_effect=lambda elf,name:(m.symbols[name],4)), \
             patch.object(gate,'elf_function_bytes',return_value=struct.pack('<I',0x03e00008)):
            return gate.check(Path('runtime'),Path('elf'),Path('payload'),module=m)
    def test_valid(self):self.assertEqual(self.check(),'release')
    def test_previous_build_identity_rejected(self):
        identity=b'PSPBatteryRuntime release 00030001\0'
        self.runtime.image[0x120:0x120+len(identity)]=identity
        with self.assertRaises(ValueError):self.check()

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
