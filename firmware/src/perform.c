/* SPDX-License-Identifier: GPL-3.0-only
 * Copyright (C) 2026 Leo Kuroshita (@kurogedelic), Hügelton Instruments */
/* PERFORM: compact live performance processing on the master. The FX layer can hold LPF, HPF,
 * FLANGER and PHASER on the white keys; black keys 1..4 mute tracks 1..4 while held.
 * The loop recorder, repeat/reverse, tape stop, freeze, octave shifter and delay/reverb throws are retired.
 * Remaining effects ramp in/out and can be combined. FILTER, CRUSH and DEPTH remain as performance macros.
 * The processing order is LPF -> HPF -> CRUSH -> FLANGER -> PHASER, after master level and before master_out.
 * Idle (no key, no knob, no ramp left) every stage is skipped. */
/* Stable stored key-map codes. The retired buffer-effect numbers remain reserved so old settings still decode;
 * only LPF, HPF, FLANGER and PHASER are exposed as active effects. */
enum { PF_R8, PF_R16, PF_R32, PF_REV, PF_LPF, PF_HPF, PF_TAPE, PF_FRZ, PF_OUP, PF_ODN, PF_FLG, PF_PHS,
       PF_RTHR, PF_ETHR,                      /* 1.5.1: REV THROW, ECHO THROW */
       PF_M1, PF_N = PF_M1 + NTRK };
#define PF_NFX PF_M1                          /* the effects a white key can hold */
#define PF_KEYS 16u                           /* the white keys F3 .. G5 */
#define PF_BIT(e) (1u << (e))
#define PF_MUTE (((1u << NTRK) - 1u) << PF_M1)
#define PF_MOD (PF_BIT(PF_FLG) | PF_BIT(PF_PHS))   /* FLANGER, PHASER: their own stages after CRUSH */
#define PF_TOP (63 << 8)                      /* filter cutoff index, Q8 (PF_SVF): the LPF's open end */
#define PF_LOW (14 << 8)                      /* .. the LPF sweep's end, the HPF sweep's (and K1's) top */
#define FL_LEN 356u                           /* FLANGER: its line's frames (8.1 ms: FL_MAX + 2) */
#define FL_MIN 22u                            /* .. the delay's sweep, samples: 0.5 .. 8 ms */
#define FL_MAX 353u
#define FL_FB 16384                           /* .. the feedback, Q15: 0.5 */
#define PH_ST 4u                              /* PHASER: all-pass stages a side (two notches, the classic pedal's) */
#define PH_FB 13107                           /* .. the feedback, Q15: 0.4 */
#define PERF_SLOPE 256                   /* 2.9 ms performance-effect ramp */

/* Default map: LPF, HPF, FLANGER and PHASER; all other white keys are unassigned. */
static const uint8_t PF_DEF[PF_KEYS] = {PF_N, PF_N, PF_N, PF_N, PF_LPF, PF_HPF, PF_N, PF_N, PF_N, PF_N,
                                        PF_FLG, PF_PHS, PF_N, PF_N, PF_N, PF_N};
static volatile uint8_t perf_map[PF_KEYS] = {PF_N, PF_N, PF_N, PF_N, PF_LPF, PF_HPF, PF_N, PF_N, PF_N, PF_N,
                                             PF_FLG, PF_PHS, PF_N, PF_N, PF_N, PF_N};
                                      /* main: white key p's effect (PF_N none), from the settings (ui_layer.c) */
static volatile uint8_t perf_remap;   /* main: perf_map changed (seq.c: a key held takes its new effect) */

static volatile uint32_t perf_mask;   /* main: the FX button's bit while its layer may own keys, 0 = none */
static volatile uint32_t kb_mask;     /* main: the button bits whose hold makes keys a layer's (ui_layer.c), 0 = none */
static volatile uint8_t kb_lock;      /* main: a layer locked open (#83, no button held): 1 keys are the layer's, 2 FX's */
static volatile uint8_t perf_solo;    /* main: tracks soloed in the GLO layer (the others muted as by a black key) */
static volatile uint8_t perf_kill;    /* main: every effect off (the menu, a dialog, UBOOT) */
static volatile int8_t perf_k[4];     /* main: the knob macros, 0 = untouched: FILTER -100..100 (- LPF, + HPF),
                                       * CRUSH 0..100, reserved knob 3, DEPTH 0..100 */
static volatile uint32_t kb_layer;    /* ISR: the keys held that are the layer's, a bit per key */
static volatile uint32_t perf_held;   /* ISR: the effects held (PF_*) */
static volatile uint8_t perf_latch_on;   /* main: MENU > FX LATCH ON (#40): a key with FX toggles its effect */
static volatile uint32_t perf_latched;   /* ISR: the effects latched (FX LATCH; main clears it: OCT-, the menu) */
static volatile uint32_t perf_act;    /* ISR: .. running (a 1/16 one from its start on) */


/* the ZDF state-variable filter at cutoff index i (30 Hz * 2^(i / 7), 0..63: up to 15.4 kHz), k = 1:
 * a1 a2 a3 in Q14 (tools: g = tan(pi fc / fs), a1 = 1 / (1 + g (g + k)), a2 = g a1, a3 = g a2) */
static const int16_t PF_SVF[64][3] = {
    {16349, 35, 0}, {16345, 39, 0}, {16341, 43, 0}, {16337, 47, 0}, {16332, 52, 0}, {16327, 57, 0}, {16321, 63, 0},
    {16314, 70, 0}, {16307, 77, 0}, {16299, 85, 0}, {16290, 94, 1}, {16280, 103, 1}, {16269, 114, 1},
    {16257, 126, 1}, {16244, 139, 1}, {16229, 153, 1}, {16213, 169, 2}, {16196, 186, 2}, {16176, 205, 3},
    {16154, 227, 3}, {16130, 250, 4}, {16104, 275, 5}, {16075, 303, 6}, {16043, 334, 7}, {16007, 368, 8},
    {15968, 406, 10}, {15925, 447, 13}, {15877, 492, 15}, {15824, 541, 19}, {15766, 596, 22}, {15702, 655, 27},
    {15631, 720, 33}, {15553, 791, 40}, {15467, 869, 49}, {15372, 953, 59}, {15267, 1046, 72}, {15151, 1146, 87},
    {15024, 1255, 105}, {14883, 1374, 127}, {14729, 1502, 153}, {14559, 1640, 185}, {14372, 1790, 223},
    {14166, 1950, 268}, {13940, 2121, 323}, {13692, 2304, 388}, {13420, 2499, 465}, {13122, 2704, 557},
    {12797, 2921, 667}, {12441, 3147, 796}, {12053, 3382, 949}, {11631, 3624, 1129}, {11173, 3870, 1341},
    {10677, 4119, 1589}, {10140, 4365, 1879}, {9562, 4605, 2218}, {8940, 4832, 2612}, {8274, 5040, 3070},
    {7563, 5219, 3602}, {6807, 5359, 4219}, {6006, 5444, 4934}, {5163, 5456, 5766}, {4282, 5369, 6733},
    {3372, 5149, 7863}, {2449, 4745, 9190},
};

static struct {
    uint32_t ph, P;                    /* samples since transport start; quarter-note subdivision */
    uint32_t act, act0;                /* effects running this block */
    uint8_t sync, mute;                /* sync: reset phase on next block; mute: tracks to ramp */
    /* the filters, CRUSH and mutes */
    int32_t lc, hc, la, ha;            /* cutoffs (Q8 index) and shares (Q15) of LPF and HPF */
    int32_t lz[4], hz[4];              /* their states: L ic1 ic2, R ic1 ic2 */
    int16_t lk[3], hk[3];              /* their coefficients this block */
    uint32_t lt, ht;                   /* samples the LPF / HPF key has been held */
    int32_t cw, cc, chl, chr;          /* CRUSH share, amount, held sample */
    uint32_t cn;
    int32_t mg[NTRK];                  /* mute gains, Q15 (32768 = open) */
    /* FLANGER, PHASER */
    int32_t fw, pw;                    /* their shares, Q15 */
    uint32_t fwp, fn;                  /* FLANGER: the frame written next; frames written since it started */
    int32_t px[2][PH_ST], py[2][PH_ST], pfb[2];   /* PHASER: each stage's last input and output, L and R; the fed back */
} pf = {.lc = PF_TOP, .mg = {32768, 32768, 32768, 32768}};

static int16_t fl_buf[FL_LEN][2];      /* FLANGER's line: L R, at half the level (headroom) */

/* the key map in the settings (ui_layer.c: favorites.factory[15][14..23]): white key p's code in 5 bits from bit 5p
 * of b: 0 its default (PF_DEF), 1 none, 2 + e effect e (an unknown code, a later firmware's effect: the default) */
static uint32_t perf_map_of(const uint8_t *b, uint32_t p)
{
    uint32_t i = 5u * p, c = (uint32_t)b[i >> 3] >> (i & 7u);
    if ((i & 7u) > 3u)
        c |= (uint32_t)b[(i >> 3) + 1u] << (8u - (i & 7u));
    c &= 31u;
    uint32_t e = c >= 2u ? c - 2u : PF_N;
    return c == 1u ? PF_N : c >= 2u && e < PF_NFX &&
           (e == PF_LPF || e == PF_HPF || e == PF_FLG || e == PF_PHS) ? e : PF_DEF[p];
}
static void perf_map_put(uint8_t *b, uint32_t p, uint32_t e)
{
    uint32_t i = 5u * p, sh = i & 7u, c, two = sh > 3u, v;
    if (e != PF_N && e != PF_LPF && e != PF_HPF && e != PF_FLG && e != PF_PHS)
        e = PF_N;
    c = e == PF_DEF[p] ? 0u : e >= PF_NFX ? 1u : e + 2u;
    v = b[i >> 3] | (two ? (uint32_t)b[(i >> 3) + 1u] << 8 : 0u);
    v = (v & ~(31u << sh)) | c << sh;
    b[i >> 3] = (uint8_t)v;
    if (two)
        b[(i >> 3) + 1u] = (uint8_t)(v >> 8);
}

/* Only these four live processors remain in the compact performance layer. */
static uint32_t perf_avail(void)
{
    return PF_BIT(PF_LPF) | PF_BIT(PF_HPF) | PF_BIT(PF_FLG) | PF_BIT(PF_PHS) | PF_MUTE;
}

/* seq.c keyboard_block: a layer key down / up (e: PF_*, PF_N = no effect) */
static void perf_press(uint32_t e, int down)
{
    if (e >= PF_N)
        return;
    if (perf_latch_on) {                  /* FX LATCH: a press turns it on or off, letting go only ends a hold begun before it */
        if (down) {
            perf_latched ^= PF_BIT(e);
        } else {
            perf_held &= ~PF_BIT(e);      /* (FX LATCH switched on during the hold: the momentary effect ends) */
        }
        return;
    }
    if (down) {
        perf_held |= PF_BIT(e);
    } else {
        perf_held &= ~PF_BIT(e);
    }
}

static void perf_start(void) { pf.ph = 0; pf.sync = 1; }      /* seq_start: a 1/16 starts with the transport */

/* each block, after the keys (seq.c) and before the parts: what runs, the 1/16, the filters, the mutes.
 * Returns 1 when a stage has something to do */
static __attribute__((noinline)) int perf_begin(uint32_t n)
{
    uint32_t held = perf_kill ? 0u : (perf_held | perf_latched | (perf_solo ? (~(uint32_t)perf_solo & 15u) << PF_M1 : 0u)) & perf_avail();
    uint32_t k;
    int32_t m;
    if (!held && !pf.la && !pf.ha && !pf.cw && !pf.fw && !pf.pw && !pf.fn && !pf.mute &&
        !(perf_k[0] | perf_k[1] | perf_k[3])) {
        pf.ph += n;
        pf.sync = 0;
        pf.act = pf.act0 = 0;
        perf_act = 0;
        return 0;
    }
    pf.P = beat_samples() >> 2;
    if (pf.sync) {
        pf.ph = 0;
        pf.sync = 0;
    }
    pf.ph += n;
    pf.act = held;
    pf.act0 = held;
    perf_act = held;
    /* the filters: LPF from open down over a bar while its key is held, KNOB 1 left; HPF up, KNOB 1 right */
    m = perf_k[0];
    {
        uint32_t bar = 16u * pf.P, t;
        int32_t lt = PF_TOP, ht = 0;
        pf.lt = (pf.act & PF_BIT(PF_LPF)) ? pf.lt + n : 0u;
        pf.ht = (pf.act & PF_BIT(PF_HPF)) ? pf.ht + n : 0u;
        if (pf.lt) {
            t = pf.lt < bar ? pf.lt : bar;
            lt = PF_TOP - (int32_t)((uint32_t)(PF_TOP - PF_LOW) / 64u * (t * 64u / bar));
        }
        if (m < 0 && PF_TOP + m * (PF_TOP - PF_LOW) / 100 < lt)
            lt = PF_TOP + m * (PF_TOP - PF_LOW) / 100;
        if (pf.ht) {
            t = pf.ht < bar ? pf.ht : bar;
            ht = (int32_t)((uint32_t)(PF_TOP - PF_LOW) / 64u * (t * 64u / bar));
        }
        if (m > 0 && m * (PF_TOP - PF_LOW) / 100 > ht)
            ht = m * (PF_TOP - PF_LOW) / 100;
        pf.lc += clamp(lt - pf.lc, -192, 192);      /* ~45 ms over the range */
        pf.hc += clamp(ht - pf.hc, -192, 192);
        for (k = 0; k < 3u; k++) {                  /* the coefficients, between two table rows */
            int32_t i = pf.lc >> 8, f = pf.lc & 255, j = pf.hc >> 8, g = pf.hc & 255;
            pf.lk[k] = (int16_t)(PF_SVF[i][k] + (((PF_SVF[i < 63 ? i + 1 : 63][k] - PF_SVF[i][k]) * f) >> 8));
            pf.hk[k] = (int16_t)(PF_SVF[j][k] + (((PF_SVF[j < 63 ? j + 1 : 63][k] - PF_SVF[j][k]) * g) >> 8));
        }
    }
    pf.mute = 0;
    for (k = 0; k < NTRK; k++)
        if (((held >> (PF_M1 + k)) & 1u) || pf.mg[k] != 32768)
            pf.mute |= (uint8_t)(1u << k);
    return 1;
}

/* a track muted by its black key: its signal ramps to 0 and back (fx.c mix_part, after the track's insert) */
static __attribute__((noinline)) void perf_mute(uint32_t k, int32_t *b, uint32_t n)
{
    uint32_t i;
    int32_t g = pf.mg[k], t = (pf.act >> (PF_M1 + k)) & 1u ? 0 : 32768;
    for (i = 0; i < n; i++) {
        g += clamp(t - g, -PERF_SLOPE, PERF_SLOPE);
        b[i] = mulq16(b[i], (uint32_t)g << 1);
    }
    pf.mg[k] = g;
}
/* perf_mute with SPREAD's side signal sd (fx.c mix_spread): the same ramp on both */
static __attribute__((noinline)) void perf_mute_sd(uint32_t k, int32_t *b, int32_t *sd, uint32_t n)
{
    uint32_t i;
    int32_t g = pf.mg[k], t = (pf.act >> (PF_M1 + k)) & 1u ? 0 : 32768;
    for (i = 0; i < n; i++) {
        g += clamp(t - g, -PERF_SLOPE, PERF_SLOPE);
        b[i] = mulq16(b[i], (uint32_t)g << 1);
        sd[i] = mulq16(sd[i], (uint32_t)g << 1);
    }
    pf.mg[k] = g;
}

/* x towards y by w (Q15, 32768 = y) */
static inline int32_t pf_mix(int32_t x, int32_t y, int32_t w)
{
    return w == 32768 ? y : x + mulq16(y - x, (uint32_t)w << 1);
}

/* one channel of a state-variable filter (k = 1): x in Q15 >> 2 */
static inline int32_t pf_svf(int32_t x, int32_t *z, const int16_t *c, int hp)
{
    int32_t v3 = x - z[1], v1 = (c[0] * z[0] + c[1] * v3) >> 14, v2 = z[1] + ((c[1] * z[0] + c[2] * v3) >> 14);
    z[0] = 2 * v1 - z[0];
    z[1] = 2 * v2 - z[1];
    return hp ? x - v1 - v2 : v2;
}

/* No buffer-based harmonizer remains; KNOB 4 always controls modulation depth. */
static int perf_harm_on(void) { return 0; }

/* FLANGER / PHASER: the sweep's place at this block's first sample, a cycle every `s` 1/16s of the transport's clock
 * (pf.ph: in time with the bars while playing), and its step a sample (*inc) */
static uint32_t perf_lfo(uint32_t s, uint32_t n, uint32_t *inc)
{
    uint32_t per = s * pf.P;
    *inc = 0xFFFFFFFFu / per;
    return ((pf.ph - n) % per) * *inc;
}
/* a triangle of the sweep's place q, 0 .. 65534 (Q16) */
static inline uint32_t pf_tri(uint32_t q)
{
    uint32_t t = q >> 16;
    return t < 32768u ? t << 1 : (65535u - t) << 1;
}
/* the share a FLANGER / PHASER fades to: KNOB 4 DEPTH */
static int32_t perf_mod_depth(void) { return 32768 - perf_k[3] * 327; }

/* FLANGER on one side c: x in, the line read at the sweep's place q (see the top) */
static inline int32_t fl_side(uint32_t c, int32_t x, uint32_t q)
{
    uint32_t t = pf_tri(q), d = (FL_MIN << 16) + (FL_MAX - FL_MIN) * ((t * t) >> 16);   /* the delay, Q16 samples */
    int32_t r0 = (int32_t)pf.fwp - (int32_t)(d >> 16), r1, a, v, fr = (int32_t)((d >> 1) & 0x7FFFu);
    if (r0 < 0)
        r0 += (int32_t)FL_LEN;
    r1 = r0 ? r0 - 1 : (int32_t)FL_LEN - 1;
    a = fl_buf[r0][c];
    v = a + (((fl_buf[r1][c] - a) * fr) >> 15);
    fl_buf[pf.fwp][c] = (int16_t)clamp((x >> 1) + softclip(mulq15(v, FL_FB)), -32767, 32767);
    return pf_mix(x, mulq16((x >> 1) + v, 55706u), pf.fw);   /* (x + delayed) / 2 * 0.85 (v: stored at half) */
}
/* after CRUSH, while held or fading: FLANGER (noinline, its own loop: the audio ISR's code stays as it was) */
static __attribute__((noinline)) void perf_flanger(int32_t *bl, int32_t *br, uint32_t n)
{
    uint32_t i, c, inc, q = perf_lfo(16u, n, &inc);
    int32_t tw = pf.act & PF_BIT(PF_FLG) ? perf_mod_depth() : 0, *const b[2] = {bl, br};
    if (!pf.fw && !(pf.act & PF_BIT(PF_FLG))) {         /* let go and faded: off, the line empty next time */
        pf.fn = 0;
        return;
    }
    if (!pf.fn)                                         /* (starting: the line empty) */
        memset(fl_buf, 0, sizeof fl_buf);
    for (i = 0; i < n; i++, q += inc) {
        pf.fw += clamp((pf.fn > FL_MAX + 1u ? tw : 0) - pf.fw, -PERF_SLOPE, PERF_SLOPE);   /* (heard once it holds 8 ms) */
        for (c = 0; c < 2u; c++)                        /* (one call: inlined; the right a quarter of the sweep behind) */
            b[c][i] = fl_side(c, b[c][i], q - (c << 30));
        if (++pf.fwp >= FL_LEN)
            pf.fwp = 0;
        if (pf.fn <= FL_MAX + 1u)
            pf.fn++;
    }
}

/* PHASER: the stages' coefficient a (Q14) for a break of 150 Hz * 2^(5 i / 32): a = (g - 1) / (g + 1), g = tan(pi f / fs) */
static const int16_t PH_A[33] = {
    -16038, -15998, -15955, -15906, -15853, -15793, -15727, -15653, -15572, -15481, -15381, -15270, -15147, -15012,
    -14862, -14696, -14514, -14313, -14092, -13849, -13582, -13290, -12970, -12621, -12240, -11825, -11375, -10886,
    -10356, -9784, -9166, -8500, -7783,
};
/* PHASER: the stages' coefficient at the sweep's place q (Q14) */
static int32_t ph_coef(uint32_t q)
{
    uint32_t t = pf_tri(q), i = t >> 11;
    return PH_A[i] + (((PH_A[i + 1u] - PH_A[i]) * (int32_t)(t & 2047u)) >> 11);
}
/* PHASER on one side c: x in, the stages' coefficient a (rounded: no DC creeping in through the low breaks) */
static inline int32_t ph_side(uint32_t c, int32_t x, int32_t a)
{
    int32_t xs = clamp((x + 2) >> 2, -16383, 16383), u = xs + ((pf.pfb[c] * PH_FB + 16384) >> 15), y = u;
    uint32_t s;
    for (s = 0; s < PH_ST; s++) {                       /* y = a (u - y1) + u1 */
        y = clamp(pf.px[c][s] + ((a * (u - pf.py[c][s]) + 8192) >> 14), -65535, 65535);
        pf.px[c][s] = u;
        pf.py[c][s] = y;
        u = y;
    }
    pf.pfb[c] = clamp(y, -32767, 32767);
    u = xs + y;                                         /* (x + y) / 2 * 0.9, x 4 (>> 2 above): (x + y) * 1.8 */
    return pf_mix(x, u + mulq16(u, 52429u), pf.pw);
}
/* after FLANGER, while held or fading: PHASER (noinline, as FLANGER). The coefficients a block at a time (at its
 * middle: 2.9 ms at most, the sweep moves 1 % in frequency meanwhile) */
static __attribute__((noinline)) void perf_phaser(int32_t *bl, int32_t *br, uint32_t n)
{
    uint32_t i, c, inc, q = perf_lfo(8u, n, &inc) + (n >> 1) * inc;
    int32_t tw = pf.act & PF_BIT(PF_PHS) ? perf_mod_depth() : 0, *const b[2] = {bl, br};
    int32_t a[2] = {ph_coef(q), ph_coef(q - 0x40000000u)};   /* (the right a quarter of the sweep behind) */
    if (!pf.pw) {                                       /* starting: the stages from rest */
        memset(pf.px, 0, sizeof pf.px);
        memset(pf.py, 0, sizeof pf.py);
        pf.pfb[0] = pf.pfb[1] = 0;
    }
    for (i = 0; i < n; i++) {
        pf.pw += clamp(tw - pf.pw, -PERF_SLOPE, PERF_SLOPE);
        for (c = 0; c < 2u; c++)
            b[c][i] = ph_side(c, b[c][i], a[c]);
    }
}

/* after the master level: the buffer effect, LPF, HPF, CRUSH on l / r (stereo, Q15) */
static __attribute__((noinline)) void perf_block(int32_t *bl, int32_t *br, uint32_t n)
{
    uint32_t i, a = pf.act0, sh, hold;
    int32_t c = perf_k[1], lt, ht, ct;
    if (c)
        pf.cc = c;
    ct = c ? 32768 : 0;
    sh = 4u + (uint32_t)pf.cc * 7u / 100u;
    hold = sh - 3u;
    for (i = 0; i < n; i++) {
        int32_t l = bl[i], r = br[i];
        lt = (a & PF_BIT(PF_LPF)) || perf_k[0] < 0 || pf.lc < PF_TOP ? 32768 : 0;
        pf.la += clamp(lt - pf.la, -PERF_SLOPE, PERF_SLOPE);
        if (pf.la) {
            int32_t fl = pf_svf(clamp(l >> 2, -32767, 32767), &pf.lz[0], pf.lk, 0) << 2;
            int32_t fr = pf_svf(clamp(r >> 2, -32767, 32767), &pf.lz[2], pf.lk, 0) << 2;
            l = pf_mix(l, fl, pf.la);
            r = pf_mix(r, fr, pf.la);
        } else {
            pf.lz[0] = pf.lz[1] = pf.lz[2] = pf.lz[3] = 0;
        }
        ht = (a & PF_BIT(PF_HPF)) || perf_k[0] > 0 || pf.hc > 0 ? 32768 : 0;
        pf.ha += clamp(ht - pf.ha, -PERF_SLOPE, PERF_SLOPE);
        if (pf.ha) {
            int32_t fl = pf_svf(clamp(l >> 2, -32767, 32767), &pf.hz[0], pf.hk, 1) << 2;
            int32_t fr = pf_svf(clamp(r >> 2, -32767, 32767), &pf.hz[2], pf.hk, 1) << 2;
            l = pf_mix(l, fl, pf.ha);
            r = pf_mix(r, fr, pf.ha);
        } else {
            pf.hz[0] = pf.hz[1] = pf.hz[2] = pf.hz[3] = 0;
        }
        {   /* CRUSH: fewer bits, a held sample (KNOB 2) */
            pf.cw += clamp(ct - pf.cw, -PERF_SLOPE, PERF_SLOPE);
            if (pf.cw) {
                if (++pf.cn >= hold) {
                    pf.cn = 0;
                    pf.chl = ((l >> sh) << sh) + (1 << (sh - 1u));
                    pf.chr = ((r >> sh) << sh) + (1 << (sh - 1u));
                }
                l = pf_mix(l, pf.chl, pf.cw);
                r = pf_mix(r, pf.chr, pf.cw);
            }
        }
        bl[i] = l;
        br[i] = r;
    }
    if ((pf.act & PF_BIT(PF_FLG)) || pf.fw || pf.fn)
        perf_flanger(bl, br, n);
    if ((pf.act & PF_BIT(PF_PHS)) || pf.pw)
        perf_phaser(bl, br, n);

}
