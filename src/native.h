/* SPDX-License-Identifier: MIT
 * Sony 6.61 native ABI boundary. Node operations require the verified XMB
 * callback/PAF lock context. These offsets are version-specific observations,
 * not a general-purpose PAF SDK; never bypass the discovery/signature guards.
 */
#ifndef BATTERY_NATIVE_H
#define BATTERY_NATIVE_H
#include <stdint.h>
typedef uintptr_t U;
extern U paf, vsh;
typedef struct {
    int paf_query, vsh_query;
    unsigned paf_base, vsh_base, paf_size, vsh_size, checks;
} NativeDiscovery;
int native_discover(NativeDiscovery *info);
int user_address(U p, unsigned size);
extern int paf_float_bits(U target, U node, unsigned id, unsigned bits);
/* Tiny memory/bit helpers remain inline; no per-translation-unit module state. */
#ifdef BATTERY_HOST_TEST
unsigned word(U p);
unsigned byte(U p);
void write_word(U p, unsigned value);
#else
static inline unsigned word(U p) { return *(volatile unsigned *)p; }
static inline unsigned byte(U p) { return *(volatile unsigned char *)p; }
static inline void write_word(U p, unsigned value) { *(volatile unsigned *)p = value; }
#endif
static inline U slot(U n, unsigned offset) { return word(word(n) + offset); }
static inline unsigned fbits(float f) { union { float f; unsigned b; } u = {.f = f}; return u.b; }
static inline float from_bits(unsigned b) { union { float f; unsigned b; } u = {.b = b}; return u.f; }
void position(U n, const float v[4]);
void visibility(U n, int visible);
int style(U n);
unsigned occurrences(U parent, unsigned offset, U needle);
int signatures(void);
int text_vtable(U n);
void destroy_text(U n);
#endif
