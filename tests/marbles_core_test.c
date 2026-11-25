/* SPDX-License-Identifier: GPL-3.0-only
 * Copyright (C) 2026 Leo Kuroshita (@kurogedelic), Hügelton Instruments */
#include <stdio.h>
#include <stdint.h>
#include "../firmware/src/marbles_core.h"

static int check(const char *name, int ok)
{
    printf("%-42s %s\n", name, ok ? "ok" : "FAIL");
    return ok ? 0 : 1;
}

int main(void)
{
    uint32_t a = 1u, b = 1u, c = 7u, i, before;
    int bad = 0;
    uint16_t major = (uint16_t)((1u<<0)|(1u<<2)|(1u<<4)|(1u<<5)|(1u<<7)|(1u<<9)|(1u<<11));
    bad += check("seeded PRNG is repeatable", marbles_rng_next(&a) == marbles_rng_next(&b));
    bad += check("different seeds diverge", marbles_rng_next(&a) != marbles_rng_next(&c));
    bad += check("zero seed escapes absorbing state", marbles_rng_next(&(uint32_t){0}) != 0u);
    before = a;
    bad += check("zero probability is false without draw", !marbles_probability(&a, 0u) && a == before);
    bad += check("full probability is true without draw", marbles_probability(&a, 100u) && a == before);
    bad += check("zero bound is safe", marbles_rng_bounded(&a, 0u) == 0u);
    for (i = 0; i < 10000u; i++) {
        uint32_t v = marbles_rng_bounded(&a, 7u);
        if (v >= 7u) { bad++; break; }
    }
    bad += check("bounded draws stay in range", i == 10000u);
    bad += check("major scale snaps down", marbles_scale_snap(major, 0, 61) == 60);
    bad += check("major scale retains allowed pitch", marbles_scale_snap(major, 0, 64) == 64);
    bad += check("scale root wraps", marbles_scale_snap(major, 12, 61) == 60);
    bad += check("empty mask is chromatic", marbles_scale_snap(0, 0, 61) == 61);
    bad += check("MIDI bounds are enforced", marbles_scale_snap(major, 0, -20) == 0 &&
                                               marbles_scale_snap(major, 0, 200) == 127);
    return bad ? 1 : 0;
}
