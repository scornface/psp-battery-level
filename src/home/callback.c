/* SPDX-License-Identifier: MIT
 * Same conservative pre/Sony/post contract as the verified 0002000f adapter.
 * No time, power, file, allocation, font or native rendering calls here.
 */
#include <pspkernel.h>
#include <pspintrman_kernel.h>
#include "backend_internal.h"

static inline __attribute__((always_inline)) int snapshot(unsigned caller, HomeNativeState *out)
{
    if (caller != home_base + 0x8a0 || *(volatile unsigned *)(home_base + 0xa1d0) != home_state ||
        *(volatile unsigned *)(home_state + 0x1bc) != (unsigned)home_callback) {
        return 0;
    }
    volatile unsigned *s = (volatile unsigned *)home_state;
    HomeNativeState live = {
        s[0x10 / 4],
        s[0x14 / 4],
        s[0x1b8 / 4],
        s[0x18 / 4],
        s[0x1c / 4],
        s[0xa4 / 4],
        s[0xb8 / 4],
        s[0xd0 / 4],
        s[0x60 / 4],
        s[0x190 / 4],
        s[0x158 / 4],
        s[0x170 / 4],
        s[0x4c / 4],
        s[0x340 / 4],
        s[0x1d8 / 4]
    };
    *out = live;
    return 1;
}

unsigned home_before(unsigned caller)
{
    int context = sceKernelIsIntrContext();
    unsigned irq = sceKernelCpuSuspendIntr(), token = 0;
    if (home_refresh.busy || !context || home_fault) {
        goto done;
    }
    HomeNativeState live;
    if (!snapshot(caller, &live)) {
        home_fault = 7;
        goto done;
    }
    unsigned reason = home_bar_bound(&live, &home_binding);
    if (reason) {
        home_fault = reason;
        goto done;
    }
    token = home_refresh_begin(&home_refresh);
    __asm__ volatile("sync" ::: "memory");
    reason = home_bar_before(
        &home_bar,
        &live,
        &home_binding,
        &home_assets.reference,
        home_power_front(&home_power),
        (volatile uint16_t *)live.draw
    );
    __asm__ volatile("sync" ::: "memory");
    if (reason == 8) {
        home_fault = reason;
    }
done:
    sceKernelCpuResumeIntr(irq);
    return token;
}

void home_after(unsigned caller, unsigned token)
{
    int context = sceKernelIsIntrContext();
    unsigned irq = sceKernelCpuSuspendIntr();
    int granted = home_refresh_finish(&home_refresh, token);
    if (!granted) {
        goto done;
    }
    if (granted < 0) {
        home_fault = 10;
        goto done;
    }
    if (!context || home_fault) {
        goto done;
    }
    HomeNativeState live;
    if (!snapshot(caller, &live)) {
        home_fault = 7;
        goto done;
    }
    unsigned reason = home_bar_bound(&live, &home_binding);
    if (reason) {
        home_fault = reason;
        goto done;
    }
    __asm__ volatile("sync" ::: "memory");
    reason = home_bar_after(
        &home_bar,
        &live,
        &home_binding,
        &home_assets.reference,
        home_power_front(&home_power),
        (volatile uint16_t *)live.draw
    );
    __asm__ volatile("sync" ::: "memory");
    if (reason == 8) {
        home_fault = reason;
    }
done:
    sceKernelCpuResumeIntr(irq);
}
