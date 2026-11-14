"""Context exclusivity and actual loader/stop code with mocked PSP services."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL_HEADER = r'''
#ifndef TEST_PSP_KERNEL_H
#define TEST_PSP_KERNEL_H
#include <stddef.h>
typedef int SceUID;
typedef unsigned SceSize;
typedef struct {unsigned size;int mpidtext,mpiddata;unsigned flags;unsigned char position,access;unsigned short reserved;} SceKernelLMOption;
typedef struct {unsigned attribute;char modname[28];unsigned nsegment,segmentaddr[4],segmentsize[4],text_addr,text_size;} SceModule;
#define PSP_MEMORY_PARTITION_USER 2
#define PSP_SMEM_Low 0
#define PSP_MODULE_INFO(a,b,c,d)
SceUID sceKernelLoadModuleBufferForKernel(SceSize,void *,int,SceKernelLMOption *);
int sceKernelStartModule(int,unsigned,void *,int *,void *);
int sceKernelStopModule(int,unsigned,void *,int *,void *);
int sceKernelUnloadModule(int);
SceModule *sceKernelFindModuleByUID(int);
SceModule *sceKernelFindModuleByName(const char *);
int sceKernelCreateThread(const char *,int (*)(SceSize,void *),int,int,unsigned,void *);
int sceKernelStartThread(int,unsigned,void *);
int sceKernelDeleteThread(int);
int sceKernelWaitThreadEnd(int,unsigned *);
int sceKernelDelayThread(unsigned);
unsigned sceKernelCpuSuspendIntr(void);
void sceKernelCpuResumeIntr(unsigned);
unsigned sceKernelDevkitVersion(void);
unsigned sceKernelGetModel(void);
unsigned sceKernelInitKeyConfig(void);
unsigned sctrlSEGetVersion(void);
unsigned sctrlHENGetVersion(void);
unsigned sctrlHENGetMinorVersion(void);
#endif
'''
VSH_CODE = r'''
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <pspkernel.h>
#include "vsh.h"
extern unsigned char battery_vsh_image[128];
static SceModule module;
static int failure,loads,starts,stops,unloads;
SceUID sceKernelLoadModuleBufferForKernel(SceSize size,void *data,int flags,SceKernelLMOption *option) {
    assert(size==128 && data==battery_vsh_image && !flags);
    assert(option->size==sizeof(*option) && option->mpidtext==2 && option->mpiddata==2);
    assert(!option->position && !option->flags && !option->access);
    ++loads;return failure==1?-1:42;
}
SceModule *sceKernelFindModuleByUID(int id) {assert(id==42);return &module;}
SceModule *sceKernelFindModuleByName(const char *name) {
    assert(!strcmp(name,"PSPBatteryLevel"));return failure==11?&module:0;
}
int sceKernelStartModule(int id,unsigned n,void *p,int *status,void *option) {
    assert(id==42 && !n && !p && !option);++starts;
    *status=failure==9?-1:0;return failure==5?-1:0;
}
int sceKernelStopModule(int id,unsigned n,void *p,int *status,void *option) {
    assert(id==42 && !n && !p && !option);++stops;
    *status=failure==8?-1:0;return failure==6?-1:0;
}
int sceKernelUnloadModule(int id) {assert(id==42);++unloads;return failure==7 || failure==10?-1:0;}
int main(int argc,char **argv) {
    assert(argc==2);failure=atoi(argv[1]);
    strcpy(module.modname,"PSPBatteryLevel");module.nsegment=2;
    module.segmentaddr[0]=module.text_addr=0x08810000;module.text_size=0x1000;module.segmentsize[0]=0x1000;
    module.segmentaddr[1]=0x08820000;module.segmentsize[1]=0x100;
    if(failure==2 || failure==10)module.modname[0]='X';
    if(failure==3)module.segmentaddr[1]=0x88000000;
    if(failure==4)module.attribute=0x1000;
    int result=battery_vsh_start();
    if(failure==11){assert(result==-24 && !loads && !starts && !unloads);return 0;}
    assert(loads==1);
    if(failure==1){assert(result==-21 && !starts);assert(battery_vsh_stop()==0 && !unloads);return 0;}
    if(failure>=2 && failure<=4){assert(result==-22 && !starts && unloads==1);assert(battery_vsh_stop()==0);return 0;}
    if(failure==10) {
        assert(result==-22 && !starts && unloads==1);
        assert(battery_vsh_start()==-20 && loads==1);
        assert(battery_vsh_stop()==-1);
        failure=0;assert(battery_vsh_stop()==0 && !stops);return 0;
    }
    assert(result==(failure==5 || failure==9?-23:0));
    assert(starts==1 && !unloads);
    assert(battery_vsh_start()==-20 && loads==1);
    if(failure==6 || failure==7 || failure==8) {
        assert(battery_vsh_stop()==-1);
        if(failure!=7)assert(!unloads);
        failure=0;assert(battery_vsh_stop()==0);
    } else assert(battery_vsh_stop()==0);
    assert(battery_vsh_stop()==0);
    return 0;
}
'''
BOOT_CODE = r'''
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <pspkernel.h>
#include "context.h"
#include "../home/backend.h"
int module_start(SceSize,void *);
int module_stop(SceSize,void *);
static int mode,held,published,vsh_started,vsh_stopped,home_started,deleted,ran;
static int (*entry)(SceSize,void *);
static volatile int *stop_pointer;
unsigned sceKernelDevkitVersion(void){return 0x06060010;}
unsigned sceKernelGetModel(void){return 1;}
unsigned sceKernelInitKeyConfig(void){return mode==2?0x300:mode==1?0x200:0x100;}
unsigned sctrlSEGetVersion(void){return 4;}
unsigned sctrlHENGetVersion(void){return 20;}
unsigned sctrlHENGetMinorVersion(void){return 69;}
int sceKernelCreateThread(const char *name,int (*f)(SceSize,void *),int priority,int stack,unsigned attr,void *option) {
    assert(!strcmp(name,"battery_bootstrap") && priority==0x30 && stack==0x8000 && !attr && !option);
    entry=f;return mode==3?-1:42;
}
int sceKernelStartThread(int id,unsigned n,void *p) {
    assert(id==42 && !n && !p);
    if(mode==4)return -1;
    if(mode!=5){ran=1;entry(0,0);}return 0;
}
int sceKernelDeleteThread(int id){assert(id==42);++deleted;return 0;}
int sceKernelWaitThreadEnd(int id,unsigned *timeout){assert(id==42 && *timeout==100000);return mode==6?-1:0;}
int sceKernelDelayThread(unsigned n){assert(n==100000);if(!ran && entry){ran=1;entry(0,0);}return 0;}
unsigned sceKernelCpuSuspendIntr(void){assert(!held);held=1;return 123;}
void sceKernelCpuResumeIntr(unsigned irq){assert(held && irq==123);held=0;}
int battery_vsh_start(void){assert(!held && !home_started);++vsh_started;return 0;}
int battery_vsh_stop(void){assert(!held);++vsh_stopped;return mode==7?-1:0;}
int home_can_unload(void){assert(held);return !published;}
int home_run(volatile int *stop,void (*poll)(void)) {
    assert(!held && !vsh_started && !poll);++home_started;stop_pointer=stop;
    assert(!*stop);published=1;return 0;
}
int main(int argc,char **argv) {
    assert(argc==2);mode=atoi(argv[1]);
    int result=module_start(0,0);
    if(mode==3){assert(result==-1 && !deleted);assert(module_stop(0,0)==0);return 0;}
    if(mode==4){assert(result==-1 && deleted==1);assert(module_stop(0,0)==0);return 0;}
    assert(result==0);
    assert(module_start(0,0)==-1);
    if(mode==1) {
        assert(home_started==1 && !vsh_started && stop_pointer && !*stop_pointer);
        assert(module_stop(0,0)==-1 && !*stop_pointer && !deleted && !vsh_stopped);return 0;
    }
    assert(module_stop(0,0)==(mode==6 || mode==7?-1:0));
    assert(!home_started);
    if(mode==2 || mode==5)assert(!vsh_started);
    else assert(vsh_started==1);
    if(mode==6)assert(!vsh_stopped && !deleted);
    if(mode==7)assert(vsh_stopped==1 && !deleted);
    return 0;
}
'''


class BootstrapTests(unittest.TestCase):
    def compile_and_run(self, code, source, scenarios):
        with tempfile.TemporaryDirectory(dir=ROOT/'build/tests') as directory:
            p=Path(directory);(p/'pspkernel.h').write_text(KERNEL_HEADER)
            for name in ('pspmodulemgr_kernel.h','psploadcore.h','pspinit.h','pspintrman_kernel.h','systemctrl.h','systemctrl_se.h'):
                (p/name).write_text('#include "pspkernel.h"\n')
            binary=p/'bootstrap'
            extra=[]
            if source.endswith('/vsh.c'):
                prefix='_' if sys.platform=='darwin' else ''
                image=prefix+'battery_vsh_image';end=prefix+'battery_vsh_image_end'
                asm=p/'payload.S'
                asm.write_text(f'.data\n.p2align 6\n.globl {image}\n.globl {end}\n{image}:\n.space 128\n{end}:\n')
                extra=['-x','assembler-with-cpp',str(asm)]
            subprocess.run([os.environ.get('CC','cc'),'-std=c99','-O2','-Wall','-Wextra','-Werror',
                            '-DBATTERY_DIAGNOSTICS=0','-I',str(p),'-I',str(ROOT/'src/bootstrap'),
                            '-x','c','-',str(ROOT/source),*extra,'-o',str(binary)],input=code,text=True,check=True)
            for scenario in scenarios:subprocess.run([str(binary),str(scenario)],check=True)

    def test_user_payload_abi_placement_and_failure_ownership(self):
        self.compile_and_run(VSH_CODE,'src/bootstrap/vsh.c',range(12))

    def test_dispatch_and_refusal_to_unload_live_game(self):
        self.compile_and_run(BOOT_CODE,'src/bootstrap/main.c',range(8))

    def test_context_guards_and_explicit_pops_refusal(self):
        code=r'''
#include <assert.h>
#include "context.h"
int main(void) {
    assert(battery_context(0x06060010,1,0x100,4,20,69)==BATTERY_VSH);
    assert(battery_context(0x06060010,1,0x200,4,20,69)==BATTERY_GAME);
    for(unsigned key=0;key<0x500;++key)
        if(key!=0x100 && key!=0x200)assert(!battery_context(0x06060010,1,key,4,20,69));
    assert(!battery_context(0x06060010,0,0x100,4,20,69));
    assert(!battery_context(0x06060000,1,0x100,4,20,69));
    assert(!battery_context(0x06060010,1,0x200,5,20,69));
    assert(!battery_context(0x06060010,1,0x200,4,21,69));
    assert(!battery_context(0x06060010,1,0x200,4,20,70));
    return 0;
}
'''
        self.compile_and_run(code,'src/bootstrap/support.c',[0])
