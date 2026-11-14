/* SPDX-License-Identifier: MIT
 * Owned-buffer plan/composition for battery-right percentages. This is NOT a
 * native writer: the adapter must supply a freshly rendered canonical Sony
 * strip, never the previous already-shifted presentation (Sony caches its bar).
 */
#ifndef HOME_BAR_POLICY_H
#define HOME_BAR_POLICY_H
#include "binding_policy.h"
#include "sprite.h"

enum {
    HOME_BAR_X = 250,
    HOME_BAR_Y = 5,
    HOME_BAR_WIDTH = 228,
    HOME_BAR_HEIGHT = 17,
    HOME_BAR_PIXELS = 228 * 17,
    HOME_BAR_RESERVE = 47 + 4
};

typedef struct {
    unsigned native_left, shift, moved_left, battery_x, percent_x, percent_width;
} HomeBarPlan;

/* Width includes every prepared shadow pixel; callers validate it before use. */
static inline __attribute__((always_inline)) unsigned home_bar_shift(unsigned width)
{
    return width + 4u;
}

static inline __attribute__((always_inline)) unsigned home_bar_percent_x(unsigned width)
{
    return HOME_BAR_X + HOME_BAR_WIDTH - width;
}

static inline __attribute__((always_inline)) unsigned home_bar_bound(
    const HomeNativeState *s, const HomeBinding *b
)
{
    if (!s || !home_binding_valid(b)) {
        return 1;
    }
    if (s->block != b->block || s->allocation != b->allocation || s->draw != b->draw) {
        return 2;
    }
    if (s->stride != 512 || s->height != 272) {
        return 3;
    }
    return 0;
}

static inline __attribute__((always_inline)) unsigned home_bar_plan(
    const HomeNativeState *s, const HomeBinding *b, const HomeSprite *sprite, HomeBarPlan *out
)
{
    if (!out || !sprite) {
        return 1;
    }
    unsigned bound = home_bar_bound(s, b);
    if (bound) {
        return bound;
    }
    if (!sprite->width || sprite->width > 47 || sprite->height != 15 || sprite->percent > 100) {
        return 3;
    }
    if (s->a4 != 0x50102 || (s->b8 != 0x33f && s->b8 != 0x3bf) || s->active != 1 ||
        s->battery != 1 || s->offset_y || s->transition || s->format_state != 2 || s->bar_mode ||
        s->resource_state != 0x6800) {
        return 4;
    }
    /* Retain the conservative maximum-slot native boundary guard even when
     * the actual presentation is narrower. No new native scene is accepted. */
    if (s->left < HOME_BAR_X + HOME_BAR_RESERVE || s->left > 450) {
        return 5;
    }
    unsigned shift = home_bar_shift(sprite->width);
    HomeBarPlan p = {
        s->left,
        shift,
        s->left - shift,
        450 - shift,
        home_bar_percent_x(sprite->width),
        sprite->width
    };
    *out = p;
    return 0;
}

/* All input and output objects must be disjoint. */
static inline __attribute__((always_inline)) int home_bar_compose(
    const uint16_t *canonical,
    size_t count,
    unsigned native_left,
    const HomeSprite *sprite,
    uint16_t *output,
    size_t capacity
)
{
    if (!canonical || !output || !sprite || canonical == output || count != HOME_BAR_PIXELS ||
        capacity < HOME_BAR_PIXELS || native_left < HOME_BAR_X + HOME_BAR_RESERVE ||
        native_left > 450 || !sprite->width || sprite->width > 47 || sprite->height != 15 ||
        sprite->percent > 100) {
        return -1;
    }
    unsigned shift = home_bar_shift(sprite->width);
    unsigned percent_x = home_bar_percent_x(sprite->width);
    unsigned prefix = native_left - HOME_BAR_X;
    /* Sony's packed-word copies may round an odd x down by one pixel (see
     * +6abc..+6b50). Preserve that alignment column as native content. Never
     * accept meaningful pixels in the columns that would be cropped. The
     * maximum-slot boundary check above still bounds every supported width.
     */
    if (prefix > shift) {
        --prefix;
    }
    /* Unknown pixels before Sony's measured content boundary block composition.
     * In particular this rejects a strip retaining our old left-side prototype.
     */
    for (unsigned y = 0; y < HOME_BAR_HEIGHT; ++y) {
        for (unsigned x = 0; x < prefix; ++x) {
            if (canonical[y * HOME_BAR_WIDTH + x] != 0x9ce7) {
                return -2;
            }
        }
    }
    for (unsigned i = 0; i < HOME_BAR_PIXELS; ++i) {
        output[i] = 0x9ce7;
    }
    for (unsigned y = 0; y < HOME_BAR_HEIGHT; ++y) {
        for (unsigned x = prefix; x < HOME_BAR_WIDTH; ++x) {
            output[y * HOME_BAR_WIDTH + x - shift] = canonical[y * HOME_BAR_WIDTH + x];
        }
    }
    for (unsigned y = 0; y < sprite->height; ++y) {
        for (unsigned x = 0; x < sprite->width; ++x) {
            output[y * HOME_BAR_WIDTH + percent_x - HOME_BAR_X + x] = sprite->pixels[y * 64 + x];
        }
    }
    return 0;
}
#endif
