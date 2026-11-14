/* Aligned synthetic user image for the host loader contract. */
#ifdef __APPLE__
#define IMAGE _battery_vsh_image
#define END _battery_vsh_image_end
#else
#define IMAGE battery_vsh_image
#define END battery_vsh_image_end
#endif
.data
.p2align 6
.globl IMAGE
.globl END
IMAGE:
.space 128
END:
#ifndef __APPLE__
.section .note.GNU-stack,"",@progbits
#endif
