/* SPDX-License-Identifier: MIT
 * Preserve Sony inputs across the pre-helper and Sony outputs across the post-
 * helper. Both helpers use integer-only code and the normal kernel ABI.
 * Token storage is per frame: a nested hook cannot claim an outer refresh.
 * Stack layout: 0..15 outgoing argument area; 16/20 caller ra/gp;
 * 24..52 saved inputs (v0/v1 reused for Sony results); 60/64 HI/LO;
 * 68 pre-helper token. Do not reuse the callee-owned outgoing area for saves.
 */
    .set noreorder
    .text
    .align 2
    .global home_callback
    .ent home_callback
home_callback:
    addiu $sp, $sp, -96
    sw $ra, 16($sp)
    sw $gp, 20($sp)
    sw $v0, 24($sp)
    sw $v1, 28($sp)
    sw $a0, 32($sp)
    sw $a1, 36($sp)
    sw $a2, 40($sp)
    sw $a3, 44($sp)
    sw $t0, 48($sp)
    sw $t1, 52($sp)
    mfhi $t0
    sw $t0, 60($sp)
    mflo $t0
    sw $t0, 64($sp)
    lw $a0, 16($sp)
    lui $t9, %hi(home_before)
    addiu $t9, $t9, %lo(home_before)
    jalr $t9
    nop
    sw $v0, 68($sp)
    lw $t0, 60($sp)
    mthi $t0
    lw $t0, 64($sp)
    mtlo $t0
    lw $v0, 24($sp)
    lw $v1, 28($sp)
    lw $a0, 32($sp)
    lw $a1, 36($sp)
    lw $a2, 40($sp)
    lw $a3, 44($sp)
    lw $t0, 48($sp)
    lw $t1, 52($sp)
    lw $gp, 20($sp)
    lui $t9, %hi(home_original)
    lw $t9, %lo(home_original)($t9)
    jalr $t9
    nop
    sw $v0, 24($sp)
    sw $v1, 28($sp)
    mfhi $t0
    sw $t0, 60($sp)
    mflo $t0
    sw $t0, 64($sp)
    lw $a0, 16($sp)
    lw $a1, 68($sp)
    lui $t9, %hi(home_after)
    addiu $t9, $t9, %lo(home_after)
    jalr $t9
    nop
    lw $t0, 60($sp)
    mthi $t0
    lw $t0, 64($sp)
    mtlo $t0
    lw $v0, 24($sp)
    lw $v1, 28($sp)
    lw $gp, 20($sp)
    lw $ra, 16($sp)
    jr $ra
    addiu $sp, $sp, 96
    .end home_callback
