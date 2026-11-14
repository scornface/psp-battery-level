"""Raw-word transfer equivalence, strict aliasing, canaries and complete preflight."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

WORDS_CODE=r'''
#include <assert.h>
#include <string.h>
#include "bar_words.h"
enum { FRAME=512*272 };
static uint16_t frame[FRAME+4] __attribute__((aligned(4)));
static uint16_t expected[FRAME+4],saved[FRAME+4];
static uint16_t shown[HOME_BAR_PIXELS+4] __attribute__((aligned(4)));
static uint16_t original[HOME_BAR_PIXELS+4] __attribute__((aligned(4)));
static unsigned seed=1;
static uint16_t random_word(void) {seed=seed*1664525u+1013904223u;return (uint16_t)(seed>>9);}
int main(void) {
    uint16_t *native=frame+2,*out=shown+2,*canonical=original+2;
    for(unsigned iteration=0;iteration<256;++iteration) {
        for(unsigned i=0;i<FRAME+4;++i) frame[i]=random_word();
        shown[0]=shown[1]=shown[HOME_BAR_PIXELS+2]=shown[HOME_BAR_PIXELS+3]=0x1234;
        assert(home_bar_capture32(native,FRAME,out,HOME_BAR_PIXELS)==0);
        for(unsigned y=0;y<17;++y) for(unsigned x=0;x<228;++x)
            assert(out[y*228+x]==native[(y+5)*512+250+x]);
        assert(shown[0]==0x1234 && shown[1]==0x1234 && shown[HOME_BAR_PIXELS+2]==0x1234 && shown[HOME_BAR_PIXELS+3]==0x1234);
        assert(home_bar_match32(native,FRAME,out,HOME_BAR_PIXELS)==0);
        for(unsigned i=0;i<HOME_BAR_PIXELS;++i)canonical[i]=random_word();
        memcpy(expected,frame,sizeof(frame));
        for(unsigned y=0;y<17;++y) for(unsigned x=0;x<228;++x)
            expected[2+(y+5)*512+250+x]=canonical[y*228+x];
        assert(home_bar_restore32(native,FRAME,out,canonical)==0);
        assert(!memcmp(expected,frame,sizeof(frame)));
        assert(home_bar_capture32(native,FRAME,out,HOME_BAR_PIXELS)==0);
    }
    /* Every pixel in BOTH halfword lanes must participate in the word match.
     * A mismatch near any row end must not cause prefix restoration stores. */
    for(unsigned i=0;i<HOME_BAR_PIXELS;++i) {
        unsigned at=(i/228+5)*512+250+i%228;
        native[at]^=1;
        assert(home_bar_match32(native,FRAME,out,HOME_BAR_PIXELS)==-2);
        if(i==0 || i%228>=226) {
            memcpy(saved,frame,sizeof(frame));
            assert(home_bar_restore32(native,FRAME,out,canonical)==-2);
            assert(!memcmp(saved,frame,sizeof(frame)));
        }
        native[at]^=1;
    }
    assert(home_bar_match32(native,FRAME,out,HOME_BAR_PIXELS)==0);
    memcpy(saved,frame,sizeof(frame));
    assert(home_bar_present32(native+1,FRAME,canonical,HOME_BAR_PIXELS)==-1);
    assert(home_bar_present32(native,FRAME,canonical+1,HOME_BAR_PIXELS)==-1);
    assert(home_bar_present32(native,FRAME-1,canonical,HOME_BAR_PIXELS)==-1);
    assert(home_bar_present32(native,FRAME,canonical,HOME_BAR_PIXELS-1)==-1);
    assert(home_bar_present32(native,FRAME,native+10,HOME_BAR_PIXELS)==-1);
    assert(home_bar_present32(0,FRAME,canonical,HOME_BAR_PIXELS)==-1);
    assert(home_bar_match32(native,FRAME,0,HOME_BAR_PIXELS)==-1);
    assert(home_bar_restore32(native,FRAME,out,canonical+1)==-1);
    assert(home_bar_capture32(native+1,FRAME,out,HOME_BAR_PIXELS)==-1);
    assert(home_bar_capture32(native,FRAME,out+1,HOME_BAR_PIXELS)==-1);
    assert(home_bar_capture32(native,FRAME,native,HOME_BAR_PIXELS)==-1);
    assert(!memcmp(saved,frame,sizeof(frame)));
    return 0;
}
'''

PHYSICAL_CODE=r'''
#include <assert.h>
#include "bar_words.h"
int main(void) {
    volatile uint16_t *native=(volatile uint16_t *)(uintptr_t)0xaa100000u;
    assert(home_bar_word_range(native,512*272,(uint16_t *)(uintptr_t)0x88010000u,HOME_BAR_PIXELS));
    assert(!home_bar_word_range(native,512*272,(uint16_t *)(uintptr_t)0x8a100000u,HOME_BAR_PIXELS));
    assert(!home_bar_word_range(native,512*272,(uint16_t *)(uintptr_t)0x8a100004u,HOME_BAR_PIXELS));
    assert(!home_bar_word_range(native,512*272,(uint16_t *)(uintptr_t)0xaa200000u,HOME_BAR_PIXELS));
    assert(!home_bar_word_range((volatile uint16_t *)(uintptr_t)0x8a100000u,512*272,(uint16_t *)(uintptr_t)0x88010000u,HOME_BAR_PIXELS));
    assert(home_bar_word_range(native,512*272,(uint16_t *)(uintptr_t)(0x8a100000u+512*272*2),HOME_BAR_PIXELS));
    assert(home_bar_word_range(native,512*272,(uint16_t *)(uintptr_t)(0x8a100000u-HOME_BAR_PIXELS*2),HOME_BAR_PIXELS));
    assert(!home_bar_word_range(native,512*272,(uint16_t *)(uintptr_t)(0x8a100000u-HOME_BAR_PIXELS*2+4),HOME_BAR_PIXELS));
    return 0;
}
'''

class HomeBarWordTests(unittest.TestCase):
    def test_word_transfers_and_all_halfword_mismatches(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build/tests') as directory:
            binary=Path(directory)/'words'
            subprocess.run([os.environ.get('CC','cc'),'-std=c99','-O3','-fstrict-aliasing','-Wall','-Wextra','-Werror',
                            '-I',str(ROOT/'src/home'),'-x','c','-','-o',str(binary)],input=WORDS_CODE,text=True,check=True)
            subprocess.run([str(binary)],check=True)

    def test_target_alias_identity_without_dereferencing_fake_addresses(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build/tests') as directory:
            binary=Path(directory)/'physical'
            subprocess.run([os.environ.get('CC','cc'),'-std=c99','-O2','-Wall','-Wextra','-Werror','-D__mips__=1',
                            '-I',str(ROOT/'src/home'),'-x','c','-','-o',str(binary)],input=PHYSICAL_CODE,text=True,check=True)
            subprocess.run([str(binary)],check=True)
