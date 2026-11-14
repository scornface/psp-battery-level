/* SPDX-License-Identifier: MIT - measured Impose allocation and scene metadata. */
#ifndef HOME_BINDING_POLICY_H
#define HOME_BINDING_POLICY_H

/* Explicit snapshots, not overlays of Sony memory. callback.c maps each field
 * from measured offsets; retaining a4/b8 names avoids inventing flag semantics. */
typedef struct {
    unsigned block, allocation, draw;
} HomeBinding;

typedef struct {
    unsigned block, allocation, draw, stride, height;
    unsigned a4, b8, left, battery, active, offset_y, transition;
    unsigned format_state, bar_mode, resource_state;
} HomeNativeState;

static inline __attribute__((always_inline)) int home_binding_valid(const HomeBinding *b)
{
    /* Exact PSP-2000 extra-RAM allocation and native uncached alias relation;
     * never infer VRAM or permit a new partition because geometry matches. */
    return b && b->block && !(b->allocation & 63u) && b->allocation >= 0x8a000000u &&
           b->allocation <= 0x8c000000u - 512u * 272u * 2u &&
           b->draw == ((b->allocation & 0x1fffffffu) | 0xa0000000u);
}
#endif
