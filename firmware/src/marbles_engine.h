/* SPDX-License-Identifier: GPL-3.0-only
 * RINGS INTO CLOUDS: lightweight Marbles-style clock / random gate generator.
 * Original control-rate generator; not a port of Mutable Instruments DSP. */
#ifndef RIC_MARBLES_ENGINE_H
#define RIC_MARBLES_ENGINE_H
#include <stdint.h>
#include "marbles_control.h"
#define MARBLES_SEQUENCE_MAX 32u

typedef struct {
    uint32_t rng;
    uint8_t step, memory_count;
    uint8_t memory_note[MARBLES_SEQUENCE_MAX], memory_gate[MARBLES_SEQUENCE_MAX];
} marbles_engine_t;
typedef struct {
    uint32_t interval_samples;
    uint8_t note, gate, pulse, step;
} marbles_event_t;

static inline uint32_t marbles_random(marbles_engine_t *e)
{
    uint32_t x = e->rng ? e->rng : 0x6D2B79F5u;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5; e->rng = x;
    return x;
}
static inline uint32_t marbles_random_bounded(marbles_engine_t *e, uint32_t n)
{
    return n ? (uint32_t)(((uint64_t)marbles_random(e) * n) >> 32) : 0u;
}
static inline void marbles_engine_init(marbles_engine_t *e, uint32_t seed)
{
    uint32_t i;
    if (!e) return;
    e->rng = seed ? seed : 0x6D2B79F5u; e->step = 0u; e->memory_count = 0u;
    for (i = 0; i < MARBLES_SEQUENCE_MAX; ++i) { e->memory_note[i] = 60u; e->memory_gate[i] = 0u; }
}
/* One control-rate event. base_samples is the master-clock interval.
 * RATE scales it 1/4x..4x; JITTER is bounded to half an interval.
 * DEJA VU probabilistically replays a complete prior loop; SPREAD / BIAS
 * shape MIDI pitch around 60; t sets the gate probability. */
static inline marbles_event_t marbles_engine_next(marbles_engine_t *e,
                                                   const marbles_control_t *c,
                                                   uint32_t base_samples)
{
    marbles_event_t out = {0u, 60u, 0u, 0u, 0u};
    uint32_t len, rate, interval, jitter, idx, note, spread, bias, r, chance;
    if (!e || !c || !c->enabled || !base_samples) return out;
    len = marbles_control_steps(c);
    if (len > MARBLES_SEQUENCE_MAX) len = MARBLES_SEQUENCE_MAX;
    rate = 16384u + (uint32_t)(((uint64_t)c->value[MARBLES_CLOCK_RATE] * 245760u) / 65535u);
    interval = (uint32_t)(((uint64_t)base_samples * 65536u) / rate);
    if (!interval) interval = 1u;
    jitter = (uint32_t)(((uint64_t)interval * c->value[MARBLES_CLOCK_JITTER]) / 131070u);
    if (jitter) {
        r = marbles_random_bounded(e, jitter * 2u + 1u);
        interval = r < jitter ? interval - r : interval + r - jitter;
    }
    idx = e->step % len; out.step = (uint8_t)idx;
    out.interval_samples = interval; out.pulse = 1u;
    chance = (uint32_t)c->value[MARBLES_RANDOM_DEJA_VU] * 100u / 65535u;
    if (idx < e->memory_count && marbles_random_bounded(e, 100u) < chance) {
        out.note = e->memory_note[idx]; out.gate = e->memory_gate[idx];
    } else {
        spread = (uint32_t)c->value[MARBLES_RANDOM_SPREAD] * 48u / 65535u;
        bias = (uint32_t)c->value[MARBLES_RANDOM_BIAS] * 48u / 65535u;
        note = 36u + bias + marbles_random_bounded(e, spread + 1u);
        if (note > 127u) note = 127u;
        out.note = (uint8_t)note;
        out.gate = marbles_random_bounded(e, 100u) < marbles_control_t_probability(c);
        if (idx >= e->memory_count) e->memory_count = (uint8_t)(idx + 1u);
        e->memory_note[idx] = out.note; e->memory_gate[idx] = out.gate;
    }
    e->step = (uint8_t)((idx + 1u) % len);
    return out;
}
#endif
