#ifndef BATTERY_UPDATE_POLICY_H
#define BATTERY_UPDATE_POLICY_H
/* Hidden USB frames cannot consume the native metric readiness budget.
 * After USB, grant the pending back a fresh active-frame budget.
 */
static int update_wait_expired(int usb_started, int ready, unsigned *ticks)
{
    if (usb_started || ready) { *ticks = 0; return 0; }
    return ++*ticks >= 10;
}
#endif
