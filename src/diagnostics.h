/* SPDX-License-Identifier: MIT
 * Diagnostic snapshots are copied under PAF's lock, emitted outside it.
 * Release builds inline these calls away and do not link diagnostics.c.
 */
#ifndef BATTERY_DIAGNOSTICS_H
#define BATTERY_DIAGNOSTICS_H
#include "xmb.h"
#if BATTERY_DIAGNOSTICS
void diagnostics_begin(const Status *s);
void diagnostics_capture(const Status *s);
void diagnostics_poll(void);
void diagnostics_terminal(void);
void diagnostics_lock_failed(int error);
void diagnostics_failure(const Status *s);
#else
static inline void diagnostics_begin(const Status *s) { (void)s; }
static inline void diagnostics_capture(const Status *s) { (void)s; }
static inline void diagnostics_poll(void) {}
static inline void diagnostics_terminal(void) {}
static inline void diagnostics_lock_failed(int error) { (void)error; }
static inline void diagnostics_failure(const Status *s) { (void)s; }
#endif
#endif
