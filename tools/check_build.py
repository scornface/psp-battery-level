#!/usr/bin/env python3
"""Bootstrap/user-payload boundary; exact imports, wrapper and integer helpers."""
import argparse
from pathlib import Path
import struct
from check_vsh import check_module, nid
from prx_checks import hook_template, check_helper, symbol_extent, elf_function_bytes, target
from prx_libraries import Prx, bounded_read

IMPORTS = {
    'SystemCtrlForKernel': (0, 9, {0x1090a2e1, 0x5328b431, 0xb47c9d77}),
    'InitForKernel': (0x11, 9, {0x7233b5bc}),
    'SysMemForKernel': (0, 9, {0x7158ce7e, 0xc886b169, 0xc1a26c6f, 0xf12a62f7, 0x07c586a1}),
    'LoadCoreForKernel': (0, 9, {0xf6b1bf0f, 0x40972e6e}),
    'ThreadManForKernel': (0, 9, {0x446d8de6, 0xceadeb47, 0x9fa03cd3, 0xd8199e4c, 0xf475845d, 0x278c0df5}),
    'InterruptManagerForKernel': (0, 9, {0x5f10d406, 0x092968f4, 0xfe28c6d9}),
    'ModuleMgrForKernel': (0, 9, {0x4e62c48a, 0x3ff74df1, 0xe5d6087b, 0x387e3ca9}),
    'scePower_driver': (0, 9, {0x0afd0d8b, 0x2085d15d}),
    'IoFileMgrForKernel': (0, 9, {0x810c4bc3, 0x109f50bc, 0x6a638d83}),
    'UtilsForKernel': (0, 9, {0x840259f1}),
}


def symbols(elf):
    data = bounded_read(elf, 8 * 1024 * 1024)
    if data[:7] != b'\x7fELF\x01\x01\x01':raise ValueError('Expected little-endian ELF32')
    start = struct.unpack_from('<I', data, 32)[0]
    size, count = struct.unpack_from('<HH', data, 46)
    if size != 40 or start + count * size > len(data):raise ValueError('Invalid ELF sections')
    sections = [struct.unpack_from('<10I', data, start + i * size) for i in range(count)]
    result = {}
    for section in sections:
        if section[1] != 2:continue
        if section[9] != 16 or section[5] % 16 or section[6] >= count:raise ValueError('Invalid ELF symbol table')
        strings = sections[section[6]]
        for s in (section, strings):
            if s[4] + s[5] > len(data):raise ValueError('ELF symbol/string range')
        names = data[strings[4]:strings[4]+strings[5]]
        for at in range(section[4], section[4]+section[5], 16):
            name, value, extent, info, other, index = struct.unpack_from('<IIIBBH', data, at)
            if not index or not name or info >> 4 not in (1,2):continue
            if name >= len(names) or b'\0' not in names[name:]:raise ValueError('Invalid ELF symbol name')
            text = names[name:names.index(0, name)].decode('ascii')
            if text in result and result[text] != value:raise ValueError('Ambiguous symbol')
            result[text] = value
    return result


def check(prx, elf, payload, diagnostic=False, module=None):
    module, child = module if module is not None else Prx.open(prx), Prx.open(payload)
    mode = 'diagnostic' if diagnostic else 'release'
    check_module(child, mode)
    identity = f'PSPBatteryRuntime {mode} '+('00030004' if diagnostic else '00030003')
    if module.name != 'PSPBatteryRuntime' or module.u32(module.info_address) != 0xa1000 \
            or module.image.count(identity.encode()+b'\0') != 1:raise ValueError('Unexpected bootstrap identity')
    expected = {key:(v,a,set(ns)) for key,(v,a,ns) in IMPORTS.items()}
    if diagnostic:
        v,a,ns=expected['IoFileMgrForKernel'];expected['IoFileMgrForKernel']=(v,a,ns|{0x42ec03ac})
        v,a,ns=expected['ThreadManForKernel'];expected['ThreadManForKernel']=(v,a,ns|{0x369ed59d})
        expected['sceUsb_driver']=(0,9,{0x112cc951})
    records = module.imports()
    if len(records)!=len(expected) or {r['name'] for r in records}!=set(expected):
        raise ValueError('Unexpected bootstrap libraries: '+', '.join(r['name'] for r in records))
    for r in records:
        version,attr,nids=expected[r['name']]
        if (r['words'],r['version'],r['attribute'],r['var_count'],r['func_count']) != (5,version,attr,0,len(nids)) \
                or set(r['nids'])!=nids:raise ValueError('Unexpected bootstrap import: '+r['name'])
    exports=module.exports()
    if len(exports)!=1:raise ValueError('Expected system exports only')
    e=exports[0]
    if e['name']!='<module-table>' or e['attribute']!=0x8000 or e['version'] \
            or e['func_count']!=2 or e['var_count']!=1 \
            or set(e['nids'][:2])!={nid('module_start'),nid('module_stop')} \
            or e['nids'][2:]!=[nid('module_info')] or e['addresses'][2]!=module.info_address:
        raise ValueError('Invalid bootstrap exports')
    for at in e['addresses'][:2]:
        if at&3:raise ValueError('Unaligned system function')
        module.require_range(at,4,executable=True)
    if e['addresses'][e['nids'].index(nid('module_start'))]!=module.entry:raise ValueError('Wrong entrypoint')
    syms=symbols(elf)
    begin,end=syms['battery_vsh_image'],syms['battery_vsh_image_end']
    data=bounded_read(payload,512*1024)
    module.require_range(begin,len(data))
    if begin&63 or end-begin!=len(data) or module.image[begin:end]!=data:raise ValueError('Embedded user PRX mismatch/alignment')
    diagnostic_path=b'ms0:/SEPLUGINS/battery-level-runtime.log\0'
    if (diagnostic_path in module.image)!=diagnostic:raise ValueError('Bootstrap diagnostics in wrong mode')
    for path in (b'flash0:/kd/resource/impose.rsc\0',b'flash0:/font/ltn8.pgf\0'):
        if module.image.count(path)!=1:raise ValueError('Missing/ambiguous startup asset path')
    helpers={}
    for name in ('home_before','home_after'):
        at,size=symbol_extent(elf,name);module.require_range(at,size,executable=True)
        if module.image[at:at+size]!=elf_function_bytes(elf,at,size):raise ValueError('Helper/ELF mismatch')
        check_helper(module,at,size) # Interrupt primitives ONLY: no timing/I/O/power calls.
        helpers[name]=at
    words,refs=hook_template();address=syms['home_callback']
    module.require_range(address,len(words)*4,executable=True)
    actual=struct.unpack_from(f'<{len(words)}I',module.image,address)
    variables={i for hi,lo,_ in refs for i in (hi,lo)}
    for i,(w,want) in enumerate(zip(actual,words)):
        if w&(0xffff0000 if i in variables else 0xffffffff)!=want:raise ValueError('Changed Sony wrapper ABI')
    for hi,lo,name in refs:
        wanted=syms['home_original'] if name=='original' else helpers[name]
        if target(actual,hi,lo)!=wanted:raise ValueError('Wrong wrapper reference')
    return mode


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('prx',type=Path,nargs='?',default=Path(__file__).resolve().parents[1]/'build/release/battery_level.prx')
    p.add_argument('--elf',type=Path)
    p.add_argument('--vsh',type=Path);p.add_argument('--mode',choices=('release','diagnostic'),default='release')
    args=p.parse_args()
    args.elf=args.elf or args.prx.with_suffix('.elf')
    args.vsh=args.vsh or args.prx.parent/'vsh-payload.prx'
    try:check(args.prx,args.elf,args.vsh,args.mode=='diagnostic')
    except (OSError,ValueError,KeyError,struct.error) as error:raise SystemExit(str(error)) from error
    print('Integrated '+args.mode+': embedded user PRX exact; kernel imports/wrapper/integer helpers verified; hardware UNVALIDATED')
