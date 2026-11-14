/* SPDX-License-Identifier: MIT
 * Event-driven canonical/presentation ownership. All calls require the adapter's
 * verified binding, interrupt context and exclusion. Never writes native flags.
 */
#ifndef HOME_BAR_SESSION_H
#define HOME_BAR_SESSION_H
#include "bar_policy.h"
#include "bar_words.h"
#define HOME_INLINE static inline __attribute__((always_inline))

enum {
    HOME_BAR_IDLE,
    HOME_BAR_CAPTURE,
    HOME_BAR_REPLACE
};

typedef struct {
    uint16_t canonical[HOME_BAR_PIXELS] __attribute__((aligned(4)));
    uint16_t presentation[HOME_BAR_PIXELS] __attribute__((aligned(4)));
    /* presented tracks pixel ownership, including suspended output. wait_full
     * blocks ordinary reuse; it does not prove Sony has cleared those pixels. */
    unsigned presented, canonical_valid, wait_full, action, percent, left;
    unsigned width; /* Committed width, not a newer worker publication. */
    unsigned restores, captures, retired, conflicts, drawn;
    unsigned fault_site;
} HomeBarSession;

HOME_INLINE unsigned home_bar_profile(
    const HomeNativeState *live, const HomeBinding *binding, const HomeSprite *shape
)
{
    HomeNativeState local = *live;
    local.b8 |= 1u; /* Permit Sony's already-pending full update, no live store. */
    HomeBarPlan plan;
    return home_bar_plan(&local, binding, shape, &plan);
}

HOME_INLINE void home_bar_retire(HomeBarSession *bar)
{
    /* Suspension is not cleanup. Retain the exact output and its canonical
     * source while any extended pixels may remain live. Repeated rejected
     * callbacks must not repeatedly report the same suspension. */
    if ((bar->presented || bar->canonical_valid) && !bar->wait_full) {
        ++bar->retired;
        bar->wait_full = 1;
    }
    if (!bar->presented) {
        bar->canonical_valid = 0;
    }
}

HOME_INLINE unsigned home_bar_conflict(HomeBarSession *bar, unsigned site)
{
    ++bar->conflicts;
    bar->fault_site = site;
    home_bar_retire(bar);
    return 8;
}

/* Both recovery and battery updates must restore the same exact old output.
 * Callers validate scene/binding first and decide whether suspension ends. */
HOME_INLINE unsigned home_bar_restore(HomeBarSession *bar, volatile uint16_t *native)
{
    if (home_bar_restore32(native, 512u * 272u, bar->presentation, bar->canonical)) {
        return home_bar_conflict(bar, 2);
    }
    ++bar->restores;
    return 0;
}

HOME_INLINE unsigned home_bar_before(
    HomeBarSession *bar,
    const HomeNativeState *live,
    const HomeBinding *binding,
    const HomeSprite *shape,
    const HomeSprite *frame,
    volatile uint16_t *native
)
{
    bar->action = HOME_BAR_IDLE;
    unsigned reason = home_bar_bound(live, binding);
    if (reason) {
        return reason;
    }

    unsigned profile = home_bar_profile(live, binding, shape);
    if (profile) {
        /* Unknown transition pixels belong to Sony. No compare/restore here.
         * A subsequent fully validated post-state may be captured only if this
         * invocation necessarily took +6a7c: exact normal a4, bit 0 clear.
         */
        home_bar_retire(bar);
        if (live->a4 == 0x50102u && !(live->b8 & 1u)) {
            bar->action = HOME_BAR_CAPTURE;
        }
        return profile;
    }

    unsigned full = !(live->b8 & 1u);
    /* Only a fully accepted scene may discharge residual output. Do this
     * BEFORE the wait gate and before Sony can perform a partial battery copy.
     * The entire strip must still match, with the same measured boundary. */
    if (bar->wait_full && bar->presented && !full) {
        if (!bar->canonical_valid || live->left != bar->left) {
            return home_bar_conflict(bar, 1);
        }
        unsigned restored = home_bar_restore(bar, native);
        if (restored) {
            return restored;
        }
        bar->presented = bar->wait_full = 0;
    }
    if (bar->wait_full && !full) {
        return 11;
    }
    if (full) {
        /* +5d0(1) clears the ENTIRE owned strip before native recomposition.
         * A stale previous presentation must not be restored over that work.
         */
        bar->action = HOME_BAR_CAPTURE;
        return 0;
    }
    if (bar->presented && live->left != bar->left) {
        return home_bar_conflict(bar, 1);
    }

    unsigned battery_dirty = !(live->b8 & 0x80u);
    if (bar->presented && (battery_dirty || !frame)) {
        unsigned restored = home_bar_restore(bar, native);
        if (restored) {
            return restored;
        }
        bar->presented = 0;
    }
    if (battery_dirty || !bar->canonical_valid) {
        bar->action = HOME_BAR_CAPTURE;
    } else if (frame &&
               (!bar->presented || frame->percent != bar->percent || frame->width != bar->width)) {
        bar->action = HOME_BAR_REPLACE;
    }
    return 0;
}

HOME_INLINE unsigned home_bar_after(
    HomeBarSession *bar,
    const HomeNativeState *live,
    const HomeBinding *binding,
    const HomeSprite *shape,
    const HomeSprite *frame,
    volatile uint16_t *native
)
{
    unsigned action = bar->action;
    bar->action = HOME_BAR_IDLE;

    /* CAPTURE with residual presentation is exclusively a pending native full
     * rebuild (restoration clears presented). Do not forget its pixels until
     * the same bound invocation reports the normal completed full-clear path.
     * Menu caches may still be cold; no capture/composition is allowed there. */
    unsigned bound = home_bar_bound(live, binding);
    if (bound) {
        home_bar_retire(bar);
        return bound;
    }
    if (action == HOME_BAR_CAPTURE && live->a4 == 0x50102u && (live->b8 & 1u)) {
        bar->presented = bar->canonical_valid = 0;
        bar->wait_full = 0;
    }

    unsigned reason = home_bar_profile(live, binding, shape);
    /* Do not capture a pending refresh or broaden the post-state flag set. */
    if (!reason && !(live->b8 & 1u)) {
        reason = 4;
    }
    if (reason) {
        home_bar_retire(bar);
        /* A completed full clear already discharged ownership above, even if
         * Sony's other menu caches are cold. Retire cannot re-suspend an empty
         * session; defer capture without demanding another full refresh. */
        return reason;
    }

    if (action == HOME_BAR_IDLE) {
        return 0; /* ZERO strip accesses on clean frames. */
    }
    if (action == HOME_BAR_CAPTURE) {
        if (home_bar_capture32(native, 512u * 272u, bar->canonical, HOME_BAR_PIXELS)) {
            return home_bar_conflict(bar, 6);
        }
        bar->canonical_valid = 1;
        bar->wait_full = 0;
        bar->presented = 0;
        bar->left = live->left;
        ++bar->captures;
    } else if (bar->presented) {
        /* Power-only replacement must retain canonical pixels, not restore them
         * on screen. Validate ALL old output before generating/writing new output.
         */
        if (home_bar_match32(native, 512u * 272u, bar->presentation, HOME_BAR_PIXELS)) {
            return home_bar_conflict(bar, 3);
        }
    }
    if (!frame) {
        return 9;
    }
    if (!bar->canonical_valid || (action != HOME_BAR_CAPTURE && live->left != bar->left)) {
        return home_bar_conflict(bar, 4);
    }

    if (home_bar_compose(
            bar->canonical, HOME_BAR_PIXELS, live->left, frame, bar->presentation, HOME_BAR_PIXELS
        )) {
        return home_bar_conflict(bar, 5);
    }
    if (home_bar_present32(native, 512u * 272u, bar->presentation, HOME_BAR_PIXELS)) {
        return home_bar_conflict(bar, 6);
    }
    bar->presented = 1;
    bar->percent = frame->percent;
    bar->left = live->left;
    bar->width = frame->width;
    ++bar->drawn;
    return 0;
}

#undef HOME_INLINE
#endif
