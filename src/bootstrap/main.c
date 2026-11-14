/* SPDX-License-Identifier: MIT
 * One installed kernel PRX; exactly one backend per execution context. VSH's
 * existing renderer remains in an embedded, separately loaded user module.
 */
#include <pspkernel.h>
#include <pspinit.h>
#include <pspintrman_kernel.h>
#include <systemctrl.h>
#include <systemctrl_se.h>
#include "context.h"
#include "vsh.h"
#include "diagnostics.h"
#include "../home/backend.h"

PSP_MODULE_INFO("PSPBatteryRuntime", 0x1000, 0, 10);
#if BATTERY_DIAGNOSTICS
static const char identity[] __attribute__((used)) = "PSPBatteryRuntime diagnostic 00030004";
#else
static const char identity[] __attribute__((used)) = "PSPBatteryRuntime release 00030003";
#endif
static SceUID worker = -1;
/* finished ends the bootstrap worker, not necessarily the selected backend.
 * In VSH the child remains resident; in GAME a published hook prevents stop. */
static volatile int stopping, finished;
static unsigned context;
static int outcome;

#if BATTERY_DIAGNOSTICS
static void poll(void)
{
    battery_boot_log(context, outcome, 0);
}
#endif

static int run(SceSize size, void *arg)
{
    (void)size;
    (void)arg;
    if (stopping)
        goto done;
    context = battery_context(sceKernelDevkitVersion(),
                              sceKernelGetModel(),
                              sceKernelInitKeyConfig(),
                              sctrlSEGetVersion(),
                              sctrlHENGetVersion(),
                              sctrlHENGetMinorVersion());
    if (!context) {
        outcome = -12;
        goto done;
    }
    if (context == BATTERY_VSH)
        outcome = battery_vsh_start();
    else {
#if BATTERY_DIAGNOSTICS
        outcome = home_run(&stopping, poll);
#else
        outcome = home_run(&stopping, 0);
#endif
    }
done:
    battery_boot_log(context, outcome, 1);
    finished = 1;
    return 0;
}

int module_start(SceSize size, void *arg)
{
    (void)size;
    (void)arg;
    /* A stopped/failed instance must be unloaded and freshly loaded, not
     * restarted with stale backend ownership or stop/publication state. */
    if (worker >= 0 || finished || stopping)
        return -1;
    worker = sceKernelCreateThread("battery_bootstrap", run, 0x30, 0x8000, 0, 0);
    if (worker < 0) {
        finished = 1;
        return worker;
    }
    int result = sceKernelStartThread(worker, 0, 0);
    if (result < 0) {
        sceKernelDeleteThread(worker);
        worker = -1;
        finished = 1;
    }
    return result;
}

int module_stop(SceSize size, void *arg)
{
    (void)size;
    (void)arg;
    unsigned irq = sceKernelCpuSuspendIntr();
    /* Check unconditionally: context may still be being selected by the worker.
     * Refusal after GAME publication leaves the active renderer running. */
    if (!home_can_unload()) {
        sceKernelCpuResumeIntr(irq);
        return -1;
    }
    stopping = 1;
    sceKernelCpuResumeIntr(irq);
    for (unsigned i = 0; !finished && i < 30; ++i)
        sceKernelDelayThread(100000);
    if (!finished)
        return -1;
    if (worker >= 0) {
        unsigned timeout = 100000;
        if (sceKernelWaitThreadEnd(worker, &timeout) < 0)
            return -1;
    }
    /* A loaded/partly started child is owned even when startup failed. Its own
     * callback cleanup must succeed before either module can be unloaded. */
    if (battery_vsh_stop() < 0)
        return -1;
    if (worker >= 0) {
        if (sceKernelDeleteThread(worker) < 0)
            return -1;
        worker = -1;
    }
    return 0;
}
