/* SPDX-License-Identifier: MIT
 * Worker-only logger. Never dereferences native nodes or takes the PAF lock.
 * A fixed buffer, bounded ordinary snapshots and one write per entry avoid
 * per-field I/O; no file is touched while Sony's USB storage driver is started.
 */
#include <pspkernel.h>
#include <pspiofilemgr.h>
#include <pspusb.h>
#include "diagnostics.h"

#define LOG_LIMIT 128u
typedef struct { char data[2048]; unsigned length; } LogBuffer;
static Status current, last_written;
static unsigned entries;

static int log_word(LogBuffer *buffer, const char *key, unsigned value)
{
    if (buffer->length > sizeof(buffer->data) - 80) return 0;
    char *line = buffer->data + buffer->length; unsigned length = 0;
    while (*key && length < 60) line[length++] = *key++;
    line[length++] = '=';
    for (int shift = 28; shift >= 0; shift -= 4)
        line[length++] = "0123456789abcdef"[(value >> shift) & 15];
    line[length++] = '\n'; buffer->length += length;
    return 1;
}

static int log_status(const Status *s, unsigned entry)
{
    if (sceUsbGetDrvState("USBStor_Driver") == 1) return 0;
    LogBuffer buffer = {.length = 0};
    int success = log_word(&buffer, "build_id", BUILD_ID);
#define LOG(field) success &= log_word(&buffer, #field, s->field)
    success &= log_word(&buffer, "entry", entry);
    success &= log_word(&buffer, "time_us", sceKernelGetSystemTimeLow());
    LOG(user_devkit); LOG(model); LOG(key_config); LOG(ark_major); LOG(ark_minor); LOG(ark_micro);
    LOG(paf_query); LOG(vsh_query); LOG(paf_base); LOG(vsh_base); LOG(paf_size); LOG(vsh_size); LOG(discovery_checks);
    LOG(installed); LOG(node); LOG(ticks); LOG(creates); LOG(layouts);
    LOG(desired); LOG(displayed); LOG(exists); LOG(charging); LOG(ac); LOG(outcome);
    LOG(width_bits); LOG(box_bits); LOG(shift_bits); LOG(rollback); LOG(callback_gaps);
    LOG(native_layout_calls); LOG(clock_resyncs); LOG(clock_x_bits);
    LOG(install_us); LOG(update_us);
    LOG(raw_percent); LOG(native_visible); LOG(text_visible); LOG(cached_restores);
    LOG(icon_changed_us); LOG(hide_us); LOG(show_us); LOG(valid_since_us);
    LOG(fault_stage); LOG(fault_code); LOG(fault_us); LOG(fault_native_visible);
    LOG(fault_battery_x); LOG(fault_shadow_x); LOG(fault_clock_x);
    LOG(fault_expected_battery_x); LOG(fault_expected_shadow_x); LOG(fault_expected_clock_x);
    LOG(usb_driver); LOG(worker_lock_error); LOG(usb_pauses);
    success &= log_word(&buffer, "log_limit", LOG_LIMIT);
#undef LOG
    if (!success || sceUsbGetDrvState("USBStor_Driver") == 1) return 0;
    int flags = PSP_O_WRONLY | PSP_O_CREAT | (entry ? PSP_O_APPEND : PSP_O_TRUNC);
    int fd = sceIoOpen("ms0:/SEPLUGINS/battery-level.log", flags, 0777);
    if (fd < 0) return 0;
    success = sceIoWrite(fd, buffer.data, buffer.length) == (int)buffer.length;
    success &= sceIoClose(fd) >= 0;
    return success;
}

static int changed(const Status *a, const Status *b)
{
    return a->desired != b->desired || a->displayed != b->displayed
        || a->exists != b->exists || a->charging != b->charging || a->ac != b->ac
        || a->outcome != b->outcome || a->installed != b->installed
        || a->layouts != b->layouts || a->callback_gaps != b->callback_gaps
        || a->clock_resyncs != b->clock_resyncs || a->raw_percent != b->raw_percent
        || a->native_visible != b->native_visible || a->text_visible != b->text_visible
        || a->cached_restores != b->cached_restores || a->usb_driver != b->usb_driver
        || a->usb_pauses != b->usb_pauses;
}

void diagnostics_begin(const Status *s) { entries = 0; current = *s; }
void diagnostics_capture(const Status *s) { current = *s; }

void diagnostics_poll(void)
{
    if ((!entries || changed(&current, &last_written)) && entries < LOG_LIMIT
        && log_status(&current, entries)) {
        ++entries; last_written = current;
    }
}

void diagnostics_terminal(void)
{
    /* Reserve a terminal entry beyond the ordinary cap. A failure under USB
     * must remain recoverable after leaving USB; stop cancels the retry loop.
     */
    while (!stop_requested && !log_status(&current, entries))
        sceKernelDelayThread(1000000);
}

void diagnostics_lock_failed(int error)
{
    /* current is the latest synchronized copy, not possibly stale native data. */
    current.worker_lock_error = error;
    current.usb_driver = sceUsbGetDrvState("USBStor_Driver");
    diagnostics_terminal();
}

void diagnostics_failure(const Status *s) { log_status(s, 0); }
