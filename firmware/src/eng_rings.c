/* SPDX-License-Identifier: GPL-3.0-only
 * RINGS INTO CLOUDS — one original modal resonator engine.
 *
 * This is an original fixed-point exciter / resonant-body implementation informed by the
 * general architecture of Mutable Instruments Rings. It is not a port of Rings source and
 * contains no Mutable Instruments code or assets. One engine, one continuous control set.
 */
static int32_t rings_sat16(int64_t x)
{
    return x > 32767 ? 32767 : x < -32768 ? -32768 : (int32_t)x;
}

static int32_t rings_mode(int32_t x, int32_t *y1, int32_t *y2,
                          int32_t a1, int32_t a2, int32_t gain)
{
    int64_t acc = (int64_t)a1 * *y1 + (int64_t)a2 * *y2 + (int64_t)gain * x;
    int32_t y = rings_sat16(acc >> 15);
    *y2 = *y1;
    *y1 = y;
    return y;
}

static void rings_note_on(struct track *t, voice_t *v)
{
    uint32_t i;
    (void)t;
    for (i = 0; i < 8u; i++)
        v->s[i] = 0;
    v->ph[0] = v->age ^ ((uint32_t)v->note * 0x9E3779B9u) ^ 0xA511E9B3u;
    if (!v->ph[0]) v->ph[0] = 0x6D2B79F5u;
    v->ph[1] = 1u;                                  /* one pluck impulse at the start */
    v->ph[2] = 0u;
}

static void rings_render(struct track *t, voice_t *v, int32_t *out, uint32_t n, const vmod_t *m)
{
    int32_t exc = clamp(t->p[P_E0], 0, 127);
    int32_t structure = clamp(t->p[P_E1], 0, 127);
    int32_t bright = clamp(t->p[P_E2] + ((m->shape >> 8) - 64) / 2, 0, 127);
    int32_t damp = clamp(t->p[P_E3], 0, 127);
    int32_t pos = clamp(t->p[P_E4], 0, 127);
    int32_t body = clamp(t->p[P_E5], 0, 127);
    int32_t tone = clamp(t->p[P_E6] + ((m->cutoff >> 8) - 64) / 2, 0, 127);
    int32_t air = clamp(t->p[P_E7], 0, 127);
    int32_t r = 32760 - damp * 2;
    int32_t r2 = (int32_t)(((int64_t)r * r) >> 15);
    int32_t a2 = -r2;
    uint32_t ratio2 = 512u + (uint32_t)(structure * 128 / 127);
    uint32_t ratio3 = 768u + (uint32_t)(structure * 256 / 127) + (uint32_t)(body * 64 / 127);
    uint32_t inc1 = m->inc, inc2, inc3, idx1, idx2, idx3;
    int32_t c1, c2, c3, a11, a12, a13;
    int32_t w2 = bright * 257 * (127 - pos) / 127;
    int32_t w3 = bright * 257 * body * pos / (127 * 127);
    int32_t noise_gain = clamp(exc * 258 + air * 64, 0, 32767);
    int32_t impulse_gain = (127 - exc) * 258;
    int32_t tone_k = clamp(512 + tone * 256, 512, 32767);
    int32_t amp = m->amp0;
    int32_t amp_step = n ? (m->amp1 - m->amp0) / (int32_t)n : 0;
    uint32_t i;

    inc2 = (uint32_t)(((uint64_t)inc1 * ratio2) >> 8);
    inc3 = (uint32_t)(((uint64_t)inc1 * ratio3) >> 8);
    if (inc1 > 0x7FFFFFFFu) inc1 = 0x7FFFFFFFu;
    if (inc2 > 0x7FFFFFFFu) inc2 = 0x7FFFFFFFu;
    if (inc3 > 0x7FFFFFFFu) inc3 = 0x7FFFFFFFu;
    idx1 = (inc1 >> 22) & 1023u;
    idx2 = (inc2 >> 22) & 1023u;
    idx3 = (inc3 >> 22) & 1023u;
    c1 = SINE[(idx1 + 256u) & 1023u];
    c2 = SINE[(idx2 + 256u) & 1023u];
    c3 = SINE[(idx3 + 256u) & 1023u];
    a11 = (int32_t)(((int64_t)(2 * r) * c1) >> 15);
    a12 = (int32_t)(((int64_t)(2 * r) * c2) >> 15);
    a13 = (int32_t)(((int64_t)(2 * r) * c3) >> 15);

    for (i = 0; i < n; i++) {
        uint32_t z = v->ph[0];
        int32_t noise, x, y1, y2, y3, sum, filtered, hp;
        z ^= z << 13;
        z ^= z >> 17;
        z ^= z << 5;
        v->ph[0] = z ? z : 0x6D2B79F5u;
        noise = (int16_t)(z >> 16);
        if (v->ph[1]) {
            x = impulse_gain;
            v->ph[1] = 0;
        } else {
            x = (int32_t)(((int64_t)noise * noise_gain) >> 15);
        }
        y1 = rings_mode(x, &v->s[0], &v->s[1], a11, a2, 24576);
        y2 = rings_mode(x, &v->s[2], &v->s[3], a12, a2, 24576);
        y3 = rings_mode(x, &v->s[4], &v->s[5], a13, a2, 24576);
        sum = rings_sat16((int64_t)y1 + (((int64_t)y2 * w2) >> 15) + (((int64_t)y3 * w3) >> 15));
        v->s[6] += (int32_t)(((int64_t)(sum - v->s[6]) * tone_k) >> 15);
        filtered = v->s[6];
        hp = rings_sat16((int64_t)filtered - v->s[7] + (((int64_t)v->s[7] * 32604) >> 15));
        v->s[7] = filtered;
        out[i] += (int32_t)(((int64_t)hp * amp) >> 15);
        amp += amp_step;
    }
}

static const preset_t RINGS_PRESETS[] = {
    {"PLUCK", {0, 18, 96, 58, 24, 64, 112, 8}, {0, 24, 0, 58}, 0, 0, FX(0, 0, 0, 0), PAT(3)},
    {"BELL",  {0, 92, 120, 38, 96, 96, 120, 16}, {0, 18, 0, 72}, 0, 0, FX(0, 18, 12, 28), PAT(7)},
    {"BOW",   {92, 22, 76, 82, 62, 70, 92, 24}, {12, 38, 92, 72}, 0, 0, FX(0, 8, 18, 34), PAT(5)},
    {"WOOD",  {12, 8, 56, 82, 18, 32, 72, 4}, {0, 32, 0, 64}, 0, 0, FX(0, 0, 8, 12), PAT(2)},
    {"GLASS", {0, 110, 127, 24, 104, 112, 127, 20}, {0, 12, 0, 88}, 0, 0, FX(0, 12, 20, 48), PAT(7)},
    {"STRING",{76, 12, 82, 96, 48, 56, 84, 18}, {16, 42, 88, 76}, 0, 0, FX(0, 0, 16, 30), PAT(5)},
    {"DRONE", {108, 64, 68, 112, 64, 96, 58, 42}, {40, 64, 100, 100}, 0, 0, FX(0, 0, 24, 52), PAT(13)},
    {"METAL", {4, 127, 116, 32, 84, 127, 104, 32}, {0, 16, 0, 92}, 0, 0, FX(0, 16, 20, 42), PAT(7)},
};

static const engine_t ENG_RINGS = {
    .name = "RINGS",
    .page_title = {"EXCITER", "RESONATOR"},
    .edit = {
        {"EXC", F_PCT, 0, 127, 0, 0, 0},
        {"STR", F_PCT, 0, 127, 18, 0, 0},
        {"BRT", F_PCT, 0, 127, 96, 0, 0},
        {"DMP", F_PCT, 0, 127, 58, 0, 0},
        {"POS", F_PCT, 0, 127, 24, 0, 0},
        {"BODY", F_PCT, 0, 127, 64, 0, 0},
        {"TONE", F_PCT, 0, 127, 112, 0, 0},
        {"AIR", F_PCT, 0, 127, 8, 0, 0},
    },
    .presets = RINGS_PRESETS,
    .npresets = sizeof RINGS_PRESETS / sizeof RINGS_PRESETS[0],
    .knob = {P_E0, P_E1, P_E2, P_E3},
    .poly = 0,
    .note_on = rings_note_on,
    .render = rings_render,
};
