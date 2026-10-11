#include <assert.h>
#include "../src/recovery_policy.h"

int main(void)
{
    /* Replay the DC episode: 86% -> API failure -> icon still hidden ->
     * icon back. The first valid visible state restores the prepared front;
     * there is no additional warmup state/timer in the recovery decision.
     */
    assert(recovery_action(86, 1, 1, 1) == RECOVERY_KEEP);
    assert(recovery_action(-1, 1, 1, 1) == RECOVERY_HIDE);
    assert(recovery_action(-1, 0, 1, 0) == RECOVERY_HIDE);
    assert(recovery_action(86, 0, 1, 0) == RECOVERY_HIDE);
    assert(recovery_action(86, 1, 1, 0) == RECOVERY_RESTORE);
    /* The second episode returns 87%: restore the previous front while the
     * changed value follows the usual double-buffered update path.
     */
    assert(recovery_action(87, 1, 1, 0) == RECOVERY_RESTORE);
    assert(recovery_action(87, 1, 1, 1) == RECOVERY_KEEP);
    /* Startup cannot restore an unprepared front. Error/overflow values must
     * not be rendered as percentages; 0% and 100% are genuine valid samples.
     */
    assert(recovery_action(86, 1, 0, 0) == RECOVERY_WAIT);
    assert(recovery_action(-2144665344, 1, 1, 0) == RECOVERY_HIDE);
    assert(recovery_action(101, 1, 1, 0) == RECOVERY_HIDE);
    assert(recovery_action(0, 1, 1, 0) == RECOVERY_RESTORE);
    assert(recovery_action(100, 1, 1, 0) == RECOVERY_RESTORE);
    return 0;
}
