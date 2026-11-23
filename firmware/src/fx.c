/* SPDX-License-Identifier: GPL-3.0-only
 * Copyright (C) 2026 Leo Kuroshita (@kurogedelic), Hügelton Instruments */
/* Effects: per-track distortion and insert processing, then stereo mix and master protection. */
/* DIST: low cut -> drive (1x..8x, exponential) -> asymmetric soft clip
 * (a little bias = even harmonics) -> tone low-pass that closes with drive ->
 * make-up gain (straight into tanh over the full band, it would sound like a
 * broken digital fuzz). State per part (track_t dist_*). */
static void track_dist(track_t *t, int32_t *b, uint32_t n)
{
    int32_t d = t->p[P_DIST], i, g, k, mk, bias = 2400, b0;
    if (!d)
        return;                                         /* states kept: switching on does not click */
    g = 4096 + d * d * 2;                                /* Q12: 1x .. ~9x, gentle at first */
    k = 32000 - d * 95;                                  /* tone: transparent at low drive .. ~3 kHz, Q15 */
    mk = 30000 - d * 120;                                /* make-up */
    b0 = softclip(bias);
    for (i = 0; i < (int32_t)n; i++) {
        int32_t x = b[i], y;
        t->dist_hp += (x - t->dist_hp + 64) >> 7;           /* ~55 Hz low cut: keep the bass out of the clipper */
        x = clamp(x - t->dist_hp, -230000, 230000);         /* (x >> 2) * g fits 32 bits; the clip is flat out there */
        y = softclip((((x >> 2) * g) >> 10) + bias) - b0;   /* >> 2 first: no overflow for loud poly */
        t->dist_lp1 += mulq15(y - t->dist_lp1, k);         /* two poles: tames the fizz */
        t->dist_lp2 += mulq15(t->dist_lp1 - t->dist_lp2, k);
        b[i] = mulq15(t->dist_lp2, mk);
    }
}

/* master: peak limiter in front of the soft clipper. Fast attack (~0.1 ms),
 * ~150 ms release, threshold where tanh is still nearly linear, so chords
 * get quieter instead of crushed. */
#define LIM_T 18000
static int32_t lim_env = LIM_T;
/* MENU > USB LEVEL FIXED (for #42: record over USB with the speaker turned down): the mix goes to master_out at the
 * full MASTER level, USB audio takes that (audio.c uac_tap), and only then does MASTER scale what the DAC gets
 * (usb_fixed_dac). MASTER (0, the default): MASTER before master_out, as always (USB follows the knob) */
static volatile uint8_t fx_usb_fixed;
#define MASTER_FULL 4096                /* main.c: the MASTER knob's top, Q12 */
/* the MASTER pot (ADC 0..1023, smoothed in main.c) to its level, square law: 0 .. 4088 (Q12) */
static inline uint32_t master_of_pot(uint32_t k10) { return (k10 * k10) >> 8; }
static __attribute__((noinline)) void usb_fixed_dac(int32_t *out, uint32_t n)   /* audio ISR, after uac_tap */
{
    uint32_t i;
    int32_t m = (int32_t)song.master_q12;
    for (i = 0; i < 2u * n; i++)
        out[i] = (out[i] * m) >> 12;                /* (|out| <= 32767 after the soft clip: fits) */
}
static volatile uint8_t fx_lowcut;     /* settings: 1 LOWCUT 12 dB/oct ~110 Hz, 2 BASS+ (the small speaker):
                                        * 12 dB/oct ~220 Hz plus the harmonics of the bass (spk_bass) */
static int32_t lc_l1, lc_l2, lc_r1, lc_r2, dc_l, dc_r, dce_l, dce_r;

/* DC blocker (~2 Hz), always on: a leaky integrator of the input (Q6 state) subtracted from it.
 * The >> 12 step keeps its remainder (error feedback, 0..4095) and adds it to the next one, so no
 * part of the step is lost: the state follows the input exactly, down to 0 after the sound stops.
 * (A rounded step of (x - dc) / 4096 would stop moving at |x - dc| < 2048 and leave an offset of up
 * to +-31 at the output after silence.) */
static inline int32_t dc_block(int32_t x, int32_t *dc, int32_t *err)
{
    int32_t e = x * 64 - *dc + *err, d = e >> 12;
    *err = e - d * 4096;
    *dc += d;
    return x - ((*dc + 32) >> 6);
}

static int32_t lce[4];
static inline int32_t lowcut1(int32_t x, int32_t *lc, int32_t *err, uint32_t sh)   /* x minus its one-pole low-pass */
{
    int32_t e = x - *lc + *err, d = e >> sh;
    *err = e - d * (int32_t)(1u << sh);
    *lc += d;
    return x - *lc;
}

/* BASS+: what the speaker cannot play, heard through its harmonics. The bass below ~150 Hz is clipped at its
 * own envelope (a level-following trapezoid: odd harmonics), then band-passed ~220 Hz..1 kHz and added.
 * The low-pass has 4 poles (#42: with 2, the trapezoid rebuilt the 300 .. 600 Hz of the mix itself, late,
 * and cancelled up to 6 dB of it; now under 0.5 dB) */
static int32_t sb_lp1, sb_lp2, sb_lp3, sb_lp4, sb_env, sb_h1, sb_h2, sb_hl;
static inline int32_t spk_bass(int32_t m)
{
    int32_t a, t, u;
    sb_lp1 += ((m - sb_lp1) * 692) >> 15;
    sb_lp2 += ((sb_lp1 - sb_lp2) * 692) >> 15;
    sb_lp3 += ((sb_lp2 - sb_lp3) * 692) >> 15;
    sb_lp4 += ((sb_lp3 - sb_lp4) * 692) >> 15;
    a = sb_lp4 < 0 ? -sb_lp4 : sb_lp4;
    if (a > sb_env)
        sb_env += (a - sb_env) >> 2;
    else if (sb_env > 0)
        sb_env -= (sb_env >> 11) + 1;
    t = clamp(sb_lp4 * 8, -sb_env, sb_env);
    sb_h1 += (t - sb_h1) >> 5;
    u = t - sb_h1;
    sb_h2 += (u - sb_h2) >> 5;
    u -= sb_h2;
    sb_hl += (u - sb_hl) >> 3;
    return sb_hl + (sb_hl >> 1);      /* x1.5 (#180: x3 peaked at 1.5 .. 3.5 x a full-scale kick, the limiter */
}                                     /* pulled the mix down up to 16 dB on each hit and the buzz took over) */

static inline void master_out(int32_t *l, int32_t *r)
{
    int32_t al, ar, a;
    *l = dc_block(*l, &dc_l, &dce_l);
    *r = dc_block(*r, &dc_r, &dce_r);
    if (fx_lowcut) {                  /* two one-pole high-passes, error feedback as dc_block (the */
        uint32_t sh = fx_lowcut == 2u ? 5u : 6u;    /* rounded step stopped at |x - lc| < 32: an offset) */
        int32_t b = fx_lowcut == 2u ? spk_bass((*l + *r) >> 1) : 0;
        *l = lowcut1(*l, &lc_l1, &lce[0], sh);
        *l = lowcut1(*l, &lc_l2, &lce[1], sh) + b;
        *r = lowcut1(*r, &lc_r1, &lce[2], sh);
        *r = lowcut1(*r, &lc_r2, &lce[3], sh) + b;
    }
    al = *l < 0 ? -*l : *l;
    ar = *r < 0 ? -*r : *r;
    a = al > ar ? al : ar;
    if (a > lim_env)
        lim_env += (a - lim_env) >> 2;
    else if (lim_env > LIM_T)
        lim_env -= ((lim_env - LIM_T) >> 12) + 1;
    if (lim_env > LIM_T) {
        int32_t g = (int32_t)(((uint32_t)LIM_T << 15) / (uint32_t)lim_env);   /* < 32768 */
        *l = ((*l >> 4) * g) >> 11;                      /* >> 4 first: |l| may be far above Q15 */
        *r = ((*r >> 4) * g) >> 11;
    }
    *l = softclip(*l);
    *r = softclip(*r);
}

/* length of one division (N_DIV order) in samples at the song tempo */
static const uint8_t DIV_DEN[6] = {1, 2, 4, 8, 3, 6};    /* original IDs stay fixed; slow rates append */
static uint32_t midi_beat_samples;                    /* zero until an external clock has a measured tempo */
static uint32_t beat_samples(void)
{
    uint32_t bpm = song.g[G_BPM] >= 40 ? (uint32_t)song.g[G_BPM] : 120u;   /* (BPM 0 for a moment, #282: no divide by 0) */
    return song.g[G_CLOCK] && midi_beat_samples ? midi_beat_samples : (uint32_t)FS * 60u / bpm;
}
static uint32_t div_samples(uint32_t div)
{
    uint32_t quarter = beat_samples();
    return div < 6u ? quarter / DIV_DEN[div] : div < 10u ? quarter << (div - 5u) : quarter / DIV_DEN[div % 6u];
}

#include "perform.c"                                 /* the FX hold layer's effects (the master) */
#include "click.c"                                   /* the metronome's click (after the master: audio.c) */

/* INSERT (1.5, Discussions #78 and #177): one effect per track, after DIST, with a dry / wet
 * MIX. TYPE (P_ITYPE, N_ITYPE; stored, append-only) and its three values A B C (P_IA .. P_IC, what they mean: params.c
 * ins_desc):
 *   SOFT HARD FOLD FUZZ  DRIVE (1x .. ~13x, squared), TONE (two one-pole low-passes at F_CUTOFF), LEVEL (F_DB, as the
 *                        track's LEVEL: 112 is 0 dB). A slow low cut in front (~27 Hz), a DC blocker after (FUZZ is
 *                        lopsided). SOFT tanh, HARD a flat clip at a voice's level, FOLD a triangle folder (the wave
 *                        reflected at +-16384: every fold more harmonics), FUZZ a hard top and a soft, halved bottom;
 *   CRUSH                BITS (1 .. 16, of a voice's full scale), RATE (a held sample, 689 Hz .. 44.1 kHz, INS_HOLD:
 *                        aliasing as the old samplers), LPF (two one-pole low-passes at F_CUTOFF after them, #177);
 *   PHASR                RATE (F_LFOHZ), DEPTH (the sweep around ~850 Hz: 0 still .. the whole 150 Hz .. 4.8 kHz),
 *                        FDBK (0 .. 0.7): the FX layer's four all-pass stages (perform.c PH_A), mono, per track;
 *   FLANG CHOR           RATE, DEPTH, FDBK: a 256-sample line per track (5.8 ms); FLANG swept 0.25 .. 5 ms (the FX
 *                        layer's squared triangle), feedback 0 .. 0.85; CHOR a sine around 3.2 ms (+-2.3 ms at DEPTH
 *                        127), feedback 0 .. 0.4. A DC blocker on the swept copy (a clipped loud input is lopsided).
 * The swept ones are the pedals': their wet is (dry + swept) / 2, the notches need both, so MIX 100 % is the whole
 * effect and less a lighter one. MIX (P_IMIX) blends dry and wet linearly; MIX 0 or TYPE OFF: the track bit for bit
 * as before (nothing runs). MIX glides (2.9 ms, INS_SLOPE); a TYPE change fades the old one out, clears the state,
 * fades the new one in; so does a start from MIX 0 (no stale line or filter). With SPREAD (mix_spread) the insert
 * takes the mono sum b, as DIST does; the side passes it by.
 * Order: DIST -> INSERT -> level / pan / sends. State in the pool, per track (ins[], 580 B each); noinline, its own
 * loops: the audio ISR's inlined path gains one test per part (track_t ins_run) */
enum { IT_OFF, IT_SOFT, IT_HARD, IT_FOLD, IT_FUZZ, IT_CRUSH, IT_PHASER, IT_FLANGER, IT_CHORUS, IT_N }; /* IT_CHORUS retired */
#define INS_SLOPE 256                    /* 2.9 ms fade at 44.1 kHz */
#define IL_LEN 256u                     /* FLANG / CHOR: the line, samples (a power of 2: masked) */
static const uint8_t INS_HOLD[16] = {64, 48, 40, 32, 24, 20, 16, 12, 10, 8, 6, 5, 4, 3, 2, 1};   /* CRUSH RATE */
typedef struct {
    int32_t w;                          /* the wet share now, Q15 */
    uint8_t type;                       /* the type running */
    uint8_t cnt;                        /* CRUSH: samples left of the held one */
    uint16_t wp;                        /* FLANG / CHOR: the line's next write */
    uint32_t ph;                        /* the sweep's phase */
    int32_t hp, lp1, lp2, dc, hold;     /* low cut (Q8), the two low-passes, DC blocker (Q8), CRUSH's held sample */
    int32_t px[PH_ST], py[PH_ST], fb;   /* PHASR: each stage's last input and output, the fed back */
    int16_t line[IL_LEN];               /* FLANG / CHOR, at a quarter (headroom) */
} ins_t;
static ins_t ins[NTRK] __attribute__((section(".pool")));

static inline int32_t ins_mixq(int32_t m) { return m >= 127 ? 32768 : m <= 0 ? 0 : m * 258; }   /* MIX -> Q15 */
/* the one-pole low-pass (topology-preserving) coefficient of cutoff index c, Q16: G = g / (1 + g), g = tan(pi fc / FS) */
static int32_t ins_lpk(int32_t c)
{
    uint32_t g = SVF_G[clamp(c, 0, 127)];
    return (int32_t)((g << 16) / (4096u + g));
}
/* the drives' and CRUSH's shape of v (a voice's full scale 32768; v already through DRIVE): the curve the INSERT
 * graph draws too */
static inline int32_t ins_shape(uint32_t ty, int32_t v, uint32_t sh)
{
    switch (ty) {
    case IT_SOFT:
        return softclip(v);
    case IT_HARD:
        return clamp(v, -24000, 24000);
    case IT_FOLD: {
        int32_t u = (int32_t)((uint32_t)(v + 16384) & 0xFFFFu) - 32768;   /* a triangle of period 65536: +-16384 */
        u = 16384 - (u < 0 ? -u : u);
        return u + (u >> 1);                            /* x 1.5 (no divide) */
    }
    case IT_FUZZ:
        return v > 0 ? (v > 20000 ? 20000 : v) : softclip(v) >> 1;
    case IT_CRUSH:                                      /* sh: 16 - BITS; to the nearest step */
        return sh ? ((v + (1 << (sh - 1u))) >> sh) << sh : v;
    default:
        return v;
    }
}
static inline uint32_t ins_bits_sh(int32_t a) { return 15u - (uint32_t)(clamp(a, 0, 127) >> 3); }   /* BITS 1..16 */

/* SOFT .. FUZZ: low cut -> DRIVE -> shape -> TONE -> LEVEL -> DC blocker; CRUSH: held sample -> bits -> LPF */
static __attribute__((noinline)) void ins_drive(ins_t *s, const track_t *t, int32_t *b, uint32_t n, int32_t tw)
{
    uint32_t i, ty = s->type, crush = ty == IT_CRUSH, sh = ins_bits_sh(t->p[P_IA]);
    uint32_t hold = INS_HOLD[clamp(t->p[P_IB], 0, 127) >> 3];
    int32_t a = t->p[P_IA], g = 4096 + a * a * 3;       /* DRIVE, Q12: 1x .. 12.8x, gentle at first */
    int32_t k = ins_lpk(crush ? t->p[P_IC] : t->p[P_IB]), lvl = crush ? 4096 : LEVEL_Q12[t->p[P_IC] & 127];
    for (i = 0; i < n; i++) {
        int32_t x = b[i], y, v;
        s->w += clamp(tw - s->w, -INS_SLOPE, INS_SLOPE);
        if (crush) {
            if (!s->cnt) {
                s->hold = ins_shape(IT_CRUSH, clamp(x, -262144, 262143), sh);
                s->cnt = (uint8_t)hold;
            }
            s->cnt--;
            y = s->hold;
        } else {
            s->hp += ((x << 8) - s->hp) >> 8;            /* ~27 Hz low cut (Q8: no offset left by the rounding) */
            v = clamp(x - (s->hp >> 8), -230000, 230000);
            y = ins_shape(ty, ((v >> 3) * g) >> 9, 0);    /* (>> 3 first: 32 bits) */
        }
        y <<= 4;                                        /* (x16: the low cutoffs' rounding leaves no offset) */
        v = mulq16(y - s->lp1, (uint32_t)k);             /* TONE / LPF: two one-pole low-passes */
        y = v + s->lp1;
        s->lp1 = y + v;
        v = mulq16(y - s->lp2, (uint32_t)k);
        y = v + s->lp2;
        s->lp2 = y + v;
        y = (y + 8) >> 4;
        if (!crush) {
            y = (y * lvl) >> 12;                        /* LEVEL */
            s->dc += ((y << 8) - s->dc) >> 9;           /* DC blocker, ~14 Hz (FUZZ's lopsided halves) */
            y -= s->dc >> 8;
        }
        b[i] = pf_mix(x, y, s->w);
    }
}

/* PHASR, FLANG, CHOR: the sweep at RATE (one LFO per track), DEPTH, FDBK */
static __attribute__((noinline)) void ins_swept(ins_t *s, const track_t *t, int32_t *b, uint32_t n, int32_t tw)
{
    uint32_t i, inc = LFO_INC[clamp(t->p[P_IA], 0, 127)] / CTL, dep = (uint32_t)clamp(t->p[P_IB], 0, 127);
    int32_t c = clamp(t->p[P_IC], 0, 127);
    if (s->type == IT_PHASER) {                         /* the coefficients a block at a time (at its middle) */
        uint32_t tr = pf_tri(s->ph + (n >> 1) * inc), q = 32768u + (uint32_t)(((int32_t)tr - 32768) * (int32_t)dep / 127);
        int32_t a = PH_A[q >> 11] + (((PH_A[(q >> 11) + 1u] - PH_A[q >> 11]) * (int32_t)(q & 2047u)) >> 11);
        int32_t fbk = c * 180;                          /* 0 .. 0.7, Q15 */
        for (i = 0; i < n; i++) {
            int32_t x = b[i], xs = clamp((x + 4) >> 3, -16383, 16383), u = xs + ((s->fb * fbk + 16384) >> 15), y = u;
            uint32_t st;
            s->w += clamp(tw - s->w, -INS_SLOPE, INS_SLOPE);
            for (st = 0; st < PH_ST; st++) {            /* y = a (u - y1) + u1 */
                y = clamp(s->px[st] + ((a * (u - s->py[st]) + 8192) >> 14), -65535, 65535);
                s->px[st] = u;
                s->py[st] = y;
                u = y;
            }
            s->fb = clamp(y, -32767, 32767);
            y <<= 2;                                    /* (y: at an eighth) */
            s->dc += ((y << 8) - s->dc) >> 9;           /* DC blocker, ~14 Hz (a clipped loud input is lopsided) */
            b[i] = pf_mix(x, (x >> 1) + y - (s->dc >> 8), s->w);   /* (dry + all-passed) / 2 */
        }
        s->ph += n * inc;
        return;
    }
    {
        int32_t fbk = c * 219;                       /* FLANGER feedback, 0 .. 0.85 Q15 */
        uint32_t dq = dep * 516u;                       /* DEPTH, Q16 */
        for (i = 0; i < n; i++, s->ph += inc) {
            int32_t x = b[i], r0, r1, v, fr;
            uint32_t d;                                 /* the delay, Q16 samples */
            s->w += clamp(tw - s->w, -INS_SLOPE, INS_SLOPE);
            {
                uint32_t tr = pf_tri(s->ph), sw = (tr * tr) >> 16;
                d = (11u << 16) + 209u * (((sw >> 1) * dq) >> 15);
            }
            r0 = (int32_t)(s->wp - (d >> 16)) & (int32_t)(IL_LEN - 1u);
            r1 = (r0 - 1) & (int32_t)(IL_LEN - 1u);
            fr = (int32_t)((d >> 1) & 0x7FFFu);
            v = s->line[r0] + (((s->line[r1] - s->line[r0]) * fr) >> 15);
            s->line[s->wp] = (int16_t)clamp((x >> 2) + softclip(mulq15(v, fbk)), -32767, 32767);
            s->wp = (uint16_t)((s->wp + 1u) & (IL_LEN - 1u));
            v <<= 1;                                    /* (v: at a quarter) */
            s->dc += ((v << 8) - s->dc) >> 9;           /* DC blocker (the line's clip on a loud lopsided wave) */
            b[i] = pf_mix(x, (x >> 1) + v - (s->dc >> 8), s->w);   /* (dry + delayed) / 2 */
        }
    }
}

/* the INSERT at rest at once (mix_part: TYPE turned OFF while the part was silent, its fade never ran) */
static __attribute__((noinline)) void ins_rest(track_t *t)
{
    memset(&ins[(uint32_t)(t - trk) % NTRK], 0, sizeof(ins_t));
    t->ins_run = 0;
}

/* the track's INSERT on its block b (mix_part, mix_spread): nothing while TYPE is OFF or MIX is 0 and faded */
static __attribute__((noinline)) void track_insert(track_t *t, int32_t *b, uint32_t n)
{
    ins_t *s = &ins[(uint32_t)(t - trk) % NTRK];
    int32_t ty = clamp(t->p[P_ITYPE], 0, IT_N - 1), tw;
    if (ty == IT_CHORUS)
        ty = IT_OFF; /* legacy stored value: chorus is no longer part of the instrument */
    if (s->type != ty && !s->w)                         /* faded out: the new type from rest */
        s->type = (uint8_t)ty;
    tw = s->type == ty && ty ? ins_mixq(t->p[P_IMIX]) : 0;
    if (!s->w) {
        if (!tw) {
            t->ins_run = 0;
            return;                                     /* dry: bit for bit */
        }
        memset(s, 0, sizeof *s);                        /* starting: no stale line or filter */
        s->type = (uint8_t)ty;
    }
    if (s->type >= IT_PHASER)
        ins_swept(s, t, b, n, tw);
    else
        ins_drive(s, t, b, n, tw);
    t->ins_run = s->w != 0;                             /* (mix_part calls again while it fades) */
}

/* One block of the stereo mix. Each core accumulates left/right and uses a private part scratch buffer. */
static void events_block(uint32_t n);                    /* seq.c */
#if FELUCCA_CPU2
typedef struct { int32_t l[CTL], r[CTL], b[CTL]; } mixsum_t;
static mixsum_t mx[2];
#define mix_l (mx[0].l)
#define mix_r (mx[0].r)
#define SM_DECL , mixsum_t *sm
#define SM_ARG(x) , (x)
#define SM(f) (sm->f)
#else
static int32_t part_buf[CTL], mix_l[CTL], mix_r[CTL];
#define SM_DECL
#define SM_ARG(x)
#define SM(f) SM1_##f
#define SM1_l mix_l
#define SM1_r mix_r
#define SM1_b part_buf
#endif

/* SPREAD (#148): a POLY or UNISON part whose SPRD is above 0. Its voices start left and right of PAN in turn (voice.c
 * voice_start; UNISON's detuned voices alternate), at PAN -/+ SPRD / 2 (SPRD 127: hard left and right), with the pan
 * law PAN has (the far side down, the near one as it is). track_render gives every voice (b, as always) and the left
 * ones (spread_buf); here d = left - right, the side signal, so for a pair of pans L = b (gla + glb) / 2 + d (gla - glb)
 * / 2 (R alike): the mono sum is b's, the level of a centre pan less by SPRD / 256 at most. b goes through DIST and the FX layer's mute key as always; d passes DIST by (the spread of a distorted chord is its voices' clean difference)
 * and gets the mute's ramp (perf_mute_sd). The sends
 * take b, mono, as before. SPRD 0, MONO or LEGATO: mix_part's own loop, bit for bit as before. The cost: a block's
 * clear and sum of spread_buf, the side and a wider mix loop, per part; per voice none (it picks its buffer) */
static __attribute__((noinline)) void mix_spread(track_t *t, int32_t *b, uint32_t n SM_DECL)
{
    int32_t *d = SPREAD_BUF(t);
    uint32_t i;
    int32_t lvl = LEVEL_Q12[t->p[P_LEVEL] & 127], pan = t->p[P_PAN], s = (t->p[P_SPRD] + 1) >> 1;
    int32_t pa = clamp(pan - s, -64, 63), pb = clamp(pan + s, -64, 63);
    int32_t gla = 4096 - (pa > 0 ? pa * 64 : 0), gra = 4096 + (pa < 0 ? pa * 64 : 0);
    int32_t glb = 4096 - (pb > 0 ? pb * 64 : 0), grb = 4096 + (pb < 0 ? pb * 64 : 0);
    int32_t glm = (gla + glb) >> 1, grm = (gra + grb) >> 1, gld = (gla - glb) >> 1, grd = (gra - grb) >> 1;
    int32_t pk = t->peak;
    for (i = 0; i < n; i++)
        d[i] = (d[i] << 1) - b[i];                      /* left - right */
    track_dist(t, b, n);
    if (t->p[P_ITYPE] | t->ins_run)
        track_insert(t, b, n);                          /* (the mono sum, as DIST) */
    if ((pf.mute >> (t - trk)) & 1u)
        perf_mute_sd((uint32_t)(t - trk), b, d, n);
    for (i = 0; i < n; i++) {
        int32_t x = ((b[i] >> 2) * lvl) >> 10, a = x < 0 ? -x : x, y = ((d[i] >> 2) * lvl) >> 10;
        if (a > pk)
            pk = a;
        SM(l)[i] += ((x * glm) >> 12) + ((y * gld) >> 12);
        SM(r)[i] += ((x * grm) >> 12) + ((y * grd) >> 12);
    }
    t->peak = pk;
}

/* a part's cost for the second core's split (mix_split, after Jangada's): its voices x its engine's cost per
 * voice (ENG_VCOST: the host's instructions per sample, tests/regress.c CPU at 8 notes held less the idle mix, over the
 * engine's voices), and the DIST, INSERT and sends while it sounds or its tail runs. ENGINES[] order; DIGITAL as FM6
 * when built, nothing when retired. An estimate: it only steers the split, the sound does not depend on it */
#if FELUCCA_CPU2
static uint16_t part_cost[NTRK];                        /* the last block's, per part */
static const uint16_t ENG_VCOST[NENGINES] = {163, FELUCCA_FM4 ? 181 : 0, 162, 67, 70, 174, 144, 143, 189, 309, 113, 134,
                                             181,
#if FELUCCA_SLICE
                                             129,
#endif
#if FELUCCA_ADPCM
                                             168,      /* ADPCM (ORGAN, 1693 instructions / sample at 8 notes) */
#endif
};
#endif

/* one synth part into the dry mix and the sends of sm (mx[0]; mx[1] on the second core); a part with no voice sounding costs
 * the LFO tick and a cleared buffer only (after the DIST tail has run out) */
static void mix_part(track_t *t, uint32_t n SM_DECL)
{
    int32_t *b = SM(b);
    uint32_t i;
#if FELUCCA_CPU2
    uint32_t nr;
#endif
    mod_begin(t);                                       /* the matrix's per-block values into t->p (mod.c) */
    T_SPREAD(t) = t->p[P_SPRD] > 0 && (trk_vmode(t) == V_POLY || trk_vmode(t) == V_UNISON);   /* (SPREAD, mix_spread) */
#if FELUCCA_CPU2
    nr = track_render(t, b, n);
    part_cost[(uint32_t)(t - trk) % NTRK] = (uint16_t)(nr * ENG_VCOST[t->engine % NENGINES] + (nr || t->tail ? 60u : 0u));
    if (nr)
#else
    if (track_render(t, b, n))
#endif
        t->tail = t->p[P_ITYPE] ? 64 : 16;              /* blocks of DIST / INSERT state to run out after the last
                                                         * voice (the INSERT's: 46 ms, a flanger's feedback) */
    else if (!t->tail || !(t->p[P_DIST] | t->p[P_ITYPE]) || !--t->tail) {
        if (t->ins_run && !t->p[P_ITYPE])
            ins_rest(t);                                /* TYPE OFF while silent: no fade-out left for the next note */
        if (MOD(t).on)
            mod_end(t);
        return;
    }
    if (T_SPREAD(t))
        mix_spread(t, b, n SM_ARG(sm));
    else {
        track_dist(t, b, n);
        if (t->p[P_ITYPE] | t->ins_run)
            track_insert(t, b, n);                      /* the INSERT (1.5): off, nothing */
        if ((pf.mute >> (t - trk)) & 1u)
            perf_mute((uint32_t)(t - trk), b, n);       /* perform.c: a black key in the FX layer */
    }
    if (!T_SPREAD(t)) {                                /* (the mix's values read after the calls: none is held over
                                                         * them, no spill in the loop: the ISR's cost as before 1.5) */
        int32_t lvl = LEVEL_Q12[t->p[P_LEVEL] & 127], pan = t->p[P_PAN];
        int32_t gl = 4096 - (pan > 0 ? pan * 64 : 0), gr = 4096 + (pan < 0 ? pan * 64 : 0);
        int32_t pk = t->peak;
        for (i = 0; i < n; i++) {
            int32_t x = ((b[i] >> 2) * lvl) >> 10, a = x < 0 ? -x : x;   /* pre-shift: 8 loud voices */
            if (a > pk)
                pk = a;
            SM(l)[i] += (x * gl) >> 12;
            SM(r)[i] += (x * gr) >> 12;
        }
        t->peak = pk;
    }
    if (MOD(t).on)
        mod_end(t);                                     /* the stored values back */
}

/* the HOME oscilloscope (ui_graph.c graph_scope): every other sample of the left channel. MENU > DISPLAY > SCOPE (1.2,
 * Discussion #165): OUT (0, the default) what goes out, after MASTER (audio.c audio_block, before the click); MIX the
 * mix before MASTER (and before the FX layer, SPEAKER EQ and the limiter), at the level MASTER at its top gives, so its
 * size does not follow the volume. The click is in neither */
#define SCOPE_N 512u
static int16_t scope_buf[SCOPE_N];
static uint32_t scope_w;
static volatile uint8_t scope_mix;
static __attribute__((noinline)) void scope_take_mix(uint32_t n)
{
    uint32_t i;
    for (i = 1; i < n; i += 2u)                         /* (((x >> 2) * MASTER_FULL) >> 10 is x) */
        scope_buf[scope_w++ & (SCOPE_N - 1u)] = (int16_t)clamp(mix_l[i], -32767, 32767);
}

/* the master with the FX layer's effects between its level and master_out (perform.c) */
static __attribute__((noinline)) void perf_master(int32_t *out, uint32_t n)
{
    uint32_t i;
    int32_t mg = fx_usb_fixed ? MASTER_FULL : (int32_t)song.master_q12;   /* (USB LEVEL FIXED: MASTER after) */
    for (i = 0; i < n; i++) {
        mix_l[i] = ((mix_l[i] >> 2) * mg) >> 10;
        mix_r[i] = ((mix_r[i] >> 2) * mg) >> 10;
    }
    perf_block(mix_l, mix_r, n);
    for (i = 0; i < n; i++) {
        int32_t l = mix_l[i], r = mix_r[i];
        master_out(&l, &r);
        out[2u * i] = l;
        out[2u * i + 1u] = r;
    }
}

/* ---- the second core (bsp/chip/fm1_cpu1.h; after Jangada's, github.com/zednaked/jangada, GPL-3.0) renders some of
 * the parts of each block into its own sums (mx[1]) while this core renders the others; then this core adds them in
 * and goes on (the LFOs' blocks, the FX layer, the buses, the master) as with one core. The sums are integers, so the
 * order they add up in changes nothing: the output is bit for bit one core's. A part's render touches its own state
 * only (its track_t with its SPREAD, ENV SYNC and LFO phase, its voices, its matrix: mod.c MOD, its SPREAD buffer,
 * its engine's memory) and what nobody writes meanwhile (song, the tables); what parts share is done before the
 * split (events_block: the notes, voice stealing; the FX layer's perf_begin) or after it (the LFOs' S&H draw from the
 * shared generator, part by part: voice.c track_lfo_end). tests/dualcore_test.c checks it, under ThreadSanitizer too.
 * Without a second core (the host, the browser, MENU > 2ND CORE OFF, one that did not answer or stopped) C1_RUN takes
 * nothing and this core renders them all */
#if FELUCCA_CPU2
#ifndef C1_RUN
#define C1_ON() 0                                       /* a second core is answering */
#define C1_RUN(fn, arg) 0                               /* hand it fn(arg): 1 = taken */
#define C1_WAIT() 0                                     /* wait for it: 0 = done */
#endif
#ifndef C1_SPLIT
#define C1_SPLIT() mix_split()
#endif
static uint32_t c1_blocks;                              /* blocks the second core took parts of (console) */

static void c1_parts(uint32_t arg)                      /* arg: the parts (bit k = part k) | n << 8 */
{
    uint32_t i, n = arg >> 8;
    mixsum_t *sm = &mx[1];
    for (i = 0; i < n; i++)
        sm->l[i] = sm->r[i] = sm->b[i] = 0;
    for (i = 0; i < NPART; i++)
        if (arg >> i & 1u)
            mix_part(&trk[i], n, sm);
}

/* which parts go to the second core: the split of the last block's costs that leaves the busier core the least; none
 * when that saves less than handing them over costs (C1_HAND) */
#define C1_HAND 40u
static uint32_t mix_split(void)
{
    uint32_t m, i, best = 0, all = 0, lo;
    for (i = 0; i < NPART; i++)
        all += part_cost[i];
    lo = all;
    for (m = 1; m < (1u << NPART) - 1u; m++) {
        uint32_t a = 0, w;
        for (i = 0; i < NPART; i++)
            if (m >> i & 1u)
                a += part_cost[i];
        w = (a > all - a ? a : all - a) + C1_HAND;
        if (w < lo) {
            lo = w;
            best = m;
        }
    }
    return best;
}
#endif

static void mix_block(int32_t *out, uint32_t n)
{
    uint32_t i;
    int perf;
    int32_t mg = fx_usb_fixed ? MASTER_FULL : (int32_t)song.master_q12;   /* (USB LEVEL FIXED: MASTER after) */
    for (i = 0; i < n; i++)
        mix_l[i] = mix_r[i] = 0;
    events_block(n);
    perf = perf_begin(n);                               /* the FX hold layer at work (perform.c) */
#if FELUCCA_CPU2
    uint32_t m = C1_ON() ? C1_SPLIT() & ((1u << NPART) - 1u) : 0u;
    if (m && !C1_RUN(c1_parts, m | n << 8))
        m = 0;
    c1_blocks += m != 0;
    for (i = 0; i < NPART; i++)
        if (!(m >> i & 1u))
            mix_part(&trk[i], n, &mx[0]);
    if (m) {
        const mixsum_t *sm = &mx[1];
        if (C1_WAIT())                                  /* it stopped answering (held from now on): its parts here */
            c1_parts(m | n << 8);
        for (i = 0; i < n; i++) {
            mix_l[i] += sm->l[i];
            mix_r[i] += sm->r[i];
        }
    }
    for (i = 0; i < NPART; i++)                         /* the LFOs' blocks, part by part (voice.c) */
        track_lfo_end(&trk[i]);
#else
    for (i = 0; i < NPART; i++)                         /* (one core: as 1.6) */
        mix_part(&trk[i], n);
#endif
    if (scope_mix)
        scope_take_mix(n);
    if (perf) {
        perf_master(out, n);
        return;
    }
    for (i = 0; i < n; i++) {
        int32_t l = ((mix_l[i] >> 2) * mg) >> 10;
        int32_t r = ((mix_r[i] >> 2) * mg) >> 10;
        master_out(&l, &r);
        out[2u * i] = l;
        out[2u * i + 1u] = r;
    }
}
