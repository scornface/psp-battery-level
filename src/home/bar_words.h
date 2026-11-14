/* SPDX-License-Identifier: MIT
 * Aligned raw-word transfers for the SAME 228x17 strip. No blending, cache
 * invalidation, geometry/state changes or native lifetime decisions here.
 * GCC/Clang may_alias explicitly permits representation access to uint16_t
 * storage; do not replace it with an ordinary alias-unsafe uint32_t cast.
 */
#ifndef HOME_BAR_WORDS_H
#define HOME_BAR_WORDS_H
#include "bar_policy.h"
typedef uint32_t HomeBarWord __attribute__((__may_alias__));
typedef char home_bar_word_sizes[(sizeof(HomeBarWord) == 4 && sizeof(uint16_t) == 2 &&
                                  HOME_BAR_WIDTH % 2 == 0 && HOME_BAR_X % 2 == 0)
                                     ? 1
                                     : -1];
#define HB_INLINE static inline __attribute__((always_inline))

/* Validate the whole allocation before any transfer. These checks do not
 * establish native lifetime/ownership; the callback/session must do that first. */
HB_INLINE int home_bar_word_range(const volatile uint16_t *native,
                                  size_t capacity,
                                  const uint16_t *owned,
                                  size_t count)
{
    if (!native || !owned || capacity < 512u * 272u || count < HOME_BAR_PIXELS)
        return 0;
    uintptr_t native_address = (uintptr_t)native, owned_address = (uintptr_t)owned;
    if ((native_address | owned_address) & 3u)
        return 0;
#ifdef __mips__
    /* PSP binding uses KSEG1 for Sony pixels and KSEG0 for owned buffers.
     * Compare physical identities so cached/uncached aliases cannot evade
     * overlap rejection. Host tests instead compare their real object ranges.
     */
    if ((native_address & 0xe0000000u) != 0xa0000000u ||
        (owned_address & 0xe0000000u) != 0x80000000u)
        return 0;
    native_address &= 0x1fffffffu;
    owned_address &= 0x1fffffffu;
#endif
    /* Reject all overlap with the bound allocation, not just the bar. Using
     * differences avoids wrapping end-address arithmetic on the target.
     */
    return native_address <= owned_address ? owned_address - native_address >= 512u * 272u * 2u
                                           : native_address - owned_address >= HOME_BAR_PIXELS * 2u;
}

HB_INLINE int home_bar_capture32(const volatile uint16_t *native,
                                 size_t capacity,
                                 uint16_t *owned,
                                 size_t count)
{
    if (!home_bar_word_range(native, capacity, owned, count))
        return -1;
    HomeBarWord *out = (HomeBarWord *)owned;
    for (unsigned y = 0; y < HOME_BAR_HEIGHT; ++y) {
        const volatile HomeBarWord *row =
            (const volatile HomeBarWord *)(native + (y + HOME_BAR_Y) * 512 + HOME_BAR_X);
        unsigned x = 0;
        for (; x + 4 <= HOME_BAR_WIDTH / 2; x += 4) {
            out[x] = row[x];
            out[x + 1] = row[x + 1];
            out[x + 2] = row[x + 2];
            out[x + 3] = row[x + 3];
        }
        for (; x < HOME_BAR_WIDTH / 2; ++x)
            out[x] = row[x];
        out += HOME_BAR_WIDTH / 2;
    }
    return 0;
}

HB_INLINE int home_bar_present32(volatile uint16_t *native,
                                 size_t capacity,
                                 const uint16_t *owned,
                                 size_t count)
{
    if (!home_bar_word_range(native, capacity, owned, count))
        return -1;
    const HomeBarWord *in = (const HomeBarWord *)owned;
    for (unsigned y = 0; y < HOME_BAR_HEIGHT; ++y) {
        volatile HomeBarWord *row =
            (volatile HomeBarWord *)(native + (y + HOME_BAR_Y) * 512 + HOME_BAR_X);
        unsigned x = 0;
        for (; x + 4 <= HOME_BAR_WIDTH / 2; x += 4) {
            row[x] = in[x];
            row[x + 1] = in[x + 1];
            row[x + 2] = in[x + 2];
            row[x + 3] = in[x + 3];
        }
        for (; x < HOME_BAR_WIDTH / 2; ++x)
            row[x] = in[x];
        in += HOME_BAR_WIDTH / 2;
    }
    return 0;
}

HB_INLINE int home_bar_match32(const volatile uint16_t *native,
                               size_t capacity,
                               const uint16_t *shown,
                               size_t count)
{
    if (!home_bar_word_range(native, capacity, shown, count))
        return -1;
    const HomeBarWord *in = (const HomeBarWord *)shown;
    for (unsigned y = 0; y < HOME_BAR_HEIGHT; ++y) {
        const volatile HomeBarWord *row =
            (const volatile HomeBarWord *)(native + (y + HOME_BAR_Y) * 512 + HOME_BAR_X);
        for (unsigned x = 0; x < HOME_BAR_WIDTH / 2; ++x)
            if (row[x] != in[x])
                return -2;
        in += HOME_BAR_WIDTH / 2;
    }
    return 0;
}

/* Preflight both buffers and compare the ENTIRE presentation before the first
 * store. Reusing present32 only after success prevents partial stale cleanup. */
HB_INLINE int home_bar_restore32(volatile uint16_t *native,
                                 size_t capacity,
                                 const uint16_t *shown,
                                 const uint16_t *canonical)
{
    if (!home_bar_word_range(native, capacity, canonical, HOME_BAR_PIXELS))
        return -1;
    int matched = home_bar_match32(native, capacity, shown, HOME_BAR_PIXELS);
    if (matched)
        return matched;
    return home_bar_present32(native, capacity, canonical, HOME_BAR_PIXELS);
}

#undef HB_INLINE
#endif
