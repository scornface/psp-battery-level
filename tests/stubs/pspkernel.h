/* Host declarations only, not a Sony structure layout or hardware ABI oracle. */
#ifndef TEST_PSP_KERNEL_H
#define TEST_PSP_KERNEL_H
#include <stddef.h>
typedef int SceUID;
typedef unsigned SceSize;
typedef struct {
    unsigned size;
    int mpidtext, mpiddata;
    unsigned flags;
    unsigned char position, access;
    unsigned short reserved;
} SceKernelLMOption;
typedef struct {
    unsigned attribute;
    char modname[28];
    unsigned nsegment, segmentaddr[4], segmentsize[4], text_addr, text_size;
} SceModule;
#define PSP_MEMORY_PARTITION_USER 2
#define PSP_SMEM_Low 0
#define PSP_MODULE_INFO(a,b,c,d)
SceUID sceKernelLoadModuleBufferForKernel(SceSize, void *, int, SceKernelLMOption *);
int sceKernelStartModule(int, unsigned, void *, int *, void *);
int sceKernelStopModule(int, unsigned, void *, int *, void *);
int sceKernelUnloadModule(int);
SceModule *sceKernelFindModuleByUID(int);
SceModule *sceKernelFindModuleByName(const char *);
int sceKernelCreateThread(const char *, int (*)(SceSize, void *), int, int, unsigned, void *);
int sceKernelStartThread(int, unsigned, void *);
int sceKernelDeleteThread(int);
int sceKernelWaitThreadEnd(int, unsigned *);
int sceKernelDelayThread(unsigned);
unsigned sceKernelCpuSuspendIntr(void);
void sceKernelCpuResumeIntr(unsigned);
unsigned sceKernelGetSystemTimeLow(void);
unsigned sceKernelDevkitVersion(void);
unsigned sceKernelGetModel(void);
unsigned sceKernelInitKeyConfig(void);
unsigned sctrlSEGetVersion(void);
unsigned sctrlHENGetVersion(void);
unsigned sctrlHENGetMinorVersion(void);
#endif
