#ifndef BATTERY_LAYOUT_POLICY_H
#define BATTERY_LAYOUT_POLICY_H
/* A Sony reflow writes one of these two clock references. Accept that reset,
 * never arbitrary coordinates, and never subtract an offset twice.
 */
static int clock_reset(float actual, float expected_x, int battery_visible, float *reference)
{
    if (actual == expected_x) return 0;
    float native_x = battery_visible ? 203 : 235;
    if (actual != native_x) return -31;
    *reference = native_x;
    return 1;
}
#endif
