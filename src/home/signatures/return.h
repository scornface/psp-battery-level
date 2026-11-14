/* SPDX-License-Identifier: MIT
 * Extra return-trial guards, not native write guards. Uses Signature from
 * signatures.h. No unknown instruction patches are masked.
 */
static const Signature post_signatures[] = {
    {0x2118, 0x3c040000, 2, 0x3a68},
    {0x211c, 0x24863a68, 1, 0},
    {0x2120, 0x00003821, 0, 0},
    {0x2124, 0x2404001e, 0, 0},
    {0x2128, 0x0c002482, 3, 0},
    {0x212c, 0x24050014, 0, 0},
    {0x2130, 0x24050014, 0, 0},
    {0x2134, 0x0c002480, 3, 0},
    {0x2138, 0x2404001e, 0, 0},
    {0x3a68, 0x27bdffc0, 0, 0},
    {0x3c78, 0x8cc50190, 0, 0},
    {0x3c7c, 0x14a0000c, 0, 0},
    {0x3cb0, 0x0c00020e, 3, 0},
    {0x3cb4, 0x00000000, 0, 0},
    {0x48e8, 0x8fb10024, 0, 0},
    {0x48ec, 0x8fb00020, 0, 0},
    {0x48f0, 0x03e00008, 0, 0},
    {0x48f4, 0x27bd0030, 0, 0},
};
