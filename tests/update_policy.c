#include <assert.h>
#include "../src/update_policy.h"

int main(void)
{
    unsigned ticks = 0;
    /* Update nearly exhausted its budget when the XMB enters USB. A long
     * hidden interval must not trigger the cleanup seen on hardware (-33).
     */
    for (unsigned i = 0; i < 9; ++i)
        assert(!update_wait_expired(0, 0, &ticks));
    for (unsigned i = 0; i < 120; ++i) {
        assert(!update_wait_expired(1, 0, &ticks));
        assert(ticks == 0);
    }
    /* Resume can warm up and complete without inheriting pre-USB failures. */
    assert(!update_wait_expired(0, 0, &ticks));
    assert(!update_wait_expired(0, 1, &ticks));
    assert(ticks == 0);
    /* A ready back waiting for Sony's icon also does not count as stalled. */
    assert(!update_wait_expired(0, 2, &ticks));
    /* A genuinely stalled active renderer still has the original bound. */
    for (unsigned i = 0; i < 9; ++i)
        assert(!update_wait_expired(0, 0, &ticks));
    assert(update_wait_expired(0, 0, &ticks));
    return 0;
}
