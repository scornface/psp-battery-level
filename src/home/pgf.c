/* SPDX-License-Identifier: MIT
 * Narrow revision-2 PGF reader. Every bit access is checked against the current
 * record's end; table lookups temporarily use the authenticated file extent.
 * Only foreground coverage needed by the HOME percent sprite is decoded.
 */
#include "pgf.h"

typedef struct {
    const unsigned char *data;
    size_t pos, end;
    int failed;
} Bits;

/* PGF fields are packed least-significant bit first. Failure is sticky, so a
 * truncated field cannot be mistaken for a successfully decoded zero value. */
static uint32_t bits(Bits *b, unsigned n)
{
    uint32_t value = 0;
    if (n > 32 || b->pos > b->end || n > b->end - b->pos) {
        b->failed = 1;
        return 0;
    }
    for (unsigned i = 0; i < n; ++i, ++b->pos) {
        value |= (uint32_t)((b->data[b->pos / 8] >> (b->pos % 8)) & 1) << i;
    }
    return value;
}

static uint32_t at(Bits *b, size_t pos, unsigned n)
{
    b->pos = pos;
    return bits(b, n);
}

static int signed7(unsigned v)
{
    return v & 64 ? (int)v - 128 : (int)v;
}

/* Runs cover either row-major or column-major source order; callers have
 * already bounded dimensions to 32x32. Always emit row-major coverage. */
static int bitmap(Bits *b, PgfGlyph *out, unsigned flags)
{
    unsigned total = out->width * out->height, produced = 0;
    while (produced < total && !b->failed) {
        unsigned code = bits(b, 4), count = code < 8 ? code + 1 : 16 - code;
        unsigned value = code < 8 ? bits(b, 4) : 0;
        if (count > total - produced) {
            return -8;
        }
        for (unsigned i = 0; i < count; ++i, ++produced) {
            if (code >= 8) {
                value = bits(b, 4);
            }
            unsigned x = (flags & 3) == 1 ? produced % out->width : produced / out->height;
            unsigned y = (flags & 3) == 1 ? produced / out->width : produced % out->height;
            out->pixels[y * out->width + x] = value;
        }
    }
    return b->failed ? -9 : 0;
}

int pgf_glyph(const unsigned char *data, size_t size, unsigned character, PgfGlyph *out)
{
    if (!data || !out || size < 392 || size > 131072) {
        return -1;
    }
    Bits b = {data, 0, size * 8, 0};
    if (at(&b, 16, 16) != 392 || at(&b, 32, 32) != 0x30464750 || at(&b, 64, 32) != 2) {
        return -2;
    }
    unsigned map_length = at(&b, 128, 32), pointer_length = at(&b, 160, 32);
    unsigned map_bits = at(&b, 192, 32), pointer_bits = at(&b, 224, 32);
    unsigned first = at(&b, 182 * 8, 16);
    unsigned shadow_length = at(&b, 364 * 8, 32), shadow_bits = at(&b, 368 * 8, 32);
    if (!map_bits || map_bits > 16 || !pointer_bits || pointer_bits > 24 || map_length > 65536 ||
        pointer_length > 65536 || shadow_length > 65536 || shadow_bits > 24 || character < first ||
        character - first >= map_length) {
        return -3;
    }

    /* Header table counts select 8-byte metric records. Packed maps/pointers
     * are padded to whole 32-bit words; glyph pointers use 4-byte units. */
    size_t advances = 392 + (data[258] + data[259] + data[260]) * 8u;
    size_t cmap = advances + data[261] * 8u + ((shadow_length * shadow_bits + 31u) / 32u) * 4u;
    size_t pointers = cmap + ((map_length * map_bits + 31u) / 32u) * 4u;
    size_t base = pointers + ((pointer_length * pointer_bits + 31u) / 32u) * 4u;
    unsigned index = at(&b, cmap * 8 + (character - first) * map_bits, map_bits);
    if (b.failed || index >= pointer_length) {
        return -4;
    }
    unsigned offset = at(&b, pointers * 8 + index * pointer_bits, pointer_bits);
    size_t start = (base + offset * 4u) * 8;
    unsigned length = at(&b, start, 14);
    if (b.failed || !length || start > size * 8 || length * 8u > size * 8 - start) {
        return -5;
    }

    b.end = start + length * 8u;
    out->width = bits(&b, 7);
    out->height = bits(&b, 7);
    out->left = signed7(bits(&b, 7));
    out->top = signed7(bits(&b, 7));
    unsigned flags = bits(&b, 6);
    if (!(flags & 3) || (flags & 3) > 2 || !out->width || out->width > 32 || !out->height ||
        out->height > 32) {
        return -6;
    }

    bits(&b, 7);
    bits(&b, 9);
    for (unsigned mask = 4; mask <= 16; mask <<= 1) {
        if (flags & mask) {
            bits(&b, 8);
        } else {
            bits(&b, 32);
            bits(&b, 32);
        }
    }
    if (flags & 32) {
        unsigned advance_index = bits(&b, 8);
        size_t saved = b.pos, end = b.end;
        if (advance_index >= data[261]) {
            return -7;
        }
        /* Metric lookup is outside the glyph record. Restore both cursor and
         * record limit before decoding its bitmap; never widen RLE bounds. */
        b.end = size * 8;
        out->advance = (int32_t)at(&b, (advances + advance_index * 8u) * 8, 32);
        b.pos = saved;
        b.end = end;
    } else {
        out->advance = (int32_t)bits(&b, 32);
        bits(&b, 32);
    }
    if (b.failed || out->advance <= 0 || out->advance > 32 * 64) {
        return -7;
    }

    return bitmap(&b, out, flags);
}
