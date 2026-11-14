/* SPDX-License-Identifier: MIT
 * Plugin lifecycle and power sampling. No native node writes or filesystem
 * operations occur under the worker's PAF lock. See xmb.c for UI ownership.
 */
#include <pspkernel.h>
#include <pspthreadman.h>
#include <psppower.h>
#if BATTERY_DIAGNOSTICS
#include <pspusb.h>
#endif
#include "native.h"
#include "xmb.h"
#include "diagnostics.h"

PSP_MODULE_INFO("PSPBatteryLevel", 0, 0, 9);
PSP_MAIN_THREAD_ATTR(PSP_THREAD_ATTR_USER | PSP_THREAD_ATTR_VFPU);

/* Offline identity remains inspectable even when release has no log. */
#if BATTERY_DIAGNOSTICS
static const char build_identity[] __attribute__((used)) = "PSPBatteryLevel diagnostic " BUILD_ID_TEXT;
#else
static const char build_identity[] __attribute__((used)) = "PSPBatteryLevel release " BUILD_ID_TEXT;
#endif

static SceUID worker = -1;
volatile int stop_requested;
static volatile int worker_finished;
static int hooks_published;

/* KUBridge/SystemCtrl are ARK runtime services, not PSPLink dependencies. */
extern int kuKernelGetModel(void);
extern int kuKernelInitKeyConfig(void);
extern int sctrlSEGetVersion(void);
extern int sctrlHENGetVersion(void);
extern int sctrlHENGetMinorVersion(void);

static int supported_environment(void)
{
    unsigned devkit = sceKernelDevkitVersion(), model = kuKernelGetModel();
    unsigned key = kuKernelInitKeyConfig(), major = sctrlSEGetVersion();
    unsigned minor = sctrlHENGetVersion(), micro = sctrlHENGetMinorVersion();
    DIAG(status.user_devkit = devkit; status.model = model; status.key_config = key;
         status.ark_major = major; status.ark_minor = minor; status.ark_micro = micro);
    /* The observed user devkit value on Sony 6.61 is 0x06060010. ARK's API
     * reports 4/20/69, not r206: module signatures remain mandatory as well.
     */
    return devkit == 0x06060010 && model == 1 && key == 0x100
        && major == 4 && minor == 20 && micro == 69;
}

static int run(SceSize size, void *arg)
{
    (void)size; (void)arg;
#if BATTERY_DIAGNOSTICS
    unsigned started = sceKernelGetSystemTimeLow();
#endif
    if (!supported_environment()) { status.outcome = -12; goto failed; }
    int result = -1;
    /* Module loading and UI construction are asynchronous. Retry readiness
     * for up to 30 seconds, but reject a discovered incompatible module now.
     */
    for (unsigned i = 0; i < 300 && !stop_requested; ++i) {
#if BATTERY_DIAGNOSTICS
        NativeDiscovery discovery;
        result = native_discover(&discovery);
        status.paf_query = discovery.paf_query; status.vsh_query = discovery.vsh_query;
        status.paf_base = discovery.paf_base; status.vsh_base = discovery.vsh_base;
        status.paf_size = discovery.paf_size; status.vsh_size = discovery.vsh_size;
        status.discovery_checks = discovery.checks;
#else
        result = native_discover(0);
#endif
        if (result == 0 || result == -2) break;
        sceKernelDelayThread(100000);
    }
    if (result < 0) { status.outcome = result; goto failed; }
    if (!signatures()) { status.outcome = -2; goto failed; }
    result = -10;
    for (unsigned i = 0; i < 300 && !stop_requested; ++i) {
        if (xmb_ready()) {
            if (xmb_lock() < 0) { result = -3; break; }
            result = xmb_install();
            if (!result) {
                hooks_published = 1;
                DIAG(status.install_us = sceKernelGetSystemTimeLow() - started);
                diagnostics_begin(&status);
            }
            xmb_unlock();
            if (!result) break;
        }
        sceKernelDelayThread(100000);
    }
    if (result) { status.outcome = result; goto failed; }
    /* No constructors run here: the hooks create Text in the verified Sony
     * callback. Snapshot diagnostic state only while owning the native lock.
     */
    diagnostics_poll();
    for (;;) {
        int exists = scePowerIsBatteryExist(), percent = scePowerGetBatteryLifePercent();
#if BATTERY_DIAGNOSTICS
        int raw_percent = percent, charging = scePowerIsBatteryCharging();
        int ac = scePowerIsPowerOnline(), usb_driver = sceUsbGetDrvState("USBStor_Driver");
#endif
        if (exists != 1 || percent < 0 || percent > 100) percent = -1;
        int locked = xmb_lock();
        if (locked < 0) {
            /* Do not inspect nodes/shared state after a failed lock. */
            xmb_request_failure(-3);
            diagnostics_lock_failed(locked);
            break;
        }
        DIAG(if (percent >= 0 && status.desired < 0)
                 status.valid_since_us = sceKernelGetSystemTimeLow();
             status.raw_percent = raw_percent; status.exists = exists;
             status.charging = charging; status.ac = ac; status.usb_driver = usb_driver);
        status.desired = percent;
        int installed = status.installed;
        diagnostics_capture(&status);
        xmb_unlock();
        if (!installed) { diagnostics_terminal(); break; }
        diagnostics_poll();
        sceKernelDelayThread(1000000);
    }
    worker_finished = 1;
    return 0;
failed:
    diagnostics_failure(&status);
    worker_finished = 1;
    return 0;
}

int module_start(SceSize size, void *arg)
{
    (void)size; (void)arg;
    worker = sceKernelCreateThread("battery_level", run, 0x30, 0x8000,
                                  PSP_THREAD_ATTR_USER | PSP_THREAD_ATTR_VFPU, 0);
    if (worker < 0) { worker_finished = 1; return worker; }
    int result = sceKernelStartThread(worker, 0, 0);
    if (result < 0) { sceKernelDeleteThread(worker); worker = -1; worker_finished = 1; }
    return result;
}

int module_stop(SceSize size, void *arg)
{
    (void)size; (void)arg;
    stop_requested = 1;
    /* Cleanup belongs to the callback. If USB/suspend pauses callbacks, refuse
     * unload instead of leaving hooks pointing into freed plugin memory.
     */
    for (unsigned i = 0; !worker_finished && i < 30; ++i) sceKernelDelayThread(100000);
    if (!worker_finished) return -1;
    if (worker >= 0) {
        unsigned timeout = 100000;
        if (sceKernelWaitThreadEnd(worker, &timeout) < 0) return -1;
        if (hooks_published && !xmb_can_unload()) return -1;
        sceKernelDeleteThread(worker); worker = -1;
    }
    return 0;
}
