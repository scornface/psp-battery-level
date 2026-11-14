/* Shared synthetic tile preparation, never an expected-pixel oracle. */
#ifndef TEST_HOME_TILES_H
#define TEST_HOME_TILES_H
#include <assert.h>
#include "sprite.h"

static void prepare_test_tiles(HomeTiles *tiles)
{
    uint16_t atlas[2400];
    unsigned char percent[121] = {0};
    for (unsigned i = 0; i < 2400; ++i) {
        atlas[i] = 0x9ce7;
    }
    for (unsigned digit = 0; digit < 10; ++digit) {
        for (unsigned x = 0; x < (digit == 1 ? 6u : 11u); ++x) {
            atlas[digit * 240 + x] = 0xffff;
        }
    }
    for (unsigned i = 0; i < 11; ++i) {
        percent[i * 11 + i] = 15;
    }
    assert(home_tiles_prepare(tiles, atlas, 2400, percent, 11, 11) == 0);
}
#endif
