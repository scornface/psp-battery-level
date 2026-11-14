/* SPDX-License-Identifier: MIT
 * Single-worker staging, callback consumption under CPU interrupt exclusion.
 * Sampling itself belongs to the worker (exists==1, percent in 0..100).
 * These functions contain no power, native-memory, locking or I/O calls.
 */
#ifndef HOME_POWER_FRAMES_H
#define HOME_POWER_FRAMES_H
#include "sprite.h"

typedef struct {
    HomeSprite frames[2];
    unsigned front, valid, generation;
} HomePowerFrames;

typedef struct {
    unsigned slot, valid;
    int sampled;
} HomePowerUpdate;

/* Only one worker may stage/publish. The callback never changes front and may
 * only hold a front pointer while exclusion is active. Thus interrupted work
 * on the back cannot affect rendering; after return no reader retains it.
 * The adapter must issue compiler/CPU barriers before publishing and must
 * exclude interrupts for commit and the complete callback read/copy. Ordinary
 * C calls alone do not establish a PSP publication/interrupt contract.
 */
static inline int home_power_stage(
    HomePowerFrames *state, const HomeTiles *tiles, int exists, int percent, HomePowerUpdate *out
)
{
    if (!state || !out || state->front > 1) {
        return -1;
    }
    HomePowerUpdate update = {state->front, 0, percent};
    if (exists == 1 && percent >= 0 && percent <= 100) {
        update.slot = state->front ^ 1u;
        if (home_sprite_compose(tiles, (unsigned)percent, &state->frames[update.slot])) {
            return -2;
        }
        update.valid = 1;
    }
    *out = update;
    return 0;
}

static inline int home_power_commit(HomePowerFrames *state, const HomePowerUpdate *update)
{
    if (!state || !update || state->front > 1 || update->slot > 1 || update->valid > 1) {
        return -1;
    }
    if (update->valid &&
        (update->slot == state->front || update->sampled < 0 || update->sampled > 100 ||
         state->frames[update->slot].percent != (unsigned)update->sampled)) {
        return -1;
    }
    if (update->valid) {
        state->front = update->slot;
    }
    state->valid = update->valid;
    ++state->generation;
    return 0;
}

static inline const HomeSprite *home_power_front(const HomePowerFrames *state)
{
    return state && state->front <= 1 && state->valid == 1 ? &state->frames[state->front] : 0;
}
#endif
