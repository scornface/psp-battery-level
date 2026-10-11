/* PSP scheduler declarations for the controller's deterministic fake backend. */
#ifndef BATTERY_RUNTIME_HOST_H
#define BATTERY_RUNTIME_HOST_H
typedef struct { unsigned words[8]; } SceLwMutexWorkarea;
int sceKernelLockLwMutex(SceLwMutexWorkarea *, int, void *);
int sceKernelTryLockLwMutex(SceLwMutexWorkarea *, int);
int sceKernelUnlockLwMutex(SceLwMutexWorkarea *, int);
int sceKernelGetThreadId(void);
unsigned sceKernelGetSystemTimeLow(void);
unsigned sceKernelTotalFreeMemSize(void);
void sceKernelDcacheWritebackRange(void *, unsigned);
int sceUsbGetDrvState(const char *);
#endif
