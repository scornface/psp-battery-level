#ifndef BATTERY_RECOVERY_POLICY_H
#define BATTERY_RECOVERY_POLICY_H
enum RecoveryAction { RECOVERY_HIDE, RECOVERY_WAIT, RECOVERY_KEEP, RECOVERY_RESTORE };
/* A cached front remains the previous sample while a changed value is prepared,
 * exactly as in normal double-buffered updates. Never show it during API failure
 * or independently of Sony's battery visibility.
 */
static enum RecoveryAction recovery_action(int desired, int native_visible,
                                           int have_front, int text_visible)
{
    if (desired < 0 || desired > 100 || !native_visible) return RECOVERY_HIDE;
    if (text_visible) return RECOVERY_KEEP;
    return have_front ? RECOVERY_RESTORE : RECOVERY_WAIT;
}
#endif
