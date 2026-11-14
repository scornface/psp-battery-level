/* SPDX-License-Identifier: MIT */
#ifndef HOME_SPRITE_H
#define HOME_SPRITE_H
#include <stddef.h>
#include <stdint.h>

enum {
    HOME_TILE_WIDTH = 16,
    HOME_TILE_HEIGHT = 15,
    HOME_TILE_PIXELS = 240,
    HOME_SPRITE_STRIDE = 64,
    HOME_SPRITE_PIXELS = 64 * 15
};

typedef struct {
    uint16_t pixels[11][HOME_TILE_PIXELS]; /* 0..9, then percent */
    unsigned left[11], right[11];          /* inclusive bright bounds, not shadow */
    unsigned ready;
} HomeTiles;

typedef struct {
    uint16_t pixels[HOME_SPRITE_PIXELS]; /* fixed stride, opaque 5551 */
    unsigned width, height, percent;
} HomeSprite;

/* Owned-memory preparation only. Caller must authenticate the original atlas
 * and font before passing them here. No file loading, native pointers or OS
 * calls belong to this module. Inputs/outputs must not alias. The initialized
 * tiles must remain immutable during composition; publication is caller-owned.
 * Errors leave the output unchanged. Both functions run outside rendering.
 * Uses original-size percent coverage and one blank bright column. Flattened
 * tile overlaps retain brighter foreground, otherwise the darker shadow.
 */
int home_tiles_prepare(
    HomeTiles *out,
    const uint16_t *atlas,
    size_t words,
    const unsigned char *percent,
    unsigned width,
    unsigned height
);
int home_sprite_compose(const HomeTiles *tiles, unsigned percent, HomeSprite *out);
#endif
