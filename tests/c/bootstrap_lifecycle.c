/* PSP services are synchronous mocks; this tests ownership/order, not scheduling. */
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <pspkernel.h>
#include "context.h"
#include "../home/backend.h"
int module_start(SceSize, void *);
int module_stop(SceSize, void *);
static int mode, held, published, vsh_started, vsh_stopped, home_started, deleted, ran;
static int (*entry)(SceSize, void *);
static volatile int *stop_pointer;
unsigned sceKernelDevkitVersion(void) { return 0x06060010; }
unsigned sceKernelGetModel(void) { return 1; }
unsigned sceKernelInitKeyConfig(void) { return mode == 2 ? 0x300 : mode == 1 ? 0x200 : 0x100; }
unsigned sctrlSEGetVersion(void) { return 4; }
unsigned sctrlHENGetVersion(void) { return 20; }
unsigned sctrlHENGetMinorVersion(void) { return 69; }
int sceKernelCreateThread(const char *name, int (*f)(SceSize, void *), int priority, int stack, unsigned attr, void *option)
{
    assert(!strcmp(name, "battery_bootstrap") && priority == 0x30 && stack == 0x8000 && !attr && !option);
    entry = f; return mode == 3 ? -1 : 42;
}
int sceKernelStartThread(int id, unsigned n, void *p)
{
    assert(id == 42 && !n && !p);
    if (mode == 4) return -1;
    if (mode != 5) { ran = 1; entry(0, 0); }
    return 0;
}
int sceKernelDeleteThread(int id) { assert(id == 42); ++deleted; return 0; }
int sceKernelWaitThreadEnd(int id, unsigned *timeout) { assert(id == 42 && *timeout == 100000); return mode == 6 ? -1 : 0; }
int sceKernelDelayThread(unsigned n) { assert(n == 100000); if (!ran && entry) { ran = 1; entry(0, 0); } return 0; }
unsigned sceKernelCpuSuspendIntr(void) { assert(!held); held = 1; return 123; }
void sceKernelCpuResumeIntr(unsigned irq) { assert(held && irq == 123); held = 0; }
int battery_vsh_start(void) { assert(!held && !home_started); ++vsh_started; return 0; }
int battery_vsh_stop(void) { assert(!held); ++vsh_stopped; return mode == 7 ? -1 : 0; }
int home_can_unload(void) { assert(held); return !published; }
int home_run(volatile int *stop, void (*poll)(void))
{
    assert(!held && !vsh_started && !poll); ++home_started; stop_pointer = stop;
    assert(!*stop); published = 1; return 0;
}
int main(int argc, char **argv)
{
    assert(argc == 2); mode = atoi(argv[1]);
    int result = module_start(0, 0);
    if (mode == 3) { assert(result == -1 && !deleted); assert(!module_stop(0, 0)); return 0; }
    if (mode == 4) { assert(result == -1 && deleted == 1); assert(!module_stop(0, 0)); return 0; }
    assert(!result && module_start(0, 0) == -1);
    if (mode == 1) {
        assert(home_started == 1 && !vsh_started && stop_pointer && !*stop_pointer);
        assert(module_stop(0, 0) == -1 && !*stop_pointer && !deleted && !vsh_stopped); return 0;
    }
    assert(module_stop(0, 0) == (mode == 6 || mode == 7 ? -1 : 0));
    assert(!home_started);
    if (mode == 2 || mode == 5) assert(!vsh_started);
    else assert(vsh_started == 1);
    if (mode == 6) assert(!vsh_stopped && !deleted);
    if (mode == 7) assert(vsh_stopped == 1 && !deleted);
    return 0;
}
