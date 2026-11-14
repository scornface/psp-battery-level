/* SPDX-License-Identifier: MIT - context selection, never module-name fallback. */
#ifndef BATTERY_CONTEXT_H
#define BATTERY_CONTEXT_H
enum { BATTERY_UNSUPPORTED, BATTERY_VSH, BATTERY_GAME };
/* Key configuration selects the backend, not the presence of module names.
 * POPS/unknown keys fail closed even when version/model checks match. Backend
 * discovery must still authenticate its own native signatures and geometry. */
static inline unsigned battery_context(unsigned devkit, unsigned model, unsigned key,
                                        unsigned major, unsigned minor, unsigned micro)
{
    if (devkit != 0x06060010u || model != 1 || major != 4 || minor != 20 || micro != 69)
        return BATTERY_UNSUPPORTED;
    return key == 0x100 ? BATTERY_VSH : key == 0x200 ? BATTERY_GAME : BATTERY_UNSUPPORTED;
}
#endif
