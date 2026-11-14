/* SPDX-License-Identifier: MIT
 * Authenticated zero-base words; relocation kinds: fixed, LO16, HI16, J26.
 * HI16 targets include signed-low carry. Never mask unknown runtime patches.
 */
typedef struct {
    unsigned offset, word, kind, target;
} Signature;

static const Signature signatures[] = {
    {0x0838, 0x27bdfff0, 0, 0},      {0x083c, 0xafbf0000, 0, 0},
    {0x0840, 0x3c070001, 2, 0xa1d0}, {0x0844, 0x2406ffff, 0, 0},
    {0x0848, 0x8ce3a1d0, 1, 0},      {0x084c, 0x8c640104, 0, 0},
    {0x0850, 0x14800014, 0, 0},      {0x0854, 0x2405ffff, 0, 0},
    {0x0858, 0x8c6300a4, 0, 0},      {0x085c, 0x3c028000, 0, 0},
    {0x0860, 0x34450105, 0, 0},      {0x0864, 0x30680002, 0, 0},
    {0x0868, 0x1100000e, 0, 0},      {0x086c, 0x30640100, 0, 0},
    {0x0870, 0x10800010, 0, 0},      {0x0874, 0x30650200, 0, 0},
    {0x0878, 0x00003021, 0, 0},      {0x087c, 0x240bffff, 0, 0},
    {0x0880, 0x00061880, 0, 0},      {0x0884, 0x10cb0007, 0, 0},
    {0x0888, 0x2405ffff, 0, 0},      {0x088c, 0x8ceca1d0, 1, 0},
    {0x0890, 0x006c3021, 0, 0},      {0x0894, 0x8cc501bc, 0, 0},
    {0x0898, 0x00a0f809, 0, 0},      {0x089c, 0x00000000, 0, 0},
    {0x08a0, 0x00002821, 0, 0},      {0x08a4, 0x8fbf0000, 0, 0},
    {0x08a8, 0x00a01021, 0, 0},      {0x08ac, 0x03e00008, 0, 0},
    {0x08b0, 0x27bd0010, 0, 0},      {0x4790, 0x27bdffd0, 0, 0},
    {0x4794, 0xafb10024, 0, 0},      {0x4798, 0x3c110001, 2, 0xa1d0},
    {0x479c, 0xafbf0028, 0, 0},      {0x47a0, 0xafb00020, 0, 0},
    {0x47a4, 0x8e23a1d0, 1, 0},      {0x47a8, 0x8c6400a4, 0, 0},
    {0x47ac, 0x048200d9, 0, 0},      {0x47b0, 0x8c6400b8, 0, 0},
    {0x47b4, 0x0c001a87, 3, 0},      {0x47b8, 0x00000000, 0, 0},
    {0x1d4c, 0x27bdffc0, 0, 0},      {0x1d50, 0x3c030001, 2, 0xa220},
    {0x1d54, 0xafb10024, 0, 0},      {0x1d58, 0x2471a220, 1, 0},
    {0x1d5c, 0x02202021, 0, 0},      {0x1d60, 0x00002821, 0, 0},
    {0x1d64, 0x24060374, 0, 0},      {0x1d68, 0xafbf0030, 0, 0},
    {0x1d6c, 0xafb3002c, 0, 0},      {0x1d70, 0xafb20028, 0, 0},
    {0x1d74, 0x3c120001, 2, 0xa1d0}, {0x1d78, 0x0c00249e, 3, 0},
    {0x1d7c, 0xafb00020, 0, 0},      {0x1d80, 0x0c002494, 3, 0},
    {0x1d84, 0xae51a1d0, 1, 0},
};

static unsigned signature_word(const Signature *s, unsigned base)
{
    if (s->kind == 1) {
        return (s->word & 0xffff0000) | ((s->word + base) & 0xffff);
    }
    if (s->kind == 2) {
        return (s->word & 0xffff0000) | (((base + s->target + 0x8000) >> 16) & 0xffff);
    }
    if (s->kind == 3) {
        return (s->word & 0xfc000000) | (((s->word & 0x03ffffff) + (base >> 2)) & 0x03ffffff);
    }
    return s->word;
}
