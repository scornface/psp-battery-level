/* SPDX-License-Identifier: MIT
 * Native XMB controller for the verified Sony 6.61 standard resource.
 * Owns hooks, geometry and both Text nodes. Once installed, its state is shared
 * with the worker only under the PAF lock. Constructors, setters, reflow and
 * destruction run exclusively in Sony's clock callbacks, never the worker.
 */
#ifdef BATTERY_HOST_TEST
#include "runtime_host.h"
#else
#include <pspkernel.h>
#include <pspthreadman.h>
#include <pspusb.h>
#endif
#include "native.h"
#include "xmb.h"
#include "layout_policy.h"
#include "recovery_policy.h"
#include "update_policy.h"

typedef void (*Callback)(void *, void *, unsigned, void *);
typedef void (*LayoutCallback)(void *, void *, void *);
static void callback(void *, void *, unsigned, void *);
static void layout_callback(void *, void *, void *);
static int recover_cached(void);
static int hide_text(void);
static int context(void);
static Callback original;
static LayoutCallback original_layout;
/* baseline is Sony's unshifted geometry; expected is the last geometry we
 * committed. Never subtract from a live position: Sony may reset clock X on
 * size/date changes, and repeatedly subtracting would accumulate drift.
 * new_node is the reusable back; shown_node is the immutable cached front.
 */
static U clock_node, parent, new_node, shown_node, event_slot, bar_nodes[3];
static float baseline[3][4], expected[3][4];
static unsigned totals[2], stable, previous_width, previous_box, pending_ticks;
static int pending_percent = -1;
static int shown_percent = -1;
static int visible;
static int updating;
#if BATTERY_DIAGNOSTICS
static int updates_suspended;
static unsigned update_started, last_callback;
#endif
static int unsafe_node;
static int reflowing;
static int teardown_failed;
static U retired_nodes[2];
static volatile int requested_fault;
static U auxiliary_nodes[4];
Status status = {
    .desired = -1,
#if BATTERY_DIAGNOSTICS
    .raw_percent = -1, .displayed = -1,
#endif
};

/* This Plane flag controls DC recovery, but does NOT describe whether the
 * containing page is on screen. USB requires its own explicit lifecycle gate.
 */
static void track_visibility(void)
{
    unsigned value = !!byte(bar_nodes[0] + 0x1fd);
    DIAG(if (value != status.native_visible) status.icon_changed_us = sceKernelGetSystemTimeLow());
    status.native_visible = value;
}

/* Latch the first fault before cleanup changes the native geometry.
 * stage: 1=layout callback, 2=clock reconciliation, 3=clock guards,
 * 4=hide/recover, 5=update/metrics, 6=cleanup. No native writes here.
 */
static void fault(int code, unsigned stage)
{
    if (!context()) { xmb_request_failure(code); return; }
    status.outcome = code;
#if BATTERY_DIAGNOSTICS
    if (!status.fault_stage) {
        status.fault_stage = stage; status.fault_code = code;
        status.fault_us = sceKernelGetSystemTimeLow();
        status.fault_native_visible = status.native_visible;
        status.fault_expected_battery_x = fbits(expected[0][0]);
        status.fault_expected_shadow_x = fbits(expected[1][0]);
        status.fault_expected_clock_x = fbits(expected[2][0]);
        if (!context()) return;
        if (user_address(bar_nodes[0], 0x330) && word(bar_nodes[0]) == paf + 0x18b068) {
            status.fault_battery_x = word(bar_nodes[0] + 0x220);
            status.fault_native_visible = !!byte(bar_nodes[0] + 0x1fd);
        }
        if (user_address(bar_nodes[1], 0x330) && word(bar_nodes[1]) == paf + 0x18b068)
            status.fault_shadow_x = word(bar_nodes[1] + 0x220);
        if (user_address(clock_node, 0x340) && text_vtable(clock_node))
            status.fault_clock_x = word(clock_node + 0x220);
    }
#else
    (void)stage;
#endif
}
static SceLwMutexWorkarea *native_lock(void) { return (void *)(paf + 0x190640); }
int xmb_lock(void) { return sceKernelLockLwMutex(native_lock(), 1, 0); }
void xmb_unlock(void) { sceKernelUnlockLwMutex(native_lock(), 1); }
int xmb_ready(void) { return word(paf + 0x190650) && word(vsh + 0x5cab4); }
void xmb_request_failure(int code) { requested_fault = code; }
int xmb_can_unload(void)
{
    /* Try-lock also waits out the last dispatcher indirectly: it cannot succeed
     * while a foreign Sony callback still owns PAF. Never authorize unload from
     * recursively inside that dispatcher, or after an unverifiable teardown.
     */
    if (word(paf + 0x190640) && word(paf + 0x190644) == (unsigned)sceKernelGetThreadId()) return 0;
    if (sceKernelTryLockLwMutex(native_lock(), 1) < 0) return 0;
    int safe = !status.installed && !new_node && !shown_node && !teardown_failed
        && !unsafe_node && !retired_nodes[0] && !retired_nodes[1];
    xmb_unlock();
    return safe;
}
/* A valid address alone is insufficient: the current callback must own PAF's
 * lock and the clock must still belong to the page captured during install.
 */
static int context(void)
{
    return paf && vsh && word(paf + 0x190640) > 0
        && word(paf + 0x190644) == (unsigned)sceKernelGetThreadId()
        && word(vsh + 0x5cab4) == clock_node
        && text_vtable(clock_node) && user_address(parent, 0x560)
        && word(parent) == paf + 0x18b218 && word(clock_node + 0x1d4) == parent;
}
static int owned_text(U node)
{
    if (!text_vtable(node) || word(node + 0x1d4) != parent
        || occurrences(parent, 0x1b4, node) != 1 || occurrences(parent, 0x1d8, node) != 1) return 0;
    U sub = word(node + 0x1e8);
    return user_address(sub, 0x20) && word(sub) == paf + 0x18c118
        && slot(sub, 0x78) == paf + 0x11a5c8 && user_address(word(sub + 0x1c), 0x1c0);
}
static int bar_identity(void)
{
    if (!context() || slot(parent, 0x4c) != paf + 0xec0c8 || slot(parent, 0x50) != paf + 0xec178
        || word(vsh + 0x5caac) != bar_nodes[0] || word(vsh + 0x5cab0) != bar_nodes[1]) return 0;
    for (unsigned i = 0; i < 2; ++i)
        if (!user_address(bar_nodes[i], 0x330) || word(bar_nodes[i]) != paf + 0x18b068
            || word(bar_nodes[i] + 0x1d4) != parent
            || occurrences(parent, 0x1b4, bar_nodes[i]) != 1
            || occurrences(parent, 0x1d8, bar_nodes[i]) != 1) return 0;
    for (unsigned i = 0; i < 4; ++i) {
        U node = auxiliary_nodes[i];
        if (word(vsh + 0x5cab8 + i * 4) != node || !user_address(node, 0x330)
            || word(node) != paf + 0x18b068 || word(node + 0x1d4) != parent
            || occurrences(parent, 0x1b4, node) != 1) return 0;
    }
    return owned_text(clock_node);
}
/* Stop if another component has changed identities, parents or geometry.
 * Restoration must not overwrite someone else's newer layout.
 */
static int bar_owned(void)
{
    if (!bar_identity()) return 0;
    for (unsigned i = 0; i < 3; ++i) {
        if (!user_address(bar_nodes[i], 0x330) || word(bar_nodes[i] + 0x1d4) != parent) return 0;
        for (unsigned j = 0; j < 4; ++j)
            if (word(bar_nodes[i] + 0x220 + j * 4) != fbits(expected[i][j])) return 0;
    }
    return 1;
}
/* Sony stores size/layout notifications in a separate bounded event vector.
 * Accept exactly one active 0x2000c slot; ambiguity is not a safe hook target.
 */
static U layout_event_slot(U function)
{
    U data = word(clock_node + 0x160);
    unsigned count = word(clock_node + 0x164), capacity = word(clock_node + 0x168);
    if (count > capacity || count > 32 || (count && !user_address(data, count * 16))) return 0;
    U found = 0;
    for (unsigned i = 0; i < count; ++i) {
        U item = data + i * 16;
        if (word(item) == 0x2000c && word(item + 4) == (unsigned)function && !byte(item + 12)) {
            if (found) return 0;
            found = item + 4;
        }
    }
    return found;
}
/* Re-resolve the unique live periodic record, rather than trusting a saved
 * address if Sony rebuilds its linked event list under the same clock object.
 */
static U clock_event_slot(U function)
{
    U head = word(clock_node + 0x1a0);
    if (!user_address(head, 8)) return 0;
    U item = word(head + 4), found = 0;
    unsigned visited = 0;
    for (; item && item != head && visited < 32; ++visited, item = word(item + 4)) {
        if (!user_address(item, 0x38)) return 0;
        if (word(item + 8) == 100 && word(item + 0x30) == (unsigned)function) {
            if (found) return 0;
            found = item + 0x30;
        }
    }
    return item == head ? found : 0;
}
static void native_reflow(float clock_x)
{
    /* VSH+31038 consumes f12, positions clock and then measures its native box
     * to place hold/mute through +30f58/+30e84. No manual auxiliary-icon offsets.
     */
    reflowing = 1;
    paf_float_bits(vsh + 0x31038, 0, 0, fbits(clock_x));
    reflowing = 0;
    expected[2][0] = clock_x;
    DIAG(status.clock_x_bits = word(clock_node + 0x220));
}
static int reconcile_clock(void)
{
    /* Only a recognized Sony reset is accepted; other geometry changes fail.
     * Native battery visibility chooses clock reference 203 or 235.
     */
    if (!bar_identity()) return -31;
    for (unsigned i = 0; i < 2; ++i)
        for (unsigned j = 0; j < 4; ++j)
            if (word(bar_nodes[i] + 0x220 + j * 4) != fbits(expected[i][j])) return -31;
    for (unsigned j = 1; j < 4; ++j)
        if (word(clock_node + 0x220 + j * 4) != fbits(expected[2][j])) return -31;
    float native_x;
    int reset = clock_reset(from_bits(word(clock_node + 0x220)), expected[2][0],
                           byte(bar_nodes[0] + 0x1fd), &native_x);
    if (reset <= 0) return reset;
    baseline[2][0] = native_x;
    float shift = shown_node && visible ? from_bits(status.shift_bits) : 0;
    native_reflow(native_x - shift);
    DIAG(++status.clock_resyncs);
    return bar_owned() ? 0 : -31;
}
/* Invoke Sony first so its layout and auxiliary icons retain their behavior.
 * reflowing prevents our own native reflow from recursively reconciling itself.
 */
static void layout_callback(void *n, void *event, void *arg)
{
    original_layout(n, event, arg); /* Preserve native size/layout notifications. */
    if ((U)n != clock_node || !context()) { fault(-20, 1); return; }
    if (requested_fault && !status.outcome) fault(requested_fault, 7);
    DIAG(++status.native_layout_calls);
    if (reflowing || !status.installed || status.outcome || unsafe_node || stop_requested) return;
    if (!layout_event_slot((U)layout_callback)) { fault(-26, 1); return; }
    int result = reconcile_clock();
    if (result < 0) fault(result, 1);
    else {
        track_visibility();
        result = recovery_action(status.desired, status.native_visible, !!shown_node, visible)
            == RECOVERY_HIDE ? hide_text() : recover_cached();
        if (result < 0) fault(result, 4);
    }
}
static int restore_bar(void)
{
    if (!bar_owned()) return -31;
    for (unsigned i = 0; i < 2; ++i) {
        position(bar_nodes[i], baseline[i]);
        for (unsigned j = 0; j < 4; ++j) expected[i][j] = baseline[i][j];
    }
    native_reflow(baseline[2][0]);
    return bar_owned() ? 0 : -32;
}
static int hide_text(void)
{
    if (!visible) return 0;
    if (shown_node) {
        if (!owned_text(shown_node)) { unsafe_node = -34; return -34; }
        visibility(shown_node, 0);
    }
    visible = 0;
    DIAG(status.displayed = -1);
    DIAG(status.text_visible = 0; status.hide_us = sceKernelGetSystemTimeLow());
    /* Keep the front's string/metrics and a pending back untouched. */
    return restore_bar();
}
/* Transactional teardown, in callback context only. Restore geometry before
 * destroying Text, verify native child counts, then restore both event slots.
 * An unsafe/partially constructed node intentionally prevents successful
 * unload: invoking an unverified destructor would be worse than refusing it.
 */
static int cleanup(void)
{
    if (unsafe_node) return unsafe_node;
    if (teardown_failed) return teardown_failed;
    if (!context()) return -26;
    event_slot = clock_event_slot((U)callback);
    if (!event_slot) return -26;
    U layout_slot = layout_event_slot((U)layout_callback);
    if (!layout_slot) return -26;
    if (new_node || shown_node) {
        U nodes[2] = {new_node, shown_node};
        for (unsigned i = 0; i < 2; ++i)
            if (nodes[i] && !owned_text(nodes[i])) { unsafe_node = -34; return -34; }
        if (!bar_owned()) return -31;
        for (unsigned i = 0; i < 2; ++i) if (nodes[i]) visibility(nodes[i], 0);
        int result = restore_bar();
        if (result < 0) return result;
        for (unsigned i = 0; i < 2; ++i) {
            U old = nodes[i];
            if (!old) continue;
            retired_nodes[i] = old;
            destroy_text(old);
            if (old == new_node) new_node = 0;
            if (old == shown_node) shown_node = 0;
            if (occurrences(parent, 0x1b4, old) || occurrences(parent, 0x1d8, old)) {
                teardown_failed = -27; return -27;
            }
            retired_nodes[i] = 0;
        }
        visible = updating = 0; shown_percent = -1;
        DIAG(status.node = 0; status.text_visible = 0);
        if (occurrences(parent, 0x1b4, clock_node) != 1
            || occurrences(parent, 0x1d8, clock_node) != 1
            || word(parent + 0x1b8) != totals[0] || word(parent + 0x1dc) != totals[1]) {
            teardown_failed = -27; return -27;
        }
    }
    layout_slot = layout_event_slot((U)layout_callback);
    event_slot = clock_event_slot((U)callback);
    if (!layout_slot || !event_slot) return -26;
    write_word(event_slot, (unsigned)(U)original);
    sceKernelDcacheWritebackRange((void *)event_slot, 4);
    write_word(layout_slot, (unsigned)(U)original_layout);
    sceKernelDcacheWritebackRange((void *)layout_slot, 4);
    status.installed = 0;
    DIAG(status.displayed = -1; status.rollback = 1);
    return 0;
}
/* Sony's setter receives UTF-16 plus a character count, excluding the NUL.
 * The maximum is four visible characters (100%); no host font/format library.
 */
static int set_percent(int percent)
{
    uint16_t text[5]; unsigned length = 0;
    if (percent < 0 || percent > 100) return -25;
    if (!owned_text(new_node)) { unsafe_node = -34; return -34; }
    if (percent == 100) text[length++] = '1';
    if (percent >= 10) text[length++] = '0' + (percent / 10) % 10;
    text[length++] = '0' + percent % 10;
    text[length++] = '%'; text[length] = 0;
    struct { uint16_t *data; unsigned length; } descriptor = {text, length};
    return ((int (*)(void *, const void *, unsigned))slot(new_node, 0xb4))((void *)new_node, &descriptor, 0);
}
static int create_text(void)
{
    /* Sony constructors still contain unchecked internal allocations. The free
     * memory preflight reduces pressure; it is not a guarantee of recovery.
     */
    if (sceKernelTotalFreeMemSize() < 64 * 1024) return -21;
    U memory = (U)((void *(*)(unsigned))(paf + 0x13a4e0))(0x340);
    if (!memory) return -21;
    ((void (*)(void *, void *, void *))(paf + 0x105aa0))((void *)memory, (void *)parent, 0);
    new_node = memory;
    DIAG(status.node = shown_node ? shown_node : memory; ++status.creates);
    if (!text_vtable(memory)) { unsafe_node = -22; return -22; }
    if (occurrences(parent, 0x1b4, memory) != 1 || occurrences(parent, 0x1d8, memory) != 1
        || word(parent + 0x1b8) != totals[0] + 1 + !!shown_node
         || word(parent + 0x1dc) != totals[1] + 1 + !!shown_node) return -23;
    if (!owned_text(memory)) { unsafe_node = -34; return -34; }
    return style(memory) < 0 ? -24 : 0;
}
/* Native text preparation is asynchronous. Return 0 for an unfinished backend,
 * 1 for measured width/box, negative for an invalid object. Backend fields:
 * +120 box, +130 glyph width, +144 format, +148 readiness, +188 pending work.
 * Fractional glyph width and rounded box must agree within one native unit.
 */
static int metrics(U node, unsigned *width_out, float *box_out)
{
    if (!owned_text(node)) { unsafe_node = -34; return -34; }
    U sub = word(node + 0x1e8);
    if (!user_address(sub, 0x20) || word(sub) != paf + 0x18c118) return -11;
    U backend = word(sub + 0x1c);
    if (!user_address(backend, 0x1c0)) return -11;
    if (word(backend + 0x188) || word(backend + 0x148) != 1
        || (word(backend + 0x144) & 0xffff) != 2) return 0;
    unsigned width = word(backend + 0x130);
    float box = from_bits(word(backend + 0x120));
    if (word(backend + 0x188) || word(backend + 0x148) != 1
        || (word(backend + 0x144) & 0xffff) != 2
        || word(backend + 0x130) != width || word(backend + 0x120) != fbits(box)
        || !(from_bits(width) > 0 && from_bits(width) < 100)
         || !(box >= from_bits(width) && box < from_bits(width) + 1)) return 0;
    *width_out = width; *box_out = box;
    return 1;
}
static int place_text(U node, unsigned width, float box)
{
    if (!owned_text(node)) { unsafe_node = -34; return -34; }
    if (!bar_owned()) return -31;
    /* Verified standard resource geometry: native gap 7, right anchor 236. */
    float shift = box + 7;
    for (unsigned i = 0; i < 2; ++i) {
        expected[i][0] = baseline[i][0] - shift;
        position(bar_nodes[i], expected[i]);
    }
    native_reflow(baseline[2][0] - shift);
    if (!bar_owned()) return -31;
    float pos[4] = {236, baseline[2][1], baseline[2][2], 1};
    position(node, pos);
    status.width_bits = width; status.box_bits = fbits(box); status.shift_bits = fbits(shift);
    DIAG(++status.layouts);
    return 1;
}
static int recover_cached(void)
{
    if (recovery_action(status.desired, status.native_visible,
                        shown_node && shown_percent >= 0, visible) != RECOVERY_RESTORE) return 0;
    unsigned width; float box;
    int result = metrics(shown_node, &width, &box);
    if (result <= 0) return result;
    /* The front is immutable: reuse only the exact previously committed box.
     * A changed desired value uses normal double buffering after restoration.
     */
    if (width != status.width_bits || fbits(box) != status.box_bits) return 0;
    result = place_text(shown_node, width, box);
    if (result < 0) return result;
    visibility(shown_node, 1); visible = 1;
    DIAG(status.displayed = shown_percent);
    DIAG(status.text_visible = 1; status.show_us = sceKernelGetSystemTimeLow(); ++status.cached_restores);
    return 1;
}
/* Commit only after two matching width/box samples. Return 2 for a ready back
 * waiting on Sony's icon: update_policy treats that as ready, not a timeout.
 */
static int layout(void)
{
    unsigned width; float box;
    int result = metrics(new_node, &width, &box);
    if (result <= 0) { stable = 0; return result; }
    stable = width == previous_width && fbits(box) == previous_box ? stable + 1 : 1;
    previous_width = width; previous_box = fbits(box);
    if (stable < 2) return 0;
    /* A ready back may wait for Sony's icon without timing out or becoming an
     * orphan percentage. No writes to the battery Plane's visibility/animation.
     */
    if (!status.native_visible) return 2;
    result = place_text(new_node, width, box);
    if (result < 0) return result;
    /* Both nodes use Sony Text/metrics/style. The existing value stays visible
     * throughout asynchronous preparation. Swap under the same native lock as
     * the bar reflow, so the renderer never sees an intentionally empty frame.
     */
    if (shown_node && !owned_text(shown_node)) { unsafe_node = -34; return -34; }
    visibility(new_node, 1);
    if (shown_node) visibility(shown_node, 0);
    U previous = shown_node; shown_node = new_node; new_node = previous;
    visible = 1; updating = 0; shown_percent = pending_percent;
    DIAG(status.node = shown_node; status.text_visible = 1;
         status.show_us = sceKernelGetSystemTimeLow();
         status.update_us = sceKernelGetSystemTimeLow() - update_started);
    DIAG(status.displayed = pending_percent);
    return 1;
}
/* Verified clock update event (100): guard -> reconcile -> USB pause -> cached
 * recovery -> prepare back -> measure -> atomic swap. Sony's original date/time
 * handler is always called, even when our own work is stopped or faulted.
 */
static void callback(void *n, void *event, unsigned id, void *arg)
{
    original(n, event, id, arg); /* Always preserve the native date/time path. */
    if ((U)n != clock_node || id != 100 || !context()) { fault(-20, 3); return; }
    event_slot = clock_event_slot((U)callback);
    if (!event_slot) { fault(-26, 3); return; }
    if (!layout_event_slot((U)layout_callback)) { fault(-26, 3); return; }
    if (unsafe_node) return;
    if (requested_fault && !status.outcome) fault(requested_fault, 7);
    int reconciliation = reconcile_clock();
    if (reconciliation < 0) { fault(reconciliation, 2); return; }
    DIAG(unsigned now = sceKernelGetSystemTimeLow();
         if (last_callback && now - last_callback > 5000000) ++status.callback_gaps;
         last_callback = now; ++status.ticks);
    track_visibility();
    if (unsafe_node) return;
    if (new_node && !owned_text(new_node)) {
        unsafe_node = -34; fault(-34, 3); return;
    }
    if (shown_node && !owned_text(shown_node)) {
        unsafe_node = -34; fault(-34, 3); return;
    }
    if (stop_requested || status.outcome) {
        int result = cleanup();
        if (result < 0) fault(result, 6);
        return;
    }
    if (!bar_owned()) { fault(-31, 3); return; }
    /* USB hides the native indicator page and may suspend metric processing.
     * Query here rather than rely on the worker's 1 Hz sample: even an update
     * already at tick 9 must not time out when USB starts between samples.
     * Only a state query; no USB lifecycle operation, I/O or wait in callback.
     * Parent visibility remains entirely Sony-owned; retain both Text nodes.
     */
    if (sceUsbGetDrvState("USBStor_Driver") == 1) {
        DIAG(if (!updates_suspended) ++status.usb_pauses);
        DIAG(updates_suspended = 1);
        stable = previous_width = previous_box = 0;
        update_wait_expired(1, 0, &pending_ticks);
        return;
    }
    DIAG(updates_suspended = 0);
    int result;
    if (recovery_action(status.desired, status.native_visible, !!shown_node, visible) == RECOVERY_HIDE) {
        result = hide_text();
        if (result < 0) { fault(result, 4); return; }
        if (status.desired < 0) return;
    } else {
        result = recover_cached();
        if (result < 0) { fault(result, 4); return; }
    }
    /* Re-showing the same front requires no setter and no metric warmup. */
    if (shown_node && status.desired == shown_percent && visible) {
        updating = 0; pending_percent = shown_percent;
        return;
    }
    /* If the committed backend no longer has its cached metrics, use the normal
     * guarded preparation path rather than leave an invisible front forever.
     */
    if (!visible && status.native_visible && !updating) pending_percent = -1;
    if (status.desired != pending_percent && !new_node && (result = create_text()) < 0) {
        fault(result, 5);
        /* Unexpected vtable may mean partial construction; never destroy it. */
        if (result != -22) {
            result = cleanup();
            if (result < 0) fault(result, 6);
        }
        return;
    }
    if (status.desired != pending_percent) {
        visibility(new_node, 0); stable = previous_width = previous_box = pending_ticks = 0;
        if (set_percent(status.desired) < 0) { fault(-25, 5); return; }
        pending_percent = status.desired;
        updating = 1;
        DIAG(update_started = sceKernelGetSystemTimeLow());
        return; /* Allow the native worker to process the new string. */
    }
    if (updating) {
        result = layout();
        if (result < 0) fault(result, 5);
        else if (update_wait_expired(0, result, &pending_ticks)) fault(-33, 5);
    }
}
/* Read-only until every address, topology, standard geometry and event guard
 * passes. Publish hooks only while holding PAF's lock. Construction is deferred
 * to the clock callback; installing the plugin never creates a foreign widget.
 */
int xmb_install(void)
{
    clock_node = word(vsh + 0x5cab4);
    if (!user_address(clock_node, 0x340) || !text_vtable(clock_node)) return -4;
    U sub = word(clock_node + 0x1e8);
    if (!user_address(sub, 0x20) || word(sub) != paf + 0x18c118
        || slot(sub, 0x78) != paf + 0x11a5c8 || !user_address(word(sub + 0x1c), 0x1c0)) return -11;
    parent = word(clock_node + 0x1d4);
    if (!user_address(parent, 0x560) || word(parent) != paf + 0x18b218
        || slot(parent, 0x4c) != paf + 0xec0c8 || slot(parent, 0x50) != paf + 0xec178) return -5;
    if (word(parent + 0x200) || word(parent + 0x204)) return -30;
    for (unsigned j = 0; j < 16; ++j)
        if (word(parent + 0x2a0 + j * 4) != fbits(j % 5 == 0 ? 1 : 0)) return -30;
    bar_nodes[0] = word(vsh + 0x5caac); bar_nodes[1] = word(vsh + 0x5cab0); bar_nodes[2] = clock_node;
    static const float x[3] = {223, 225, 203}, y[3] = {124, 122, 123};
    for (unsigned i = 0; i < 3; ++i) {
        U node = bar_nodes[i];
        if (!user_address(node, 0x330) || (i < 2 && word(node) != paf + 0x18b068)
            || word(node + 0x1d4) != parent || word(node + 0x200) || word(node + 0x204)
            || occurrences(parent, 0x1b4, node) != 1 || occurrences(parent, 0x1d8, node) != 1) return -30;
        for (unsigned j = 0; j < 3; ++j)
            if (word(node + 0x230 + j * 4) != fbits(1)) return -30;
        for (unsigned j = 0; j < 4; ++j) expected[i][j] = baseline[i][j] = from_bits(word(node + 0x220 + j * 4));
        if (fbits(baseline[i][0]) != fbits(x[i]) || fbits(baseline[i][1]) != fbits(y[i])
            || fbits(baseline[i][2]) != fbits(0) || fbits(baseline[i][3]) != fbits(1)) return -30;
        if (i < 2 && (word(node + 0x320) != fbits(44) || word(node + 0x324) != fbits(16))) return -30;
    }
    for (unsigned i = 0; i < 4; ++i) {
        U node = word(vsh + 0x5cab8 + i * 4);
        if (!user_address(node, 0x330) || word(node) != paf + 0x18b068
            || word(node + 0x1d4) != parent || occurrences(parent, 0x1b4, node) != 1) return -30;
        auxiliary_nodes[i] = node;
    }
    if (!bar_owned()) return -30;
    totals[0] = word(parent + 0x1b8); totals[1] = word(parent + 0x1dc);
    event_slot = clock_event_slot(vsh + 0x30ba8);
    if (!event_slot) return -8;
    U layout_slot = layout_event_slot(vsh + 0x3113c);
    if (!layout_slot) return -9;
    original_layout = (LayoutCallback)(U)word(layout_slot);
    original = (Callback)(U)word(event_slot);
    status.installed = 1;
    track_visibility();
    write_word(event_slot, (unsigned)(U)callback);
    sceKernelDcacheWritebackRange((void *)event_slot, 4);
    write_word(layout_slot, (unsigned)(U)layout_callback);
    sceKernelDcacheWritebackRange((void *)layout_slot, 4);
    return 0;
}
