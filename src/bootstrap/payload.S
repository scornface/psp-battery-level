/* SPDX-License-Identifier: MIT - verified user PRX, loaded only in VSH. */
    .section .data
    .balign 64
    .global battery_vsh_image
    .global battery_vsh_image_end
battery_vsh_image:
    .incbin VSH_PAYLOAD
battery_vsh_image_end:
