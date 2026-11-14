/* SPDX-License-Identifier: MIT
 * Optional outer lifecycle/GAME snapshots. Worker only, after native snapshots
 * have released exclusion. VSH keeps its original separate user diagnostics.
 */
#include <pspkernel.h>
#include <pspiofilemgr.h>
#include <pspusb.h>
#include "diagnostics.h"
#include "../home/backend.h"

void battery_boot_log(unsigned context, int outcome, int terminal)
{
    static const char *const names[] = {"context", "outcome", "published", "fault",
        "fault_site", "drawn", "restores", "captures", "retired", "conflicts",
        "presented", "suspended", "shown", "width", "terminal", "start_us", "time_us"};
    static unsigned previous[15], have_previous, written, session, have_session;
    unsigned time = sceKernelGetSystemTimeLow();
    if (!have_session) { session = time; have_session = 1; }
    HomeStatus s = home_status();
    unsigned values[] = {context, (unsigned)outcome, s.published, s.fault,
        s.fault_site, s.drawn, s.restores, s.captures, s.retired, s.conflicts,
        s.presented, s.suspended, s.percent, s.width, terminal != 0, session, time};
    unsigned changed = !have_previous;
    for (unsigned i = 0; i < 15; ++i) if (values[i] != previous[i]) changed = 1;
    /* Budget limits diagnostic I/O only, never worker/power/render lifetime.
     * Failed USB/I/O attempts do not consume it or acknowledge a snapshot. */
    if (!changed || (written >= 256 && !terminal) || sceUsbGetDrvState("USBStor_Driver") == 1) return;
    char buffer[768];
    unsigned used = 0;
    const char *prefix = "runtime build_id=00030004";
    while (*prefix) buffer[used++] = *prefix++;
    for (unsigned i = 0; i < 17; ++i) {
        buffer[used++] = ' ';
        const char *name = names[i];
        while (*name) buffer[used++] = *name++;
        buffer[used++] = '=';
        for (int shift = 28; shift >= 0; shift -= 4)
            buffer[used++] = "0123456789abcdef"[(values[i] >> shift) & 15];
    }
    const char *end = " end_runtime\n";
    while (*end) buffer[used++] = *end++;
    SceUID fd = sceIoOpen("ms0:/SEPLUGINS/battery-level-runtime.log",
                          PSP_O_WRONLY | PSP_O_CREAT | PSP_O_APPEND, 0777);
    if (fd < 0) return;
    unsigned offset = 0;
    while (offset < used) {
        int n = sceIoWrite(fd, buffer + offset, used - offset);
        if (n <= 0 || (unsigned)n > used - offset) break;
        offset += (unsigned)n;
    }
    int closed = sceIoClose(fd);
    if (offset != used || closed < 0) return;
    for (unsigned i = 0; i < 15; ++i) previous[i] = values[i];
    have_previous = 1;
    ++written;
}
