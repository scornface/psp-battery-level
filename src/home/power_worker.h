/* SPDX-License-Identifier: MIT */
#ifndef HOME_POWER_WORKER_H
#define HOME_POWER_WORKER_H
#include "power_frames.h"

typedef struct {
    int exists, percent, preparation, publication;
    unsigned generation;
} HomePowerSample;

/* Call only from the single sampler worker, normally at 1 Hz. Tiles are
 * immutable, state starts zero-initialized, and frames are module-owned for
 * the entire resident lifetime. No native/UI memory access occurs here.
 */
int home_power_poll(HomePowerFrames *state, const HomeTiles *tiles, HomePowerSample *sample);
#endif
