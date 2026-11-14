/* SPDX-License-Identifier: MIT
 * GAME worker lifecycle. Native hook publication is the irreversible boundary;
 * all resource I/O and FPL queries finish outside interrupt exclusion.
 */
#include <pspkernel.h>
#include <pspsysmem_kernel.h>
#include <psploadcore.h>
#include <pspintrman_kernel.h>
#include <stddef.h>
#include "backend.h"
#include "backend_internal.h"
#include "signatures/dispatch.h"
#include "signatures/return.h"
#include "signatures/draw.h"
#include "signatures/cache.h"
#include "signatures/event.h"

typedef char home_module_abi
    [(offsetof(SceModule, text_addr) == 0x6c && offsetof(SceModule, segmentaddr) == 0x80) ? 1 : -1];
HomeAssets home_assets;
HomePowerFrames home_power;
HomeBarSession home_bar;
HomeRefreshState home_refresh;
HomeBinding home_binding;
unsigned home_base, home_state, home_original, home_published;
volatile unsigned home_fault;

static int guards(const Signature *list, unsigned count)
{
    for (unsigned i = 0; i < count; ++i)
        if (*(volatile unsigned *)(home_base + list[i].offset) !=
            signature_word(&list[i], home_base))
            return 0;
    return 1;
}

#define HOME_GUARDS(list) guards(list, sizeof(list) / sizeof((list)[0]))

static int discover(volatile int *stop)
{
    SceModule *m = sceKernelFindModuleByName("sceImpose_Driver");
    if (!m)
        return -1;
    home_base = m->text_addr;
    if ((home_base & 3) || home_base < 0x88000000 || home_base > 0x88400000 - 0xa598 ||
        m->text_size != 0xa1c8 || m->nsegment != 2 || m->segmentaddr[0] != home_base ||
        m->segmentsize[0] != 0xa1c8 || m->segmentaddr[1] != home_base + 0xa1d0 ||
        m->segmentsize[1] != 0x3c8)
        return -2;
    if (!HOME_GUARDS(signatures) || !HOME_GUARDS(post_signatures) ||
        !HOME_GUARDS(draw_signatures) || !HOME_GUARDS(battery_signatures) ||
        !HOME_GUARDS(event_signatures))
        return -3;
    unsigned state = *(volatile unsigned *)(home_base + 0xa1d0);
    if (!state)
        return -1;
    if (state != home_base + 0xa220)
        return -4;
    unsigned irq = sceKernelCpuSuspendIntr();
    HomeBinding binding = {*(volatile unsigned *)(state + 0x10),
                           *(volatile unsigned *)(state + 0x14),
                           *(volatile unsigned *)(state + 0x1b8)};
    int same = *(volatile unsigned *)(state + 0x1bc) == home_base + 0x4790 &&
               *(volatile unsigned *)(state + 0x18) == 512 &&
               *(volatile unsigned *)(state + 0x1c) == 272;
    sceKernelCpuResumeIntr(irq);
    if (!same || !home_binding_valid(&binding))
        return -16;
    SceKernelFplInfo info = {0};
    info.size = sizeof(info);
    if (sceKernelReferFplStatus((SceUID)binding.block, &info) || info.blockSize != 512 * 272 * 2 ||
        info.numBlocks != 1 || info.freeBlocks)
        return -15;
    irq = sceKernelCpuSuspendIntr();
    int result = 0;
    /* Stop and publication share exclusion: unload cannot pass its unpublished
     * check while this worker is installing a callback behind its back. */
    if (*stop || home_published || *(volatile unsigned *)(home_base + 0xa1d0) != state ||
        *(volatile unsigned *)(state + 0x1bc) != home_base + 0x4790 ||
        *(volatile unsigned *)(state + 0x10) != binding.block ||
        *(volatile unsigned *)(state + 0x14) != binding.allocation ||
        *(volatile unsigned *)(state + 0x1b8) != binding.draw)
        result = -5;
    else {
        home_state = state;
        home_original = home_base + 0x4790;
        home_binding = binding;
        __asm__ volatile("sync" ::: "memory");
        *(volatile unsigned *)(state + 0x1bc) = (unsigned)home_callback;
        __asm__ volatile("sync" ::: "memory");
        home_published = 1;
    }
    sceKernelCpuResumeIntr(irq);
    return result;
}

int home_run(volatile int *stop, void (*poll)(void))
{
    if (!stop || home_published)
        return -1;
    /* Scratch is startup-only and cannot leak pointers into installed hooks. */
    SceUID memory = sceKernelAllocPartitionMemory(
        PSP_MEMORY_PARTITION_KERNEL, "battery_assets", PSP_SMEM_Low, sizeof(HomeAssetWorkspace), 0);
    if (memory < 0)
        return -18;
    HomeAssetWorkspace *work = sceKernelGetBlockHeadAddr(memory);
    int result = work ? home_assets_prepare(&home_assets, work) : -18;
    if (sceKernelFreePartitionMemory(memory) < 0)
        return -19;
    if (result || *stop)
        return result ? result : -5;
    HomePowerSample sample;
    if (home_power_poll(&home_power, &home_assets.tiles, &sample))
        return -17;
    for (unsigned i = 0; i < 100 && !*stop; ++i) {
        result = discover(stop);
        if (result != -1)
            break;
        sceKernelDelayThread(100000);
    }
    if (result)
        return result;
    while (!*stop) {
        if (home_power_poll(&home_power, &home_assets.tiles, &sample)) {
            /* Publication invalidates power on preparation failure. Existing
             * callback recovery, not worker pixel writes, handles visibility. */
            result = -17;
        }
        if (poll)
            poll();
        sceKernelDelayThread(1000000);
    }
    return result;
}

HomeStatus home_status(void)
{
    unsigned irq = sceKernelCpuSuspendIntr();
    HomeStatus result = {home_published,
                         home_fault,
                         home_bar.fault_site,
                         home_bar.drawn,
                         home_bar.restores,
                         home_bar.captures,
                         home_bar.retired,
                         home_bar.conflicts,
                         home_bar.presented,
                         home_bar.wait_full,
                         home_bar.percent,
                         home_bar.width};
    sceKernelCpuResumeIntr(irq);
    return result;
}

int home_can_unload(void)
{
    return !home_published;
}
