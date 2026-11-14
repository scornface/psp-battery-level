/* Exercise target address classification only; fake addresses are never read. */
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
