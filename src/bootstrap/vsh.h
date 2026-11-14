/* SPDX-License-Identifier: MIT */
#ifndef BATTERY_VSH_PAYLOAD_H
#define BATTERY_VSH_PAYLOAD_H
/* Single bootstrap worker owns load/start. Stop only after that worker has
 * joined. Refusal retains the child UID and parent, never frees live hooks.
 * Start failure can still leave an owned child; stop must handle that case.
 * This manages src/vsh's user module, not its rendering state or PAF lock. */
int battery_vsh_start(void);
int battery_vsh_stop(void);
#endif
