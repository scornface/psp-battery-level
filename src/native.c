/* SPDX-License-Identifier: MIT
 * Module discovery and native PAF calls for the single verified firmware.
 * Sony code/resources are read from runtime modules, not bundled in the PRX.
 */
#include "native.h"
U paf, vsh;

/* KUBridge copies the 0xa0-byte ARK/M33 SceModule2 ABI into user memory.
 * No kernel pointer returned in this descriptor is dereferenced by this PRX.
 */
typedef struct { unsigned words[40]; } ModuleDescriptor;
extern int kuKernelFindModuleByName(char *name, ModuleDescriptor *out);

int user_address(U p, unsigned size)
{
    return size <= 0x03800000 && p >= 0x08800000 && p <= 0x0c000000 - size && !(p & 3);
}

static int named(const ModuleDescriptor *m, const char *name)
{
    const char *actual = (const char *)m + 8;
    unsigned i = 0;
    while (i < 27 && name[i] && actual[i] == name[i]) ++i;
    return i < 27 && !name[i] && !actual[i];
}

/* Validate complete ranges without overflowing an address + size expression. */
static int mapped(const ModuleDescriptor *m, unsigned address, unsigned bytes)
{
    unsigned count = m->words[0x7c / 4];
    if (!count || count > 4) return 0;
    for (unsigned i = 0; i < count; ++i) {
        unsigned base = m->words[0x80 / 4 + i], size = m->words[0x90 / 4 + i];
        if (user_address(base, size) && address >= base && bytes <= size
            && address - base <= size - bytes) return 1;
    }
    return 0;
}

int native_discover(NativeDiscovery *info)
{
    ModuleDescriptor p = {{0}}, v = {{0}};
    int pq = kuKernelFindModuleByName("scePaf_Module", &p);
    int vq = kuKernelFindModuleByName("vsh_module", &v);
    if (info) { *info = (NativeDiscovery){0}; info->paf_query = pq; info->vsh_query = vq; }
    if (pq < 0 || vq < 0) return -1;
    unsigned pb = p.words[0x6c / 4], vb = v.words[0x6c / 4];
    unsigned ps = p.words[0x70 / 4], vs = v.words[0x70 / 4];
    unsigned checks = (named(&p, "scePaf_Module") && named(&v, "vsh_module") ? 1 : 0)
        | (ps == 0x18c518 && vs == 0x556c0 ? 2 : 0)
        | (mapped(&p, pb, 0x18c518) ? 4 : 0) | (mapped(&v, vb, 0x556c0) ? 8 : 0)
        | (mapped(&p, pb + 0x190640, 0x14) ? 16 : 0) | (mapped(&v, vb + 0x5cab4, 0x14) ? 32 : 0);
    if (info) {
        info->paf_size = ps; info->vsh_size = vs; info->paf_base = pb;
        info->vsh_base = vb; info->checks = checks;
    }
    if (checks != 63) return -2;
    paf = pb; vsh = vb;
    return 0;
}

/* Vectors are passed by pointer; float scalars use the adapter in abi.S. */
#ifndef BATTERY_HOST_TEST
void position(U n, const float v[4])
{
    ((void (*)(void *, const float *, unsigned))(paf + 0xeccb4))((void *)n, v, 0);
}
void visibility(U n, int visible)
{
    float color[4] = {1, 1, 1, visible ? 1 : 0};
    ((void (*)(void *, const float *, unsigned))slot(n, 0x54))((void *)n, color, 0);
}
static int scalar(U n, unsigned offset, unsigned id, unsigned value)
{
    return ((int (*)(void *, unsigned, unsigned))slot(n, offset))((void *)n, id, value);
}
static int real(U n, unsigned id, float value)
{
    return paf_float_bits(slot(n, 0x74), n, id, fbits(value));
}
static int record(U n, unsigned id, float x, float y, float z, float w)
{
    float v[4] = {x, y, z, w};
    return ((int (*)(void *, unsigned, const void *))slot(n, 0x78))((void *)n, id, v);
}

/* Match Text clock's RCO property sequence, including outline/drop shadow.
 * Numeric property IDs are Sony's observed ABI, not guessed public constants.
 * Construct transparent at the right anchor; measured layout makes it visible.
 */
int style(U n)
{
    float pos[4] = {236, 123, 0, 1}, color[4] = {1, 1, 1, 0};
    float dimensions[4] = {0, 0, 1, 1}, scale[4] = {1, 1, 1, 1};
    typedef void (*Vector)(void *, const float *, unsigned);
    position(n, pos);
    ((Vector)slot(n, 0x54))((void *)n, color, 0);
    ((Vector)slot(n, 0x5c))((void *)n, dimensions, 0);
    ((Vector)(paf + 0xece98))((void *)n, scale, 0);
    int result = scalar(n, 0x70, 0x0e, 2);
    result |= scalar(n, 0x70, 0x0f, ~0u);
    result |= scalar(n, 0x70, 0x25, 2);
    result |= real(n, 0x1c, 7.6f);
    result |= record(n, 0x26, 1, 1, 1, 1);
    result |= record(n, 0x27, 1, 1, 1, 1);
    for (unsigned id = 0x1d; id <= 0x21; ++id) result |= real(n, id, 0);
    result |= scalar(n, 0x6c, 0x22, 0);
    result |= scalar(n, 0x70, 0x23, 0);
    result |= scalar(n, 0x6c, 0x24, 1);
    result |= scalar(n, 0x6c, 0x2d, 1);
    result |= record(n, 0x2e, 2, -2.5f, 0, 1);
    result |= record(n, 0x2f, .45f, .45f, .45f, 1);
    return result;
}
void destroy_text(U n) { ((void (*)(void *))slot(n, 0x0c))((void *)n); }
#endif

/* Membership in both native child vectors is an ownership guard, not a count
 * of our allocations. ~0u deliberately fails callers' expected 0/1 checks.
 */
unsigned occurrences(U parent, unsigned offset, U needle)
{
    if (offset > 0x560 - 12 || !user_address(parent, 0x560)) return ~0u;
    unsigned count = word(parent + offset + 4), capacity = word(parent + offset + 8), found = 0;
    U data = word(parent + offset);
    if (count > capacity || count > 64 || (count && !user_address(data, count * 4))) return ~0u;
    for (unsigned i = 0; i < count; ++i) found += word(data + i * 4) == needle;
    return found;
}

/* Exact instruction guards for constructors, setters, reflow and callbacks. */
int signatures(void)
{
    return word(paf + 0x105aa0) == 0x27bdfff0 && word(paf + 0x105aa4) == 0xafb20008
        && word(paf + 0xe47ac) == 0x27bdfff0 && word(vsh + 0x30ba8) == 0x27bdfee0
        && word(paf + 0xdeabc) == 0x0100f809
        && word(paf + 0x13a4e0) == 0x27bdfff0 && word(paf + 0x13a4e4) == 0xafbf0000
        && word(paf + 0xeccb4) == 0x27bdffe0 && word(paf + 0xeccb8) == 0xafb00010
        && word(paf + 0xece98) == 0x27bdfff0 && word(paf + 0xece9c) == 0xafbf0000
        && word(paf + 0x11a1d0) == 0x27bdfff0
        && word(vsh + 0x31038) == 0x27bdffd0 && word(vsh + 0x3103c) == 0xafb10014
        && word(vsh + 0x3113c) == 0x27bdfff0 && word(vsh + 0x31140) == 0xafbf0000
        && word(paf + 0xde2dc) == 0x0040f809;
}
int text_vtable(U n)
{
    return user_address(n, 0x340) && word(n) == paf + 0x18b578
        && slot(n, 0xb4) == paf + 0x105e20 && slot(n, 0x0c) == paf + 0x159004
        && slot(n, 0x54) == paf + 0x156cc4 && slot(n, 0x5c) == paf + 0xeced8
        && slot(n, 0x6c) == paf + 0x105d88 && slot(n, 0x70) == paf + 0x105dac
        && slot(n, 0x74) == paf + 0x105dd0 && slot(n, 0x78) == paf + 0x105df8
        && slot(n, 0x98) == paf + 0xeebac;
}
