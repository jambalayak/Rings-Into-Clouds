/* SPDX-License-Identifier: GPL-3.0-only
 * Host tests for the one RINGS exciter / modal-resonator engine.
 */
#include "hostsim.c"

static int rings_state_bounded(const voice_t *v)
{
    uint32_t i;
    for (i = 0; i < 8u; i++)
        if (v->s[i] < -32768 || v->s[i] > 32767)
            return 0;
    return 1;
}

static uint64_t rings_energy(const int32_t *out, uint32_t n)
{
    uint32_t i;
    uint64_t e = 0;
    for (i = 0; i < n; i++) {
        int64_t x = out[i];
        e += (uint64_t)(x * x);
    }
    return e;
}

int main(void)
{
    track_t *t;
    voice_t a, b;
    vmod_t m;
    int32_t oa[CTL], ob[CTL];
    uint32_t i, p, bad = 0;
    int deterministic, alive, bounded = 1;

    ui_power_on();
    t = &trk[0];
    t->p[P_MUTE] = 0;
    for (i = 0; i < 8u; i++)
        t->p[P_E0 + i] = ENG_RINGS.edit[i].def;
    memset(&m, 0, sizeof m);
    m.inc = 0x01000000u;                       /* a stable low-mid pitch */
    m.amp0 = m.amp1 = 32767;
    m.shape = 64 << 8;
    m.cutoff = 64 << 8;

    memset(&a, 0, sizeof a);
    a.note = 60;
    a.age = 17;
    b = a;
    memset(oa, 0, sizeof oa);
    memset(ob, 0, sizeof ob);
    ENG_RINGS.note_on(t, &a);
    ENG_RINGS.note_on(t, &b);
    ENG_RINGS.render(t, &a, oa, CTL, &m);
    ENG_RINGS.render(t, &b, ob, CTL, &m);
    deterministic = !memcmp(oa, ob, sizeof oa) && !memcmp(a.s, b.s, sizeof a.s);
    alive = rings_energy(oa, CTL) != 0;
    bounded &= rings_state_bounded(&a) && rings_state_bounded(&b);
    bad += check("RINGS: deterministic pluck exciter produces a non-silent modal body", deterministic && alive);
    bad += check("RINGS: all eight per-voice state words remain bounded", bounded);

    /* Exercise every control at both ends while the resonator runs for 512 blocks. */
    for (p = 0; p < 2u; p++) {
        for (i = 0; i < 8u; i++)
            t->p[P_E0 + i] = p ? 127 : 0;
        memset(&a, 0, sizeof a);
        a.note = (uint8_t)(36u + p * 48u);
        a.age = 31u + p;
        ENG_RINGS.note_on(t, &a);
        for (i = 0; i < 512u; i++) {
            memset(oa, 0, sizeof oa);
            ENG_RINGS.render(t, &a, oa, CTL, &m);
            bounded &= rings_state_bounded(&a);
        }
    }
    bad += check("RINGS: minimum and maximum parameter sets remain stable over 512 audio blocks", bounded);

    /* Brightness / position / structure must alter the resonant response, not create another engine. */
    for (i = 0; i < 8u; i++)
        t->p[P_E0 + i] = ENG_RINGS.edit[i].def;
    memset(&a, 0, sizeof a);
    a.note = 60; a.age = 99;
    ENG_RINGS.note_on(t, &a);
    memset(oa, 0, sizeof oa);
    ENG_RINGS.render(t, &a, oa, CTL, &m);
    for (i = 0; i < 8u; i++)
        t->p[P_E0 + i] = ENG_RINGS.edit[i].def;
    t->p[P_E1] = 127; t->p[P_E2] = 0; t->p[P_E4] = 127;
    memset(&b, 0, sizeof b);
    b.note = 60; b.age = 99;
    ENG_RINGS.note_on(t, &b);
    memset(ob, 0, sizeof ob);
    ENG_RINGS.render(t, &b, ob, CTL, &m);
    bad += check("RINGS: resonator controls produce a distinct response within the same engine",
                 memcmp(oa, ob, sizeof oa) != 0);
    return bad ? 1 : 0;
}
