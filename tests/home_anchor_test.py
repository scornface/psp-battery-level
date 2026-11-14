"""Actual-width anchoring, no accumulated shifts, and native/session boundaries."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CODE = r'''
#include <assert.h>
#include <string.h>
#include "bar_session.h"
static HomeBarSession bar;
static uint16_t storage[512*272+4] __attribute__((aligned(4)));
static uint16_t saved[512*272+4], canonical[HOME_BAR_PIXELS], output[HOME_BAR_PIXELS+2];
static uint16_t *native=storage+2;
static HomeSprite sprite;
static HomeBinding binding={42,0x8a100000u,0xaa100000u};
static HomeNativeState s={42,0x8a100000u,0xaa100000u,512,272,0x50102,0x3bf,338,1,1,0,0,2,0,0x6800};
static void source(unsigned left) {
    s.left=left;
    for(unsigned y=0;y<17;++y) for(unsigned x=0;x<228;++x)
        canonical[y*228+x]=x<left-250?0x9ce7:(uint16_t)(0x8000+y*228+x);
}
static void shape(unsigned percent) {
    sprite.percent=percent;sprite.height=15;
    sprite.width=percent==100?44:percent<10?21+percent%3:32+percent%8;
    for(unsigned i=0;i<960;++i)sprite.pixels[i]=(uint16_t)(0xc000+i+percent);
}
static void verify(const uint16_t *shown) {
    unsigned shift=sprite.width+4, px=228-sprite.width;
    /* Independent pixel oracle: include Sony's rounded alignment column. */
    unsigned start=s.left-250;
    if(start>shift)--start;
    for(unsigned y=0;y<17;++y) for(unsigned x=0;x<228;++x) {
        uint16_t expected=0x9ce7;
        if(x+shift>=start && x+shift<228)expected=canonical[y*228+x+shift];
        if(y<15 && x>=px)expected=sprite.pixels[y*64+x-px];
        assert(shown[y*228+x]==expected);
    }
}
static void verify_native(void) {
    verify(bar.presentation);
    assert(bar.presented && bar.width==sprite.width && bar.percent==sprite.percent);
    for(unsigned y=0;y<272;++y)for(unsigned x=0;x<512;++x)
        assert(native[y*512+x]==((y>=5 && y<22 && x>=250 && x<478)?bar.presentation[(y-5)*228+x-250]:0x1234));
    assert(storage[0]==0x1234 && storage[1]==0x1234 && storage[512*272+2]==0x1234 && storage[512*272+3]==0x1234);
}
static unsigned before(const HomeSprite *frame) {
    return home_bar_before(&bar,&s,&binding,&sprite,frame,native);
}
static unsigned after(const HomeSprite *frame) {
    return home_bar_after(&bar,&s,&binding,&sprite,frame,native);
}
static void native_full(unsigned left) {
    source(left);
    for(unsigned y=0;y<17;++y)for(unsigned x=0;x<228;++x)native[(y+5)*512+250+x]=canonical[y*228+x];
    s.b8=0x3bf;
}
int main(void) {
    shape(100);
    /* Every supported width, even/odd left and output canary, independent
     * reference for movement, four-pixel gap and fixed inclusive right=477. */
    for(unsigned left=301;left<=450;++left) {
        source(left);
        for(unsigned width=1;width<=47;++width) {
            sprite.width=width;
            HomeBarPlan plan;
            assert(home_bar_plan(&s,&binding,&sprite,&plan)==0);
            assert(plan.shift==width+4 && plan.percent_x+width==478);
            assert(plan.battery_x+28+4==plan.percent_x);
            assert(plan.moved_left==left-width-4);
            output[0]=output[HOME_BAR_PIXELS+1]=0x1234;
            assert(home_bar_compose(canonical,HOME_BAR_PIXELS,left,&sprite,output+1,HOME_BAR_PIXELS)==0);
            verify(output+1);
            assert(output[0]==0x1234 && output[HOME_BAR_PIXELS+1]==0x1234);
        }
    }
    /* Preserve Sony's meaningful alignment column; never crop unknown pixels. */
    source(338);sprite.width=37;canonical[87]=0xabcd;
    assert(home_bar_compose(canonical,HOME_BAR_PIXELS,338,&sprite,output+1,HOME_BAR_PIXELS)==0);
    assert(output[1+87-41]==0xabcd);
    canonical[0]=0xbeef;memcpy(saved,output,sizeof(output));
    assert(home_bar_compose(canonical,HOME_BAR_PIXELS,338,&sprite,output+1,HOME_BAR_PIXELS)==-2);
    assert(!memcmp(saved,output,sizeof(output)));
    s.left=300;HomeBarPlan plan;assert(home_bar_plan(&s,&binding,&sprite,&plan)==5);
    s.left=451;assert(home_bar_plan(&s,&binding,&sprite,&plan)==5);
    /* Repeated shrinking/growing widths must always use canonical pixels,
     * not translate the old presentation or leave text/icon tails behind. */
    for(unsigned i=0;i<512*272+4;++i)storage[i]=0x1234;
    shape(100);native_full(338);assert(before(&sprite)==0 && after(&sprite)==0);verify_native();
    static const unsigned transitions[]={99,100,9,10,11,8,0,100,1,99,10,9,100};
    for(unsigned i=0;i<sizeof(transitions)/sizeof(*transitions);++i) {
        shape(transitions[i]);memcpy(saved,storage,sizeof(storage));
        assert(before(&sprite)==0 && !memcmp(saved,storage,sizeof(storage)));
        assert(after(&sprite)==0);verify_native();
        assert(bar.restores==0 && bar.captures==1);
    }
    for(unsigned p=0;p<=100;++p) {
        shape(p);assert(before(&sprite)==0 && after(&sprite)==0);verify_native();
    }
    /* Width-only changes must also recompose and commit their new width. */
    --sprite.width;assert(before(&sprite)==0 && bar.action==HOME_BAR_REPLACE);
    assert(after(&sprite)==0);verify_native();
    for(unsigned i=0;i<4000;++i) {
        assert(home_bar_before(&bar,&s,&binding,&sprite,&sprite,0)==0);
        assert(home_bar_after(&bar,&s,&binding,&sprite,&sprite,0)==0);
    }
    /* Native partial battery update retains original canonical coordinates. */
    s.b8=0x33f;assert(before(&sprite)==0 && !bar.presented);
    for(unsigned y=0;y<17;++y)for(unsigned x=0;x<228;++x)assert(native[(y+5)*512+250+x]==canonical[y*228+x]);
    for(unsigned y=0;y<17;++y)for(unsigned x=200;x<228;++x)
        native[(y+5)*512+250+x]=canonical[y*228+x]=0xabcd;
    s.b8=0x3bf;shape(9);assert(after(&sprite)==0);verify_native();
    /* Suspension keeps the old geometry until exact restoration; a narrower
     * publication during the pause cannot replace the restoration source. */
    s.b8=0x3b9;assert(before(&sprite)==4);s.b8=0x3bb;shape(100);
    assert(after(&sprite)==4 && bar.width!=sprite.width && bar.presented);
    s.b8=0x33f;assert(before(&sprite)==0 && !bar.presented && !bar.wait_full);
    for(unsigned y=0;y<17;++y)for(unsigned x=0;x<228;++x)assert(native[(y+5)*512+250+x]==canonical[y*228+x]);
    s.b8=0x3bf;assert(after(&sprite)==0);verify_native();
    assert(before(0)==0 && after(0)==0 && !bar.presented);
    shape(1);assert(before(&sprite)==0 && after(&sprite)==0);verify_native();
    for(unsigned left=301;left<=450;left+=49) {
        s.b8=0x3be;assert(before(&sprite)==0);native_full(left);
        shape(left%101);assert(after(&sprite)==0);verify_native();
    }
    shape(99);assert(before(&sprite)==0);native[21*512+477]^=1;
    memcpy(saved,storage,sizeof(storage));
    assert(after(&sprite)==8 && bar.fault_site==3);
    assert(!memcmp(saved,storage,sizeof(storage)));
    return 0;
}
'''


class HomeAnchorTests(unittest.TestCase):
    def test_geometry_and_session(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build/tests') as directory:
            binary = Path(directory)/'anchor'
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c99', '-O3',
                            '-fstrict-aliasing', '-Wall', '-Wextra', '-Werror',
                            '-I', str(ROOT/'src/home'), '-x', 'c', '-', '-o', str(binary)],
                           input=CODE, text=True, check=True)
            subprocess.run([str(binary)], check=True)
