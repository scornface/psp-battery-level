"""Single-worker back-buffer staging/guarded publication model, no PSP APIs."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HomePowerFramesTests(unittest.TestCase):
    def test_all_values_invalid_samples_and_back_buffer_visibility(self):
        code=r'''
#include <assert.h>
#include <string.h>
#include "power_frames.h"
#include "refresh_policy.h"
static HomePowerFrames state;
static HomeTiles tiles;
static uint16_t atlas[2400];
static unsigned char percent[121];
int main(void) {
    HomeRefreshState refresh={0};
    unsigned token=home_refresh_begin(&refresh);
    assert(token && home_refresh_begin(&refresh)==0);
    assert(home_refresh_finish(&refresh,0)==0 && refresh.busy==token);
    assert(home_refresh_finish(&refresh,token+1)==-1 && refresh.busy==token);
    assert(home_refresh_finish(&refresh,token)==1 && !refresh.busy);
    assert(home_refresh_finish(&refresh,token)==-1);
    refresh.serial=0xffffffffu;
    assert(home_refresh_begin(&refresh)==1);
    assert(home_refresh_finish(&refresh,1)==1);
    for(unsigned i=0;i<2400;++i) atlas[i]=0x9ce7;
    for(unsigned n=0;n<10;++n) for(unsigned x=0;x<(n==1?6u:11u);++x) atlas[n*240+x]=0xffff;
    for(unsigned i=0;i<11;++i) percent[i*11+i]=15;
    assert(home_tiles_prepare(&tiles,atlas,2400,percent,11,11)==0);
    assert(!home_power_front(&state));
    for(unsigned value=0;value<=100;++value) {
        HomePowerUpdate update;
        HomeSprite before=state.frames[state.front];
        unsigned front=state.front, valid=state.valid;
        assert(home_power_stage(&state,&tiles,1,(int)value,&update)==0);
        assert(state.front==front && state.valid==valid);
        assert(memcmp(&before,&state.frames[front],sizeof(before))==0);
        if(valid) assert(home_power_front(&state)->percent==value-1);
        assert(update.slot==(front^1u) && update.valid==1);
        assert(home_power_commit(&state,&update)==0);
        assert(home_power_front(&state)->percent==value && state.generation==value+1);
    }
    for(unsigned n=0;n<4;++n) {
        int exists=n==0?0:n==1?-1:1;
        int sample=n==2?-1:n==3?101:50;
        HomePowerUpdate update;
        assert(home_power_stage(&state,&tiles,exists,sample,&update)==0 && !update.valid);
        assert(home_power_commit(&state,&update)==0 && !home_power_front(&state));
    }
    HomePowerUpdate update;
    assert(home_power_stage(&state,&tiles,1,42,&update)==0);
    assert(home_power_commit(&state,&update)==0 && home_power_front(&state)->percent==42);
    HomePowerUpdate bad={state.front,1,42};
    unsigned generation=state.generation;
    assert(home_power_commit(&state,&bad)==-1 && state.generation==generation);
    state.front=2;
    assert(!home_power_front(&state));
    assert(home_power_stage(&state,&tiles,1,42,&update)==-1);
    return 0;
}
'''
        with tempfile.TemporaryDirectory(dir=ROOT/'build/tests') as directory:
            source=Path(directory)/'power.c';source.write_text(code);binary=Path(directory)/'power'
            subprocess.run([os.environ.get('CC','cc'),'-std=c99','-O2','-Wall','-Wextra','-Werror',
                            '-I',str(ROOT/'src/home'),str(source),str(ROOT/'src/home/sprite.c'),'-o',str(binary)],check=True,capture_output=True)
            subprocess.run([str(binary)],check=True)
