/* SPDX-License-Identifier: MIT
 * Per-invocation refresh grants. Caller excludes CPU interrupts for all access.
 */
#ifndef HOME_REFRESH_POLICY_H
#define HOME_REFRESH_POLICY_H

typedef struct {
    unsigned busy, serial;
} HomeRefreshState;

/* Zero means no grant, including a nested call. Serial wrap skips zero so a
 * rejected invocation cannot finish or steal the outer invocation's grant. */
static inline unsigned home_refresh_begin(HomeRefreshState *state)
{
    if (state->busy)
        return 0;
    unsigned token = ++state->serial;
    if (!token)
        token = ++state->serial;
    state->busy = token;
    return token;
}

static inline int home_refresh_finish(HomeRefreshState *state, unsigned token)
{
    if (!token)
        return 0;
    if (state->busy != token)
        return -1;
    state->busy = 0;
    return 1;
}
#endif
