/* Optional worker logger: I/O retry, partial writes and finite change budget. */
#include <assert.h>
#include <string.h>
#include "diagnostics.h"
#include "../home/backend.h"
static HomeStatus status;
static int usb, fail_open, fail_write, fail_close, opens, closes, active;
static unsigned used, time;
static char line[768];

HomeStatus home_status(void)
{
    assert(!active);
    return status;
}

unsigned sceKernelGetSystemTimeLow(void)
{
    return ++time;
}

int sceUsbGetDrvState(const char *name)
{
    assert(!strcmp(name, "USBStor_Driver"));
    return usb;
}

int sceIoOpen(const char *path, int flags, int mode)
{
    assert(!active && !strcmp(path, "ms0:/SEPLUGINS/battery-level-runtime.log"));
    assert(flags == (2 | 0x100 | 0x200) && mode == 0777);
    ++opens;
    if (fail_open) {
        return -1;
    }
    used = 0;
    active = 1;
    return 42;
}

int sceIoWrite(int id, const void *data, unsigned n)
{
    assert(active && id == 42 && n);
    if (fail_write) {
        return -1;
    }
    if (n > 7) {
        n = 7;
    }
    assert(used + n < sizeof(line));
    memcpy(line + used, data, n);
    used += n;
    line[used] = 0;
    return (int)n;
}

int sceIoClose(int id)
{
    assert(active && id == 42);
    active = 0;
    ++closes;
    return fail_close ? -1 : 0;
}

int main(void)
{
    status.published = 1;
    status.percent = 75;
    status.width = 37;
    usb = 1;
    battery_boot_log(2, 0, 0);
    assert(!opens);
    usb = 0;
    fail_open = 1;
    battery_boot_log(2, 0, 0);
    assert(opens == 1 && !closes);
    fail_open = 0;
    battery_boot_log(2, 0, 0);
    assert(opens == 2 && closes == 1);
    assert(
        strstr(line, "runtime build_id=00030004") && strstr(line, " start_us=") &&
        strstr(line, " time_us=") && strstr(line, " end_runtime\n")
    );
    battery_boot_log(2, 0, 0);
    assert(opens == 2); /* Time alone does not log. */
    status.drawn = 1;
    fail_write = 1;
    battery_boot_log(2, 0, 0);
    assert(opens == 3 && closes == 2);
    fail_write = 0;
    battery_boot_log(2, 0, 0);
    assert(opens == 4 && closes == 3);
    status.drawn = 2;
    fail_close = 1;
    battery_boot_log(2, 0, 0);
    assert(opens == 5 && closes == 4);
    fail_close = 0;
    battery_boot_log(2, 0, 0);
    assert(opens == 6 && closes == 5);
    for (unsigned i = 3; i <= 255; ++i) {
        status.drawn = i;
        battery_boot_log(2, 0, 0);
    }
    int count = opens;
    status.drawn = 256;
    battery_boot_log(2, 0, 0);
    assert(opens == count);
    battery_boot_log(2, 0, 1);
    assert(opens == count + 1 && !active);
    battery_boot_log(2, 0, 1);
    assert(opens == count + 1);
    return 0;
}
