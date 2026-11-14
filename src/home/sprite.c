/* SPDX-License-Identifier: MIT
 * Portable private-buffer implementation of the approved offline candidate.
 * There is deliberately no API for copying a sprite to Sony/display memory.
 */
#include "sprite.h"

#define BACKGROUND 0x9ce7u

static uint16_t gray(unsigned value)
{
    return (uint16_t)(0x8000u | value | (value << 5) | (value << 10));
}

static int describe(HomeTiles *tiles, unsigned index)
{
    unsigned left = HOME_TILE_WIDTH, right = 0;
    for (unsigned i = 0; i < HOME_TILE_PIXELS; ++i) {
        unsigned p = tiles->pixels[index][i], x = i % HOME_TILE_WIDTH;
        if (p != gray(p & 31)) {
            return -2;
        }
        if (p > BACKGROUND) {
            if (x < left) {
                left = x;
            }
            if (x > right) {
                right = x;
            }
        }
    }
    if (left == HOME_TILE_WIDTH) {
        return -2;
    }
    tiles->left[index] = left;
    tiles->right[index] = right;
    return 0;
}

int home_tiles_prepare(
    HomeTiles *out,
    const uint16_t *atlas,
    size_t words,
    const unsigned char *percent,
    unsigned width,
    unsigned height
)
{
    if (!out || !atlas || !percent || words != 10 * HOME_TILE_PIXELS || width != 11 ||
        height != 11) {
        return -1;
    }
    for (unsigned i = 0; i < width * height; ++i) {
        if (percent[i] > 15) {
            return -2;
        }
    }
    HomeTiles prepared = {0};
    for (unsigned digit = 0; digit < 10; ++digit) {
        for (unsigned i = 0; i < HOME_TILE_PIXELS; ++i) {
            prepared.pixels[digit][i] = atlas[digit * HOME_TILE_PIXELS + i];
        }
        if (describe(&prepared, digit)) {
            return -2;
        }
    }
    /* Unscaled 11x11 percent, bottom aligned with digit rows 0..12.
     * Fitted shadow: local 3x3 box centered at translated (+1,+2).
     * Opacity is quantized to 991386/1000000 from the offline fit. Integer
     * arithmetic avoids FPU state assumptions. The 16x15 window clips tails,
     * matching the approved preview, not claiming Sony's original algorithm.
     */
    for (int y = 0; y < HOME_TILE_HEIGHT; ++y) {
        for (int x = 0; x < HOME_TILE_WIDTH; ++x) {
            unsigned c = y >= 2 && y < 13 && x < 11 ? percent[(y - 2) * 11 + x] : 0;
            unsigned sum = 0;
            for (int sy = y - 3; sy <= y - 1; ++sy) {
                for (int sx = x - 2; sx <= x; ++sx) {
                    if (sy >= 2 && sy < 13 && sx >= 0 && sx < 11) {
                        sum += percent[(sy - 2) * 11 + sx];
                    }
                }
            }
            const uint64_t denominator = 9u * 15u * 1000000u;
            uint64_t shaded = 7u * (denominator - (uint64_t)991386u * sum);
            uint64_t numerator = shaded * (15u - c) + 31u * c * denominator;
            unsigned value = (unsigned)((numerator + 15u * denominator / 2u) / (15u * denominator));
            prepared.pixels[10][y * HOME_TILE_WIDTH + x] = gray(value);
        }
    }
    if (describe(&prepared, 10)) {
        return -2;
    }
    prepared.ready = 1;
    *out = prepared;
    return 0;
}

int home_sprite_compose(const HomeTiles *tiles, unsigned percent, HomeSprite *out)
{
    if (!tiles || !out || tiles->ready != 1 || percent > 100) {
        return -1;
    }
    unsigned indices[4], count = 0;
    if (percent == 100) {
        indices[count++] = 1;
    }
    if (percent >= 10) {
        indices[count++] = (percent / 10) % 10;
    }
    indices[count++] = percent % 10;
    indices[count++] = 10;
    HomeSprite prepared;
    for (unsigned i = 0; i < HOME_SPRITE_PIXELS; ++i) {
        prepared.pixels[i] = BACKGROUND;
    }
    prepared.width = 0;
    prepared.height = HOME_TILE_HEIGHT;
    prepared.percent = percent;
    unsigned previous_right = 0;
    for (unsigned n = 0; n < count; ++n) {
        unsigned index = indices[n], left = tiles->left[index], right = tiles->right[index];
        if (left > right || right >= HOME_TILE_WIDTH) {
            return -2;
        }
        unsigned x = 0;
        if (n) {
            /* One blank column between inclusive bright bounds, not tile boxes. */
            if (left > previous_right + 2) {
                return -2;
            }
            x = previous_right + 2 - left;
        }
        if (x > HOME_SPRITE_STRIDE - HOME_TILE_WIDTH) {
            return -2;
        }
        previous_right = x + right;
        for (unsigned i = 0; i < HOME_TILE_PIXELS; ++i) {
            uint16_t p = tiles->pixels[index][i];
            if (p != gray(p & 31)) {
                return -2;
            }
            if (p == BACKGROUND) {
                continue;
            }
            unsigned col = x + i % HOME_TILE_WIDTH;
            unsigned at = (i / HOME_TILE_WIDTH) * HOME_SPRITE_STRIDE + col;
            /* Approved compact-preview rule for flattened tile overlap:
             * bright wins; otherwise keep the darker shadow. This changes
             * overlapping shadows, never claims native alpha compositing.
             */
            uint16_t old = prepared.pixels[at];
            if (old > BACKGROUND || p > BACKGROUND) {
                p = old > p ? old : p;
            } else {
                p = old < p ? old : p;
            }
            prepared.pixels[at] = p;
            if (col + 1 > prepared.width) {
                prepared.width = col + 1;
            }
        }
    }
    *out = prepared;
    return 0;
}
