/* Exercise real controller/guard code with sparse, checked native memory.
 * No PSP headers, mapped host pointers, firmware or Sony functions are used.
 */
#include <assert.h>
#include <string.h>
#define BATTERY_HOST_TEST 1
#define BATTERY_DIAGNOSTICS 0
#include "../src/native.c"
#include "../src/xmb.c"

volatile int stop_requested;
static struct { U address; unsigned value; } memory[4096];
static unsigned used, dispatches, destructions, reflows, reads, try_failure;
static int leave_registration;
unsigned word(U p)
{
    assert(user_address(p, 4)); ++reads;
    for (unsigned i = 0; i < used; ++i) if (memory[i].address == p) return memory[i].value;
    return 0;
}
unsigned byte(U p) { return word(p & ~(U)3) >> ((p & 3) * 8) & 255; }
void write_word(U p, unsigned value)
{
    assert(user_address(p, 4));
    for (unsigned i = 0; i < used; ++i) if (memory[i].address == p) { memory[i].value = value; return; }
    assert(used < 4096); memory[used].address = p; memory[used++].value = value;
}
int kuKernelFindModuleByName(char *name, ModuleDescriptor *out) { (void)name; (void)out; return -1; }
int sceKernelGetThreadId(void) { return 1; }
unsigned sceKernelGetSystemTimeLow(void) { return 10; }
unsigned sceKernelTotalFreeMemSize(void) { return 0; }
void sceKernelDcacheWritebackRange(void *p, unsigned n) { (void)p; (void)n; }
int sceUsbGetDrvState(const char *s) { (void)s; return 2; }
int sceKernelLockLwMutex(SceLwMutexWorkarea *p, int n, void *t)
{ (void)p; (void)n; (void)t; return 0; }
int sceKernelTryLockLwMutex(SceLwMutexWorkarea *p, int n)
{ (void)p; (void)n; return try_failure ? -1 : 0; }
int sceKernelUnlockLwMutex(SceLwMutexWorkarea *p, int n) { (void)p; (void)n; return 0; }
void position(U n, const float v[4])
{ ++dispatches; for (unsigned i = 0; i < 4; ++i) write_word(n + 0x220 + i * 4, fbits(v[i])); }
void visibility(U n, int v) { (void)n; (void)v; ++dispatches; }
int style(U n) { (void)n; ++dispatches; return 0; }
int paf_float_bits(U target, U node, unsigned id, unsigned bits)
{
    (void)target; (void)node; (void)id; ++reflows;
    write_word(clock_node + 0x220, bits); return 0;
}
void destroy_text(U n)
{
    ++destructions;
    if (leave_registration) return;
    for (unsigned k = 0; k < 2; ++k) {
        U offset = k ? 0x1d8 : 0x1b4, data = word(parent + offset);
        unsigned count = word(parent + offset + 4);
        for (unsigned i = 0; i < count; ++i) if (word(data + i * 4) == n) {
            for (unsigned j = i; j + 1 < count; ++j) write_word(data + j * 4, word(data + (j + 1) * 4));
            write_word(parent + offset + 4, count - 1); break;
        }
    }
}
static void add_node(U n, int text)
{
    write_word(n, paf + (text ? 0x18b578 : 0x18b068));
    write_word(n + 0x1d4, parent);
    if (text) {
        U sub = n + 0x800;
        write_word(n + 0x1e8, sub); write_word(sub, paf + 0x18c118);
        write_word(sub + 0x1c, sub + 0x100);
    }
}
static void setup(void)
{
    used = dispatches = destructions = reflows = reads = try_failure = 0;
    leave_registration = 0; unsafe_node = teardown_failed = requested_fault = reflowing = 0;
    retired_nodes[0] = retired_nodes[1] = 0; stop_requested = 0;
    paf = 0x08800000; vsh = 0x0a000000; parent = 0x09800000; clock_node = 0x09810000;
    new_node = 0x09820000; shown_node = 0;
    status = (Status){.installed = 1, .desired = 50};
    write_word(paf + 0x190640, 1); write_word(paf + 0x190644, 1);
    write_word(vsh + 0x5cab4, clock_node); write_word(parent, paf + 0x18b218);
    write_word(paf + 0x18b218 + 0x4c, paf + 0xec0c8);
    write_word(paf + 0x18b218 + 0x50, paf + 0xec178);
    const unsigned offsets[] = {0xb4, 0x0c, 0x54, 0x5c, 0x6c, 0x70, 0x74, 0x78, 0x98};
    const unsigned targets[] = {0x105e20, 0x159004, 0x156cc4, 0xeced8, 0x105d88, 0x105dac, 0x105dd0, 0x105df8, 0xeebac};
    for (unsigned i = 0; i < 9; ++i) write_word(paf + 0x18b578 + offsets[i], paf + targets[i]);
    write_word(paf + 0x18c118 + 0x78, paf + 0x11a5c8);
    bar_nodes[0] = 0x09830000; bar_nodes[1] = 0x09840000; bar_nodes[2] = clock_node;
    add_node(clock_node, 1); add_node(new_node, 1);
    add_node(bar_nodes[0], 0); add_node(bar_nodes[1], 0);
    write_word(vsh + 0x5caac, bar_nodes[0]); write_word(vsh + 0x5cab0, bar_nodes[1]);
    for (unsigned i = 0; i < 4; ++i) {
        auxiliary_nodes[i] = 0x09850000 + i * 0x1000;
        add_node(auxiliary_nodes[i], 0); write_word(vsh + 0x5cab8 + i * 4, auxiliary_nodes[i]);
    }
    for (unsigned i = 0; i < 3; ++i) for (unsigned j = 0; j < 4; ++j) {
        baseline[i][j] = expected[i][j] = j == 3 ? 1 : 0;
        write_word(bar_nodes[i] + 0x220 + j * 4, fbits(expected[i][j]));
    }
    U nodes[] = {clock_node, new_node, bar_nodes[0], bar_nodes[1], auxiliary_nodes[0], auxiliary_nodes[1], auxiliary_nodes[2], auxiliary_nodes[3]};
    for (unsigned k = 0; k < 2; ++k) {
        U offset = k ? 0x1d8 : 0x1b4, data = 0x09900000 + k * 0x1000;
        write_word(parent + offset, data); write_word(parent + offset + 4, 8); write_word(parent + offset + 8, 8);
        for (unsigned i = 0; i < 8; ++i) write_word(data + i * 4, nodes[i]);
        totals[k] = 7;
    }
    U head = 0x09910000, item = head + 0x100, layout_data = head + 0x200;
    write_word(clock_node + 0x1a0, head); write_word(head + 4, item);
    write_word(item + 4, head); write_word(item + 8, 100); write_word(item + 0x30, (unsigned)(U)callback);
    event_slot = item + 0x30;
    write_word(clock_node + 0x160, layout_data); write_word(clock_node + 0x164, 1); write_word(clock_node + 0x168, 1);
    write_word(layout_data, 0x2000c); write_word(layout_data + 4, (unsigned)(U)layout_callback);
}
int main(void)
{
    setup(); write_word(parent + 0x1b4, 3);
    assert(occurrences(parent, 0x1b4, new_node) == ~0u);
    setup(); write_word(new_node, paf + 0x18b068);
    unsigned width; float box;
    assert(metrics(new_node, &width, &box) == -34);
    assert(cleanup() == -34 && !dispatches && !destructions);
    setup(); leave_registration = 1;
    assert(cleanup() == -27 && destructions == 1);
    assert(cleanup() == -27 && destructions == 1);
    write_word(paf + 0x190640, 0); assert(!xmb_can_unload());
    setup(); totals[0] = 6;
    assert(cleanup() == -27 && !new_node);
    assert(cleanup() == -27);
    setup(); bar_nodes[0] = 3; write_word(vsh + 0x5caac, 3);
    assert(reconcile_clock() == -31 && !reflows);
    setup(); write_word(paf + 0x190644, 2);
    fault(-20, 3); assert(!status.outcome && requested_fault == -20);
    write_word(paf + 0x190644, 1); fault(requested_fault, 7); assert(status.outcome == -20);
    setup(); assert(cleanup() == 0 && destructions == 1 && !status.installed);
    write_word(paf + 0x190640, 0); try_failure = 1; assert(!xmb_can_unload());
    try_failure = 0; assert(xmb_can_unload());
    setup(); U old = event_slot, head = word(clock_node + 0x1a0), replacement = head + 0x400;
    write_word(head + 4, replacement); write_word(replacement + 4, head);
    write_word(replacement + 8, 100); write_word(replacement + 0x30, (unsigned)(U)callback);
    assert(clock_event_slot((U)(unsigned)(U)callback) == replacement + 0x30);
    assert(old != replacement + 0x30);
    setup(); U backend = word(word(new_node + 0x1e8) + 0x1c);
    write_word(backend + 0x148, 1); write_word(backend + 0x144, 2);
    write_word(backend + 0x130, fbits(10.2f)); write_word(backend + 0x120, fbits(10.5f));
    stable = previous_width = previous_box = 0; status.native_visible = 0;
    assert(layout() == 0);
    write_word(backend + 0x120, fbits(11)); assert(layout() == 0);
    assert(layout() == 2 && !dispatches);
    setup(); destroy_text(new_node); new_node = 0; destructions = 0;
    for (unsigned j = 0; j < 16; ++j) write_word(parent + 0x2a0 + j * 4, fbits(j % 5 == 0 ? 1 : 0));
    const float xs[] = {223, 225, 203}, ys[] = {124, 122, 123};
    for (unsigned i = 0; i < 3; ++i) {
        write_word(bar_nodes[i] + 0x220, fbits(xs[i])); write_word(bar_nodes[i] + 0x224, fbits(ys[i]));
        for (unsigned j = 0; j < 3; ++j) write_word(bar_nodes[i] + 0x230 + j * 4, fbits(1));
        if (i < 2) { write_word(bar_nodes[i] + 0x320, fbits(44)); write_word(bar_nodes[i] + 0x324, fbits(16)); }
    }
    write_word(event_slot, vsh + 0x30ba8);
    write_word(word(clock_node + 0x160) + 4, vsh + 0x3113c);
    memset(auxiliary_nodes, 0, sizeof(auxiliary_nodes));
    assert(xmb_install() == 0 && !dispatches && !destructions);
    return 0;
}
