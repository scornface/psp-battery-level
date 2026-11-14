/* SPDX-License-Identifier: MIT
 * Local freestanding aggregate-copy support. Do not import filesystem or
 * unrelated kernel libc services to initialize/copy owned C structures.
 */
#include <stddef.h>

void *memcpy(void *to, const void *from, size_t count)
{
    unsigned char *d = to;
    const unsigned char *s = from;
    for (size_t i = 0; i < count; ++i) {
        d[i] = s[i];
    }
    return to;
}

void *memset(void *to, int value, size_t count)
{
    unsigned char *d = to;
    for (size_t i = 0; i < count; ++i) {
        d[i] = (unsigned char)value;
    }
    return to;
}
