/* SPDX-License-Identifier: MIT */
#ifndef HOME_BACKEND_H
#define HOME_BACKEND_H
typedef struct {
    unsigned published, fault, fault_site, drawn, restores, captures;
    unsigned retired, conflicts, presented, suspended, percent, width;
} HomeStatus;
/* Bootstrap's single kernel worker owns preparation, discovery and polling.
 * poll is diagnostic-only, invoked on the worker outside exclusion. A zero
 * return does not authorize unload: hook publication is the lifetime boundary. */
int home_run(volatile int *stop, void (*poll)(void));
/* Copies callback-owned counters under exclusion; no live native pointers escape. */
HomeStatus home_status(void);
/* Requires interrupt exclusion shared with hook publication. Once published,
 * no live unload is supported; refuse without stopping the active renderer. */
int home_can_unload(void);
#endif
