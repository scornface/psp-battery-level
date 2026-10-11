#include <assert.h>
#include "../src/layout_policy.h"

int main(void)
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
    return 0;
}
