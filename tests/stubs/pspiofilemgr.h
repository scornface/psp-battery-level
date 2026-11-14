#include "pspkernel.h"
#define PSP_O_RDONLY 1
#define PSP_O_WRONLY 2
#define PSP_O_CREAT 0x100
#define PSP_O_APPEND 0x200
int sceIoOpen(const char *, int, int);
int sceIoRead(int, void *, unsigned);
int sceIoWrite(int, const void *, unsigned);
int sceIoClose(int);
