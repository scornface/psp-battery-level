#include <assert.h>
#include "layout_policy.h"
#include "recovery_policy.h"
#include "update_policy.h"

static void test_clock_reset(void)
{
    /* Hardware regression: 100% => shift 54, clock 149; Sony resets it to 203.
     * Repeated date/layout refreshes must restore 149, not accumulate shifts.
     */
    float reference = 203, expected_x = 149;
    for (unsigned i = 0; i < 3; ++i) {
        assert(clock_reset(203, expected_x, 1, &reference) == 1);
        expected_x = reference - 54;
        assert(expected_x == 149);
        assert(clock_reset(149, expected_x, 1, &reference) == 0);
    }
    /* New native box after a percentage change: offset 43 instead of 54. */
    expected_x = reference - 43;
    assert(expected_x == 160);
    assert(clock_reset(203, expected_x, 1, &reference) == 1);
    assert(reference - 43 == 160);
    /* Preserve the other Sony reference when battery is absent. */
    assert(clock_reset(235, expected_x, 0, &reference) == 1);
    assert(reference == 235);
    /* An unrelated layout owner must not be overwritten. */
    assert(clock_reset(204, expected_x, 1, &reference) == -31);
    assert(clock_reset(235, expected_x, 1, &reference) == -31);
    assert(reference == 235);
}

static void test_cached_recovery(void)
{
    assert(recovery_action(86, 1, 1, 1) == RECOVERY_KEEP);
    assert(recovery_action(-1, 1, 1, 1) == RECOVERY_HIDE);
    assert(recovery_action(-1, 0, 1, 0) == RECOVERY_HIDE);
    assert(recovery_action(86, 0, 1, 0) == RECOVERY_HIDE);
    assert(recovery_action(86, 1, 1, 0) == RECOVERY_RESTORE);
    assert(recovery_action(87, 1, 1, 0) == RECOVERY_RESTORE);
    assert(recovery_action(87, 1, 1, 1) == RECOVERY_KEEP);
    assert(recovery_action(86, 1, 0, 0) == RECOVERY_WAIT);
    assert(recovery_action(-2144665344, 1, 1, 0) == RECOVERY_HIDE);
    assert(recovery_action(101, 1, 1, 0) == RECOVERY_HIDE);
    assert(recovery_action(0, 1, 1, 0) == RECOVERY_RESTORE);
    assert(recovery_action(100, 1, 1, 0) == RECOVERY_RESTORE);
}

static void test_usb_wait_budget(void)
{
    unsigned ticks = 0;
    for (unsigned i = 0; i < 9; ++i) assert(!update_wait_expired(0, 0, &ticks));
    /* USB pause resets the nearly exhausted wait budget. */
    for (unsigned i = 0; i < 120; ++i) {
        assert(!update_wait_expired(1, 0, &ticks));
        assert(ticks == 0);
    }
    assert(!update_wait_expired(0, 0, &ticks));
    assert(!update_wait_expired(0, 1, &ticks));
    assert(ticks == 0);
    assert(!update_wait_expired(0, 2, &ticks));
    for (unsigned i = 0; i < 9; ++i) assert(!update_wait_expired(0, 0, &ticks));
    assert(update_wait_expired(0, 0, &ticks));
}

int main(void)
{
    test_clock_reset();
    test_cached_recovery();
    test_usb_wait_budget();
    return 0;
}
