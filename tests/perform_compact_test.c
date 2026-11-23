/* SPDX-License-Identifier: GPL-3.0-only
 * Copyright (C) 2026 Leo Kuroshita (@kurogedelic), Hügelton Instruments */
/* Regression checks for the compact performance layer retained by RINGS INTO CLOUDS. */
#define main hostsim_main
#include "hostsim.c"
#undef main

static int check(const char *name, int ok)
{
    printf("perform-compact: %-68s %s\n", name, ok ? "ok" : "FAIL");
    return ok ? 0 : 1;
}

int main(void)
{
    uint8_t map[10] = {0};
    uint32_t i;
    int bad = 0, changed = 0, bounded = 1;
    int32_t l[CTL], r[CTL], dry[CTL];

    host_tracks_init();
    bad += check("only LPF / HPF / FLANGER / PHASER and track mutes are available",
                 perf_avail() == (PF_BIT(PF_LPF) | PF_BIT(PF_HPF) | PF_BIT(PF_FLG) |
                                  PF_BIT(PF_PHS) | PF_MUTE));

    for (i = 0; i < PF_KEYS; i++)
        bad += check("factory key map contains no retired effect",
                     PF_DEF[i] == PF_N || PF_DEF[i] == PF_LPF || PF_DEF[i] == PF_HPF ||
                     PF_DEF[i] == PF_FLG || PF_DEF[i] == PF_PHS);

    perf_map_put(map, 0, PF_LPF);
    perf_map_put(map, 1, PF_HPF);
    perf_map_put(map, 2, PF_FLG);
    perf_map_put(map, 3, PF_PHS);
    perf_map_put(map, 4, PF_R8);       /* retired buffer effect must not be assignable */
    perf_map_put(map, 5, PF_RTHR);     /* retired global-bus throw must not be assignable */
    bad += check("saved key map round-trips the four retained effects and rejects retired effects",
                 perf_map_of(map, 0) == PF_LPF && perf_map_of(map, 1) == PF_HPF &&
                 perf_map_of(map, 2) == PF_FLG && perf_map_of(map, 3) == PF_PHS &&
                 perf_map_of(map, 4) == PF_N && perf_map_of(map, 5) == PF_N);

    memset(&pf, 0, sizeof pf);
    pf.lc = PF_TOP;
    for (i = 0; i < NTRK; i++)
        pf.mg[i] = 32768;
    perf_held = 0;
    perf_latched = 0;
    perf_latch_on = 0;
    perf_kill = 0;
    perf_k[0] = perf_k[1] = perf_k[2] = perf_k[3] = 0;
    for (i = 0; i < CTL; i++)
        l[i] = r[i] = dry[i] = (i & 1u) ? 20000 : -20000;
    perf_press(PF_LPF, 1);
    bad += check("LPF key activates the performance block", perf_begin(CTL));
    perf_block(l, r, CTL);
    for (i = 0; i < CTL; i++) {
        changed |= l[i] != dry[i] || r[i] != dry[i];
        bounded &= l[i] >= -32768 && l[i] <= 32767 && r[i] >= -32768 && r[i] <= 32767;
    }
    bad += check("LPF changes a bright test signal without exceeding audio bounds", changed && bounded);
    perf_press(PF_LPF, 0);
    (void)perf_begin(CTL);
    perf_block(l, r, CTL);

    memset(&pf, 0, sizeof pf);
    pf.lc = PF_TOP;
    for (i = 0; i < NTRK; i++)
        pf.mg[i] = 32768;
    perf_held = 0;
    perf_latched = 0;
    perf_press(PF_FLG, 1);
    bad += check("FLANGER key activates the retained stereo processor", perf_begin(CTL));
    for (i = 0; i < CTL; i++)
        l[i] = r[i] = (i & 1u) ? 12000 : -12000;
    perf_block(l, r, CTL);
    bounded = 1;
    for (i = 0; i < CTL; i++)
        bounded &= l[i] >= -32768 && l[i] <= 32767 && r[i] >= -32768 && r[i] <= 32767;
    bad += check("FLANGER output remains bounded on a high-level alternating signal", bounded);
    perf_press(PF_FLG, 0);

    printf("perform-compact: %s\n", bad ? "FAILED" : "all ok");
    return bad ? 1 : 0;
}
