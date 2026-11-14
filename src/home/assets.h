/* SPDX-License-Identifier: MIT */
#ifndef HOME_ASSETS_H
#define HOME_ASSETS_H
#include "sprite.h"

typedef struct {
    HomeTiles tiles;
    HomeSprite reference; /* Authenticated compact, original-size 100% sprite. */
} HomeAssets;

/* Startup-only scratch, never allocate this on an interrupt/thread stack.
 * The caller owns exclusive access and may reclaim it before publishing hooks.
 * No pointer into scratch survives a successful preparation.
 */
typedef struct {
    unsigned char bytes[113677];
    uint16_t atlas[10 * HOME_TILE_PIXELS];
    HomeAssets prepared;
} HomeAssetWorkspace;

/* GAME worker only, before hooks/publication: reads exactly the two known Sony
 * files read-only, closes each handle, authenticates before parsing, and checks
 * the approved reference sprite. No logging, fallback, native pointer access,
 * callback work or runtime polling. Caller supplies disjoint output/scratch;
 * failure leaves output unchanged, scratch is unspecified. Return 0 on success,
 * -1 invalid storage, -10 I/O/length, -11 authentication/resource layout,
 * -13 PGF decode, -14 tile/reference composition or digest mismatch.
 */
int home_assets_prepare(HomeAssets *out, HomeAssetWorkspace *workspace);
#endif
