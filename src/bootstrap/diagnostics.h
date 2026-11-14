/* SPDX-License-Identifier: MIT - outer lifecycle, not PAF/HOME state sharing. */
#ifndef BATTERY_BOOT_DIAGNOSTICS_H
#define BATTERY_BOOT_DIAGNOSTICS_H
#if BATTERY_DIAGNOSTICS
void battery_boot_log(unsigned context, int outcome, int terminal);
#else
#define battery_boot_log(context, outcome, terminal) ((void)0)
#endif
#endif
