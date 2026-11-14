/* SPDX-License-Identifier: MIT
 * Power calls and glyph composition stay outside interrupt exclusion; only
 * the completed front-index/validity publication is protected. The renderer
 * must hold exclusion for its full read/copy and never retain a frame pointer.
 */
#include <pspkernel.h>
#include <pspintrman_kernel.h>
#include <psppower.h>
#include "power_worker.h"

static inline void publication_barrier(void)
{
#ifdef HOME_POWER_HOST_TEST
    __asm__ volatile("" ::: "memory");
#else
    __asm__ volatile("sync" ::: "memory");
#endif
}

int home_power_poll(HomePowerFrames *state, const HomeTiles *tiles, HomePowerSample *sample)
{
    if (!state || !tiles || !sample) return -1;
    HomePowerSample result;
    result.exists = scePowerIsBatteryExist();
    result.percent = result.exists == 1 ? scePowerGetBatteryLifePercent() : -1;
    HomePowerUpdate update = {state->front, 0, result.percent};
    result.preparation = home_power_stage(state, tiles, result.exists, result.percent, &update);
    /* A preparation failure publishes invalidity, not an old charge as if it
     * were fresh. Invalid front metadata itself is rejected by commit/reader.
     */
    unsigned irq = sceKernelCpuSuspendIntr();
    publication_barrier();
    result.publication = home_power_commit(state, &update);
    result.generation = state->generation;
    publication_barrier();
    sceKernelCpuResumeIntr(irq);
    *sample = result;
    return result.preparation ? result.preparation : result.publication;
}
