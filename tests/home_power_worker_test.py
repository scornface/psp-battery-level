"""Real sampler source with mocked PSP APIs: power calls never hold exclusion."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HomePowerWorkerTests(unittest.TestCase):
    def test_sampler_and_guarded_publication(self):
        code=r'''
#include <assert.h>
#include "power_worker.h"
static int held, exists=1, charge, reads;
static HomePowerFrames state;
static HomeTiles tiles;
static uint16_t atlas[2400];
static unsigned char percent[121];
int scePowerIsBatteryExist(void) { assert(!held); return exists; }
int scePowerGetBatteryLifePercent(void) { assert(!held); ++reads; return charge; }
unsigned sceKernelCpuSuspendIntr(void) { assert(!held); held=1; return 0x123; }
void sceKernelCpuResumeIntr(unsigned irq) { assert(held && irq==0x123); held=0; }
int main(void) {
    for(unsigned i=0;i<2400;++i) atlas[i]=0x9ce7;
    for(unsigned d=0;d<10;++d) for(unsigned x=0;x<(d==1?6u:11u);++x) atlas[d*240+x]=0xffff;
    for(unsigned i=0;i<11;++i) percent[i*11+i]=15;
    assert(home_tiles_prepare(&tiles,atlas,2400,percent,11,11)==0);
    HomePowerSample sample;
    for(charge=0;charge<=100;++charge) {
        assert(home_power_poll(&state,&tiles,&sample)==0);
        assert(!held && sample.percent==charge && sample.exists==1);
        assert(sample.generation==(unsigned)charge+1);
        assert(home_power_front(&state)->percent==(unsigned)charge);
    }
    charge=-1;assert(home_power_poll(&state,&tiles,&sample)==0 && !home_power_front(&state));
    charge=101;assert(home_power_poll(&state,&tiles,&sample)==0 && !home_power_front(&state));
    int previous=reads;exists=0;
    assert(home_power_poll(&state,&tiles,&sample)==0 && !home_power_front(&state));
    assert(reads==previous && sample.percent==-1);
    exists=-1;assert(home_power_poll(&state,&tiles,&sample)==0 && !home_power_front(&state));
    exists=1;charge=42;
    assert(home_power_poll(&state,&tiles,&sample)==0 && home_power_front(&state)->percent==42);
    tiles.ready=0;
    assert(home_power_poll(&state,&tiles,&sample)==-2 && !home_power_front(&state));
    assert(!held);
    return 0;
}
'''
        with tempfile.TemporaryDirectory(dir=ROOT/'build/tests') as directory:
            directory=Path(directory)
            (directory/'pspkernel.h').write_text('unsigned sceKernelCpuSuspendIntr(void);\nvoid sceKernelCpuResumeIntr(unsigned);\n')
            (directory/'pspintrman_kernel.h').write_text('')
            (directory/'psppower.h').write_text('int scePowerIsBatteryExist(void);\nint scePowerGetBatteryLifePercent(void);\n')
            source=directory/'worker.c';source.write_text(code);binary=directory/'worker'
            subprocess.run([os.environ.get('CC','cc'),'-std=c99','-O2','-Wall','-Wextra','-Werror',
                '-DHOME_POWER_HOST_TEST','-I',str(directory),'-I',str(ROOT/'src/home'),str(source),
                str(ROOT/'src/home/power_worker.c'),str(ROOT/'src/home/sprite.c'),'-o',str(binary)],check=True,capture_output=True)
            subprocess.run([str(binary)],check=True)
