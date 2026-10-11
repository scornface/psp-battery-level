/* SPDX-License-Identifier: MIT
 * Internal worker/controller contract. This is not a public plugin API. */
#ifndef BATTERY_XMB_H
#define BATTERY_XMB_H

#ifndef BATTERY_DIAGNOSTICS
#define BATTERY_DIAGNOSTICS 0
#endif
#if BATTERY_DIAGNOSTICS
#define DIAG(...) do { __VA_ARGS__; } while (0)
#define BUILD_ID_TOKEN 0001000b
#else
#define DIAG(...) do { } while (0)
#define BUILD_ID_TOKEN 0001000a
#endif
#define BUILD_NUMBER_(token) 0x##token##u
#define BUILD_NUMBER(token) BUILD_NUMBER_(token)
#define BUILD_STRING_(token) #token
#define BUILD_STRING(token) BUILD_STRING_(token)
#define BUILD_ID BUILD_NUMBER(BUILD_ID_TOKEN)
#define BUILD_ID_TEXT BUILD_STRING(BUILD_ID_TOKEN)

/* Operational fields survive in release: cached metrics are required for
 * restoring the front Text without setting its string again. The rest of the
 * snapshot exists only in diagnostic builds, not just in a disabled logger.
 * Once hooks are installed all access requires xmb_lock(), or Sony's callback
 * context already holding that same lock. Copy before doing filesystem I/O.
 */
typedef struct {
    unsigned installed, native_visible, width_bits, box_bits, shift_bits;
    int desired, outcome;
#if BATTERY_DIAGNOSTICS
    int displayed;
    unsigned user_devkit, model, key_config, ark_major, ark_minor, ark_micro;
    unsigned paf_base, vsh_base, node, ticks, creates, layouts;
    unsigned paf_size, vsh_size, discovery_checks;
    unsigned native_layout_calls, clock_resyncs, clock_x_bits;
    unsigned install_us, update_us, text_visible, cached_restores;
    unsigned icon_changed_us, hide_us, show_us, valid_since_us;
    unsigned fault_stage, fault_us, fault_native_visible;
    unsigned fault_battery_x, fault_shadow_x, fault_clock_x;
    unsigned fault_expected_battery_x, fault_expected_shadow_x, fault_expected_clock_x;
    int fault_code, usb_driver, worker_lock_error, raw_percent;
    int paf_query, vsh_query;
    unsigned usb_pauses, rollback, callback_gaps;
    int exists, charging, ac;
#endif
} Status;

extern Status status;
/* Stop is an asynchronous request. Only the callback may remove native nodes;
 * successful unload requires both the worker and the controller to be done.
 */
extern volatile int stop_requested;
int xmb_lock(void);
void xmb_unlock(void);
int xmb_ready(void);
int xmb_install(void);
int xmb_can_unload(void);
/* May be called without PAF ownership; only requests stop. Shared Status is
 * updated later by a verified callback. The latest deferred error is retained.
 */
void xmb_request_failure(int code);
#endif
