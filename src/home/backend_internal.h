/* SPDX-License-Identifier: MIT - kernel-only native binding, not shared with VSH. */
#ifndef HOME_BACKEND_INTERNAL_H
#define HOME_BACKEND_INTERNAL_H
#include "assets.h"
#include "bar_session.h"
#include "refresh_policy.h"
#include "power_worker.h"
/* backend.c owns storage and initializes assets/binding before publication.
 * Afterwards assets/binding are immutable, power has one worker publisher,
 * and bar/refresh/fault belong to callbacks under interrupt exclusion.
 * Worker diagnostics may only copy callback state through home_status(). */
extern HomeAssets home_assets;
extern HomePowerFrames home_power;
extern HomeBarSession home_bar;
extern HomeRefreshState home_refresh;
extern HomeBinding home_binding;
extern unsigned home_base, home_state, home_original, home_published;
extern volatile unsigned home_fault;
void home_callback(void);
/* Assembly-only ABI: caller is Sony's return address, not a node pointer.
 * The stack-local token pairs one before/after call across the original hook. */
unsigned home_before(unsigned caller);
void home_after(unsigned caller, unsigned token);
#endif
