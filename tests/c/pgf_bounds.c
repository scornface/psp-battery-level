/* Bounded-input mutation harness. Some mutations are valid; only memory safety
 * and the known unmodified glyph are asserted, not rejection of every change. */
#include <assert.h>
#include <stdio.h>
#include "pgf.h"

int main(int argc, char **argv)
{
    assert(argc == 2);
    FILE *input = fopen(argv[1], "rb");
    assert(input);
    unsigned char data[512];
    size_t size = fread(data, 1, sizeof(data), input);
    assert(size && feof(input));
    assert(!fclose(input));

    struct {
        unsigned before;
        PgfGlyph glyph;
        unsigned after;
    } out = {0};

    out.before = out.after = 0x12345678;
    assert(!pgf_glyph(data, size, '%', &out.glyph));
    assert(out.glyph.width == 1 && out.glyph.height == 1 && out.glyph.pixels[0] == 15);
    for (size_t length = 0; length < size; ++length)
        pgf_glyph(data, length, '%', &out.glyph);
    for (size_t i = 0; i < size; ++i) {
        unsigned char original = data[i];
        for (unsigned bit = 0; bit < 8; ++bit) {
            data[i] = original ^ (1u << bit);
            pgf_glyph(data, size, '%', &out.glyph);
            assert(out.before == 0x12345678 && out.after == 0x12345678);
        }
        data[i] = original;
    }
    return 0;
}
