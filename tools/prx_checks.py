"""Shared bounded ELF access and the verified integer-only HOME callback ABI."""
import struct
from prx_libraries import bounded_read


def target(words, hi, lo):
    low = words[lo] & 0xffff
    return ((words[hi] & 0xffff) << 16) + (low - 0x10000 if low & 0x8000 else low)


def hook_template():
    words=[0x27bdffa0,0xafbf0010,0xafbc0014];refs=[]
    for reg,offset in ((2,24),(3,28),(4,32),(5,36),(6,40),(7,44),(8,48),(9,52)):
        words.append(0xafa00000 | reg<<16 | offset)
    words += [0x00004010,0xafa8003c,0x00004012,0xafa80040,0x8fa40010]
    def reference(name,lo):
        refs.append((len(words),len(words)+1,name));words.extend([0x3c190000,lo])
    reference('home_before',0x27390000)
    words += [0x0320f809,0,0xafa20044,0x8fa8003c,0x01000011,0x8fa80040,0x01000013]
    for reg,offset in ((2,24),(3,28),(4,32),(5,36),(6,40),(7,44),(8,48),(9,52),(28,20)):
        words.append(0x8fa00000 | reg<<16 | offset)
    reference('original',0x8f390000)
    words += [0x0320f809,0,0xafa20018,0xafa3001c,0x00004010,0xafa8003c,0x00004012,0xafa80040,0x8fa40010,0x8fa50044]
    reference('home_after',0x27390000)
    words += [0x0320f809,0,0x8fa8003c,0x01000011,0x8fa80040,0x01000013,
              0x8fa20018,0x8fa3001c,0x8fbc0014,0x8fbf0010,0x03e00008,0x27bd0060]
    return words,refs


def check_helper(module, address, size):
    if address & 3 or size < 4 or size & 3:raise ValueError('Invalid helper extent')
    module.require_range(address,size,executable=True)
    calls={stub for lib in module.imports() if lib['name']=='InterruptManagerForKernel' for stub in lib['stubs']}
    integer_ops={1,4,5,6,7,8,9,10,11,12,13,14,15,20,21,22,23,32,33,35,36,37,40,41,43}
    special={0,2,3,4,6,7,10,11,15,16,17,18,19,24,25,26,27,32,33,34,35,36,37,38,39,42,43}
    for at in range(address,address+size,4):
        w=module.u32(at);op=w>>26
        if op in (2,3):
            destination=(w&0x3ffffff)*4
            if destination not in calls and not (op==2 and address<=destination<address+size):
                raise ValueError('Helper calls outside interrupt primitives')
        elif op==0:
            if w&63==8:
                if w!=0x03e00008:raise ValueError('Unexpected indirect helper jump')
            elif w&63 not in special:raise ValueError('Unexpected helper special instruction')
        elif op==31:
            if w&63 not in (0,4):raise ValueError('Unexpected helper SPECIAL3 instruction')
        elif op not in integer_ops:raise ValueError('Non-integer or unsupported helper instruction')
        if op==1 and (w>>16)&31 not in (0,1,2,3):raise ValueError('Unexpected helper REGIMM instruction')
        if op in (1,4,5,6,7,20,21,22,23):
            low=w&0xffff;destination=at+4+(low-0x10000 if low&0x8000 else low)*4
            if not address<=destination<address+size:raise ValueError('Helper branch escapes its extent')


def symbol_extent(elf,name):
    data=bounded_read(elf,32*1024*1024)
    if len(data)<52 or data[:7]!=b'\x7fELF\x01\x01\x01':raise ValueError('Expected ELF32 companion')
    offset=struct.unpack_from('<I',data,32)[0];entry_size,count=struct.unpack_from('<HH',data,46)
    if entry_size!=40 or not 0<count<=1024 or offset+count*40>len(data):raise ValueError('Invalid ELF section table')
    sections=[struct.unpack_from('<10I',data,offset+i*40) for i in range(count)];found=[]
    for section in sections:
        if section[1]!=2:continue
        start,size,link,entry=section[4],section[5],section[6],section[9]
        if entry!=16 or size%entry or start+size>len(data) or link>=count:raise ValueError('Invalid symbol table')
        strings=sections[link]
        if strings[4]+strings[5]>len(data):raise ValueError('Invalid symbol strings')
        names=data[strings[4]:strings[4]+strings[5]]
        for at in range(start,start+size,16):
            n,value,length,info,other,index=struct.unpack_from('<IIIBBH',data,at)
            if n>=len(names):raise ValueError('Invalid symbol name')
            end=names.find(b'\0',n)
            if end<0:raise ValueError('Unterminated symbol')
            if names[n:end]==name.encode() and info&15==2 and index:found.append((value,length))
    if len(found)!=1:raise ValueError('Missing or ambiguous helper symbol')
    return found[0]


def elf_function_bytes(elf,address,size):
    data=bounded_read(elf,32*1024*1024)
    if len(data)<52 or data[:7]!=b'\x7fELF\x01\x01\x01' or struct.unpack_from('<HHI',data,16) not in ((2,8,1),(0xffa0,8,1)):
        raise ValueError('Unexpected companion ELF type/machine')
    start=struct.unpack_from('<I',data,28)[0];entry,count=struct.unpack_from('<HH',data,42)
    if entry!=32 or not 0<count<=16 or start+count*entry>len(data):raise ValueError('Invalid companion program headers')
    candidates=[]
    for i in range(count):
        kind,offset,vaddr,paddr,filesz,memsz,flags,align=struct.unpack_from('<8I',data,start+i*32)
        if kind!=1:continue
        if filesz>memsz or offset+filesz>len(data):raise ValueError('Invalid companion segment')
        if flags&1 and vaddr<=address and address+size<=vaddr+filesz:
            at=offset+address-vaddr;candidates.append(data[at:at+size])
    if len(candidates)!=1:raise ValueError('Companion helper is not uniquely executable/file-backed')
    return candidates[0]
