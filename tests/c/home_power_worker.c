/* Real sampler with mocked PSP services. Exhaustive values belong to the pure
 * frame/sprite suites; this harness verifies service ordering and publication. */
#include <assert.h>
#include "power_worker.h"
#include "home_tiles.h"
static int held, exists = 1, charge, reads;
static HomePowerFrames state;
static HomeTiles tiles;

int scePowerIsBatteryExist(void)
{
    assert(!held);
    return exists;
}

int scePowerGetBatteryLifePercent(void)
{
    assert(!held);
    ++reads;
    return charge;
}

unsigned sceKernelCpuSuspendIntr(void)
{
    assert(!held);
    held = 1;
    return 0x123;
}

void sceKernelCpuResumeIntr(unsigned irq)
{
    assert(held && irq == 0x123);
    held = 0;
}

int main(void)
{
    prepare_test_tiles(&tiles);
    HomePowerSample sample;
    static const int values[] = {0, 1, 9, 10, 42, 99, 100};
    for (unsigned i = 0; i < sizeof(values) / sizeof(*values); ++i) {
        charge = values[i];
        assert(home_power_poll(&state, &tiles, &sample) == 0);
        assert(!held && sample.percent == charge && sample.exists == 1);
        assert(sample.generation == i + 1);
        assert(home_power_front(&state)->percent == (unsigned)charge);
    }
    charge = -1;
    assert(home_power_poll(&state, &tiles, &sample) == 0 && !home_power_front(&state));
    charge = 101;
    assert(home_power_poll(&state, &tiles, &sample) == 0 && !home_power_front(&state));
    int previous = reads;
    exists = 0;
    assert(home_power_poll(&state, &tiles, &sample) == 0 && !home_power_front(&state));
    assert(reads == previous && sample.percent == -1);
    exists = -1;
    assert(home_power_poll(&state, &tiles, &sample) == 0 && !home_power_front(&state));
    exists = 1;
    charge = 42;
    assert(
        home_power_poll(&state, &tiles, &sample) == 0 && home_power_front(&state)->percent == 42
    );
    tiles.ready = 0;
    assert(home_power_poll(&state, &tiles, &sample) == -2 && !home_power_front(&state));
    assert(!held);
    return 0;
}
