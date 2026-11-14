"""Residual ownership regression: the photographed sequence, scalar and packed."""
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
static uint16_t native[512*272] __attribute__((aligned(4))), saved[512*272];
static HomeSprite sprite;
static HomeBinding binding={42,0x8a100000u,0xaa100000u};
static HomeNativeState s;
static unsigned before(const HomeSprite *f) {
    return home_bar_before(&bar,&s,&binding,&sprite,f,native);
}
static unsigned after(const HomeSprite *f) {
    return home_bar_after(&bar,&s,&binding,&sprite,f,native);
}
static void sony_full(void) {
    for(unsigned y=0;y<17;++y) for(unsigned x=0;x<228;++x)
        native[(y+5)*512+250+x]=x<88?0x9ce7:(uint16_t)(0x8000+y*228+x);
    s.b8=0x3bf;
}
static void matches(const uint16_t *pixels) {
    for(unsigned y=0;y<17;++y) for(unsigned x=0;x<228;++x)
        assert(native[(y+5)*512+250+x]==pixels[y*228+x]);
}
static void start(void) {
    memset(&bar,0,sizeof(bar));
    s=(HomeNativeState){42,0x8a100000u,0xaa100000u,512,272,0x50102,0x3bf,338,1,1,0,0,2,0,0x6800};
    sprite.width=36;sprite.height=15;sprite.percent=86;
    for(unsigned i=0;i<960;++i)sprite.pixels[i]=0xffff;
    sony_full();assert(before(&sprite)==0 && after(&sprite)==0);
    assert(bar.presented && bar.canonical_valid);matches(bar.presentation);
}
static void suspend(void) {
    s.b8=0x3b9;
    assert(before(&sprite)==4);
    s.b8=0x3bb;assert(after(&sprite)==4);
    assert(bar.presented && bar.canonical_valid && bar.wait_full && bar.retired==1);
    /* Unknown scenes cannot read pixels, even with residual ownership. */
    for(unsigned i=0;i<100;++i) {
        assert(home_bar_before(&bar,&s,&binding,&sprite,&sprite,0)==4);
        assert(home_bar_after(&bar,&s,&binding,&sprite,&sprite,0)==4);
    }
    assert(bar.retired==1);matches(bar.presentation);
}
int main(void) {
    /* Exact failure sequence: suspend, then Sony requests a partial update.
     * Restore MUST precede Sony, and composition must use its new canonical. */
    start();suspend();s.b8=0x33f;
    assert(before(&sprite)==0 && bar.restores==1 && !bar.presented && !bar.wait_full);
    matches(bar.canonical);
    for(unsigned y=5;y<22;++y)for(unsigned x=450;x<478;++x)native[y*512+x]=0xabcd;
    s.b8=0x3bf;assert(after(&sprite)==0 && bar.presented && bar.captures==2);
    unsigned battery_x=450-home_bar_shift(sprite.width);
    for(unsigned y=5;y<22;++y)for(unsigned x=battery_x;x<battery_x+28;++x)assert(native[y*512+x]==0xabcd);
    matches(bar.presentation);assert(!bar.conflicts);
    /* The actual trace first returns to clean accepted flags: recover there,
     * without waiting for the subsequent native battery or minute refresh. */
    start();suspend();s.b8=0x3bf;
    assert(before(&sprite)==0 && bar.restores==1 && !bar.presented);
    matches(bar.canonical);assert(after(&sprite)==0 && bar.presented);
    for(unsigned i=0;i<4000;++i) {
        assert(home_bar_before(&bar,&s,&binding,&sprite,&sprite,0)==0);
        assert(home_bar_after(&bar,&s,&binding,&sprite,&sprite,0)==0);
    }
    assert(bar.restores==1 && bar.drawn==2);
    sprite.percent=85;
    assert(before(&sprite)==0 && after(&sprite)==0 && bar.percent==85);
    assert(bar.restores==1 && bar.drawn==3 && !bar.wait_full);
    matches(bar.presentation);
    /* Invalid power recovers to Sony-only pixels, not another shifted bar. */
    start();suspend();s.b8=0x3bf;
    assert(before(0)==0 && after(0)==0 && !bar.presented);matches(bar.canonical);
    assert(before(&sprite)==0 && after(&sprite)==0 && bar.presented);
    /* A full native rebuild needs no stale restore, even if Sony already
     * changed pixels. Responsibility is discharged only after completion. */
    start();suspend();s.b8=0x3be;native[5*512+250]^=1;
    assert(before(&sprite)==0 && bar.presented);
    sony_full();assert(after(&sprite)==0 && bar.presented && !bar.wait_full && !bar.restores);
    /* Unknown post-state / incomplete full path cannot erase responsibility. */
    start();suspend();s.b8=0x3be;assert(before(&sprite)==0);
    s.a4=0x80050102u;s.b8=0x800003beu;
    assert(after(&sprite)==4 && bar.presented && bar.canonical_valid && bar.wait_full);
    /* Complete full clear with cold menu caches removes residuals, but never
     * composes until the original conservative scene guard accepts them. */
    start();suspend();s.b8=0xbe;assert(before(&sprite)==4);
    sony_full();s.b8=0xbf;
    assert(after(&sprite)==4 && !bar.presented && !bar.canonical_valid && !bar.wait_full);
    s.b8=0x3bf;assert(before(&sprite)==0 && after(&sprite)==0 && bar.presented);
    /* No stale write on full-strip mismatch, changed boundary or binding.
     * These faults retain responsibility but do not bypass any guard. */
    for(unsigned mode=0;mode<4;++mode) {
        start();suspend();s.b8=0x33f;
        if(mode==0) native[21*512+477]^=1;
        if(mode==1) ++s.left;
        if(mode==2) s.draw+=64;
        if(mode==3) bar.canonical_valid=0;
        memcpy(saved,native,sizeof(native));
        assert(before(&sprite)==(mode==2?2:8));
        assert(bar.presented && bar.wait_full);
        assert(!memcmp(saved,native,sizeof(native)));
    }
    /* A binding change between phases cannot authorize post-phase cleanup. */
    start();suspend();s.b8=0x3be;assert(before(&sprite)==0);
    sony_full();s.draw+=64;
    assert(after(&sprite)==2 && bar.presented && bar.wait_full);
    /* A post-only rejection must also retain residual output. */
    start();assert(before(&sprite)==0);s.b8=0x3bb;
    assert(after(&sprite)==4 && bar.presented && bar.canonical_valid && bar.wait_full);
    s.b8=0x33f;assert(before(&sprite)==0 && !bar.presented && bar.restores==1);
    /* Every original scene guard still blocks all pixel access, not just b8. */
    for(unsigned guard=0;guard<9;++guard) {
        start();suspend();s.b8=0x3bf;
        if(guard==0)s.a4=0x80050102u;
        if(guard==1)s.active=0;
        if(guard==2)s.battery=0;
        if(guard==3)s.offset_y=1;
        if(guard==4)s.transition=1;
        if(guard==5)s.format_state=1;
        if(guard==6)s.bar_mode=1;
        if(guard==7)s.resource_state=0;
        if(guard==8)s.left=250;
        assert(home_bar_before(&bar,&s,&binding,&sprite,&sprite,0)!=0);
        assert(home_bar_after(&bar,&s,&binding,&sprite,&sprite,0)!=0);
        assert(bar.presented && bar.wait_full && !bar.restores);
    }
    return 0;
}
'''


class HomeRecoveryTests(unittest.TestCase):
    def test_residual_ownership(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build/tests') as directory:
            binary = Path(directory)/'recovery'
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c99', '-O3',
                            '-fstrict-aliasing', '-Wall', '-Wextra', '-Werror',
                            '-I', str(ROOT/'src/home'), '-x', 'c', '-', '-o', str(binary)],
                           input=CODE, text=True, check=True)
            subprocess.run([str(binary)], check=True)
