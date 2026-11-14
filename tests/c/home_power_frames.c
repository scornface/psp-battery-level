/* Pure staging/commit contract: old front remains immutable until publication. */
#include <assert.h>
#include <string.h>
#include "power_frames.h"
#include "home_tiles.h"
static HomePowerFrames state;
static HomeTiles tiles;

int main(void)
{
    prepare_test_tiles(&tiles);
    assert(!home_power_front(&state));
    for (unsigned value = 0; value <= 100; ++value) {
        HomePowerUpdate update;
        HomeSprite before = state.frames[state.front];
        unsigned front = state.front, valid = state.valid;
        assert(home_power_stage(&state, &tiles, 1, (int)value, &update) == 0);
        assert(state.front == front && state.valid == valid);
        assert(memcmp(&before, &state.frames[front], sizeof(before)) == 0);
        if (valid)
            assert(home_power_front(&state)->percent == value - 1);
        assert(update.slot == (front ^ 1u) && update.valid == 1);
        assert(home_power_commit(&state, &update) == 0);
        assert(home_power_front(&state)->percent == value && state.generation == value + 1);
    }
    for (unsigned n = 0; n < 4; ++n) {
        int exists = n == 0 ? 0 : n == 1 ? -1 : 1;
        int sample = n == 2 ? -1 : n == 3 ? 101 : 50;
        HomePowerUpdate update;
        assert(home_power_stage(&state, &tiles, exists, sample, &update) == 0 && !update.valid);
        assert(home_power_commit(&state, &update) == 0 && !home_power_front(&state));
    }
    HomePowerUpdate update;
    assert(home_power_stage(&state, &tiles, 1, 42, &update) == 0);
    assert(home_power_commit(&state, &update) == 0 && home_power_front(&state)->percent == 42);
    HomePowerUpdate bad = {state.front, 1, 42};
    unsigned generation = state.generation;
    assert(home_power_commit(&state, &bad) == -1 && state.generation == generation);
    state.front = 2;
    assert(!home_power_front(&state));
    assert(home_power_stage(&state, &tiles, 1, 42, &update) == -1);
    return 0;
}
