/* PAF native-float ABI: fourth C argument's bits must be in f12. */
    .set noreorder
    .text
    .global paf_float_bits
    .ent paf_float_bits
paf_float_bits:
    move $t9, $a0
    move $a0, $a1
    move $a1, $a2
    mtc1 $a3, $f12
    jr $t9
    nop
    .end paf_float_bits
