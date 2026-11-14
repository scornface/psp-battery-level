/* Run each lifecycle scenario in a fresh process: loader ownership is static. */
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <pspkernel.h>
#include "vsh.h"
extern unsigned char battery_vsh_image[128];
static SceModule module;
static int failure, loads, starts, stops, unloads;

SceUID sceKernelLoadModuleBufferForKernel(SceSize size,
                                          void *data,
                                          int flags,
                                          SceKernelLMOption *option)
{
    assert(size == 128 && data == battery_vsh_image && !flags);
    assert(option->size == sizeof(*option) && option->mpidtext == 2 && option->mpiddata == 2);
    assert(!option->position && !option->flags && !option->access);
    ++loads;
    return failure == 1 ? -1 : 42;
}

SceModule *sceKernelFindModuleByUID(int id)
{
    assert(id == 42);
    return &module;
}

SceModule *sceKernelFindModuleByName(const char *name)
{
    assert(!strcmp(name, "PSPBatteryLevel"));
    return failure == 11 ? &module : 0;
}

int sceKernelStartModule(int id, unsigned n, void *p, int *status, void *option)
{
    assert(id == 42 && !n && !p && !option);
    ++starts;
    *status = failure == 9 ? -1 : 0;
    return failure == 5 ? -1 : 0;
}

int sceKernelStopModule(int id, unsigned n, void *p, int *status, void *option)
{
    assert(id == 42 && !n && !p && !option);
    ++stops;
    *status = failure == 8 ? -1 : 0;
    return failure == 6 ? -1 : 0;
}

int sceKernelUnloadModule(int id)
{
    assert(id == 42);
    ++unloads;
    return failure == 7 || failure == 10 ? -1 : 0;
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    failure = atoi(argv[1]);
    strcpy(module.modname, "PSPBatteryLevel");
    module.nsegment = 2;
    module.segmentaddr[0] = module.text_addr = 0x08810000;
    module.text_size = module.segmentsize[0] = 0x1000;
    module.segmentaddr[1] = 0x08820000;
    module.segmentsize[1] = 0x100;
    if (failure == 2 || failure == 10)
        module.modname[0] = 'X';
    if (failure == 3)
        module.segmentaddr[1] = 0x88000000;
    if (failure == 4)
        module.attribute = 0x1000;
    int result = battery_vsh_start();
    if (failure == 11) {
        assert(result == -24 && !loads && !starts && !unloads);
        return 0;
    }
    assert(loads == 1);
    if (failure == 1) {
        assert(result == -21 && !starts);
        assert(!battery_vsh_stop() && !unloads);
        return 0;
    }
    if (failure >= 2 && failure <= 4) {
        assert(result == -22 && !starts && unloads == 1);
        assert(!battery_vsh_stop());
        return 0;
    }
    if (failure == 10) {
        assert(result == -22 && !starts && unloads == 1);
        assert(battery_vsh_start() == -20 && loads == 1);
        assert(battery_vsh_stop() == -1);
        failure = 0;
        assert(!battery_vsh_stop() && !stops);
        return 0;
    }
    assert(result == (failure == 5 || failure == 9 ? -23 : 0));
    assert(starts == 1 && !unloads);
    assert(battery_vsh_start() == -20 && loads == 1);
    if (failure == 6 || failure == 7 || failure == 8) {
        assert(battery_vsh_stop() == -1);
        if (failure != 7)
            assert(!unloads);
        failure = 0;
        assert(!battery_vsh_stop());
    } else
        assert(!battery_vsh_stop());
    assert(!battery_vsh_stop());
    return 0;
}
