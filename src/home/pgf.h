/* SPDX-License-Identifier: MIT
 * Bounded decoder for the authenticated revision-2 Latin PGF resource only.
 * Produces original 4-bit coverage, no scaling or substitute font.
 */
#ifndef HOME_PGF_H
#define HOME_PGF_H
#include <stddef.h>
#include <stdint.h>
typedef struct {
    unsigned width, height;
    int left, top, advance;
    unsigned char pixels[32 * 32];
} PgfGlyph;
/* Caller authenticates input first. Returns 0 on success or a negative parse
 * error; output is scratch and may be partially filled on failure. Bearings
 * and advance retain PGF units; pixels are row-major 0..15 coverage values. */
int pgf_glyph(const unsigned char *data, size_t size, unsigned character, PgfGlyph *out);
#endif
