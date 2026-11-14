/* SPDX-License-Identifier: MIT
 * Narrow GAME startup resource exception. File I/O is not a renderer service.
 * Keep the paths, exact sizes and hashes closed; no configurable asset source.
 */
#include <pspiofilemgr.h>
#include <psputils.h>
#include "assets.h"
#include "pgf.h"

static int same_digest(const unsigned char a[20], const unsigned char b[20])
{
    for (unsigned i = 0; i < 20; ++i)
        if (a[i] != b[i])
            return 0;
    return 1;
}

static int read_asset(HomeAssetWorkspace *work,
                      const char *path,
                      unsigned size,
                      const unsigned char expected[20])
{
    if (size >= sizeof(work->bytes))
        return -10;
    SceUID fd = sceIoOpen(path, PSP_O_RDONLY, 0);
    if (fd < 0)
        return -10;
    unsigned n = 0;
    int error = 0;
    /* Read one byte beyond the expected extent to reject trailing data, too.
     * Partial reads are permitted; an error or oversized provider result is not.
     */
    while (n < size + 1) {
        unsigned remaining = size + 1 - n;
        int got = sceIoRead(fd, work->bytes + n, remaining);
        if (got < 0 || (unsigned)got > remaining) {
            error = 1;
            break;
        }
        if (!got)
            break;
        n += (unsigned)got;
    }
    int closed = sceIoClose(fd);
    if (error || closed < 0 || n != size)
        return -10;
    unsigned char digest[20];
    if (sceKernelUtilsSha1Digest(work->bytes, n, digest) || !same_digest(digest, expected))
        return -11;
    return 0;
}

static unsigned le32(const unsigned char *p)
{
    return p[0] | ((unsigned)p[1] << 8) | ((unsigned)p[2] << 16) | ((unsigned)p[3] << 24);
}

int home_assets_prepare(HomeAssets *out, HomeAssetWorkspace *work)
{
    if (!out || !work)
        return -1;
    /* Difference-based bounds avoid end-pointer overflow and reject overlapping
     * caller storage before any I/O or output publication. Both are owned,
     * normally cached objects, never Sony cached/uncached buffer aliases.
     */
    uintptr_t a = (uintptr_t)out, b = (uintptr_t)work;
    if (a <= b ? b - a < sizeof(*out) : a - b < sizeof(*work))
        return -1;
    static const unsigned char resource_hash[20] = {0x3f, 0x91, 0xe6, 0xc8, 0xf5, 0xeb, 0x14,
                                                    0xcd, 0x31, 0x80, 0x23, 0x5b, 0xaa, 0x39,
                                                    0x65, 0x93, 0xc4, 0x95, 0x97, 0x0f};
    static const unsigned char font_hash[20] = {0xca, 0xf7, 0x1c, 0x8b, 0xed, 0x92, 0x37,
                                                0x49, 0xea, 0x3b, 0x8b, 0xb9, 0x6b, 0xc0,
                                                0xa5, 0x8c, 0x4c, 0x10, 0x52, 0x98};
    static const unsigned char sprite_hash[20] = {0x1a, 0x01, 0x1d, 0xc6, 0x1c, 0xb7, 0x72,
                                                  0x18, 0xf5, 0x48, 0xdc, 0xf6, 0x24, 0xbb,
                                                  0x18, 0x79, 0x04, 0xdd, 0x82, 0x94};
    int result = read_asset(work, "flash0:/kd/resource/impose.rsc", 113676, resource_hash);
    if (result)
        return result;
    unsigned start = le32(work->bytes + 12 + 25 * 4);
    if (start > 113676 - 4804 || le32(work->bytes + start) != 4800)
        return -11;
    for (unsigned i = 0; i < 2400; ++i)
        work->atlas[i] =
            work->bytes[start + 4 + i * 2] | ((unsigned)work->bytes[start + 5 + i * 2] << 8);
    result = read_asset(work, "flash0:/font/ltn8.pgf", 41000, font_hash);
    if (result)
        return result;
    PgfGlyph glyph;
    if (pgf_glyph(work->bytes, 41000, '%', &glyph))
        return -13;
    if (home_tiles_prepare(
            &work->prepared.tiles, work->atlas, 2400, glyph.pixels, glyph.width, glyph.height) ||
        home_sprite_compose(&work->prepared.tiles, 100, &work->prepared.reference))
        return -14;
    unsigned char digest[20];
    if (sceKernelUtilsSha1Digest((unsigned char *)work->prepared.reference.pixels,
                                 sizeof(work->prepared.reference.pixels),
                                 digest) ||
        !same_digest(digest, sprite_hash))
        return -14;
    *out = work->prepared;
    return 0;
}
