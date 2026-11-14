/* SPDX-License-Identifier: MIT
 * Keep the existing PAF implementation in a genuine user module. A user thread
 * executing kernel-linked callbacks would not preserve that boundary.
 */
#include <pspkernel.h>
#include <pspmodulemgr_kernel.h>
#include <psploadcore.h>
#include <stddef.h>
#include <stdint.h>
#include "vsh.h"

extern unsigned char battery_vsh_image[], battery_vsh_image_end[];
/* The pinned SDK's sceKernelLoadModuleBuffer prototype swaps these arguments.
 * Use its same-NID ForKernel symbol with the actual 6.61 ABI: size in a0,
 * buffer in a1. Verified export 4e62c48a (+567c/+571c..+572c) retains a1 as
 * base and a0 as size. Do not cast/call the incorrectly typed SDK declaration.
 */
extern SceUID sceKernelLoadModuleBufferForKernel(SceSize size,
                                                 void *buffer,
                                                 int flags,
                                                 SceKernelLMOption *option);
static SceUID child = -1;
static unsigned start_attempted, stopped;

static int user_module(const SceModule *m)
{
    static const char name[] = "PSPBatteryLevel";
    if (!m || (m->attribute & 0x1000) || !m->nsegment || m->nsegment > 4)
        return 0;
    for (unsigned i = 0; i < sizeof(name); ++i)
        if (m->modname[i] != name[i])
            return 0;
    for (unsigned i = 0; i < m->nsegment; ++i) {
        unsigned a = m->segmentaddr[i], n = m->segmentsize[i];
        if (n > 0x03800000u || a < 0x08800000u || a > 0x0c000000u - n || (a & 3u))
            return 0;
    }
    return m->text_addr == m->segmentaddr[0] && m->text_size <= m->segmentsize[0];
}

int battery_vsh_start(void)
{
    uintptr_t begin = (uintptr_t)battery_vsh_image, end = (uintptr_t)battery_vsh_image_end;
    if (child >= 0 || (begin & 63u) || end <= begin || end - begin > 512u * 1024u)
        return -20;
    /* Never install a second backend over an already resident standalone copy.
     * Configuration still must enable only one resident plugin per context. */
    if (sceKernelFindModuleByName("PSPBatteryLevel"))
        return -24;
    size_t size = end - begin;
    /* The embedded PRX is structurally verified before the outer build. The
     * kernel buffer is writable/aligned for the module manager, not executed
     * as a payload in place. Explicitly request user text/data partitions. */
    SceKernelLMOption option = {0};
    option.size = sizeof(option);
    option.mpidtext = PSP_MEMORY_PARTITION_USER;
    option.mpiddata = PSP_MEMORY_PARTITION_USER;
    option.position = PSP_SMEM_Low;
    child = sceKernelLoadModuleBufferForKernel(size, battery_vsh_image, 0, &option);
    if (child < 0)
        return -21;
    if (!user_module(sceKernelFindModuleByUID(child))) {
        if (sceKernelUnloadModule(child) >= 0)
            child = -1;
        return -22;
    }
    int status = 0;
    start_attempted = 1;
    int result = sceKernelStartModule(child, 0, 0, &status, 0);
    /* Keep ownership even on ambiguous start failure. Only successful stop /
     * unload can clear it; automatic parent unload must not strand a child. */
    return result < 0 || status < 0 ? -23 : 0;
}

int battery_vsh_stop(void)
{
    if (child < 0)
        return 0;
    if (start_attempted && !stopped) {
        int status = 0;
        if (sceKernelStopModule(child, 0, 0, &status, 0) < 0 || status < 0)
            return -1;
        stopped = 1;
    }
    if (sceKernelUnloadModule(child) < 0)
        return -1;
    child = -1;
    return 0;
}
