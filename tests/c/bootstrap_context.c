#include <assert.h>
#include "context.h"
int main(void)
{
    assert(battery_context(0x06060010, 1, 0x100, 4, 20, 69) == BATTERY_VSH);
    assert(battery_context(0x06060010, 1, 0x200, 4, 20, 69) == BATTERY_GAME);
    for (unsigned key = 0; key < 0x500; ++key)
        if (key != 0x100 && key != 0x200) assert(!battery_context(0x06060010, 1, key, 4, 20, 69));
    assert(!battery_context(0x06060010, 0, 0x100, 4, 20, 69));
    assert(!battery_context(0x06060000, 1, 0x100, 4, 20, 69));
    assert(!battery_context(0x06060010, 1, 0x200, 5, 20, 69));
    assert(!battery_context(0x06060010, 1, 0x200, 4, 21, 69));
    assert(!battery_context(0x06060010, 1, 0x200, 4, 20, 70));
    return 0;
}
