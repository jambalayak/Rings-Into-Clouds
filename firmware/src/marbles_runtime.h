/* SPDX-License-Identifier: GPL-3.0-only
 * RINGS INTO CLOUDS — bounded Marbles-inspired per-track random sequencer.
 *
 * Original state machine built on marbles_gen.h; no Mutable Instruments source
 * is included. All work is fixed-size and bounded for audio-thread use.
 */
#ifndef RIC_MARBLES_RUNTIME_H
#define RIC_MARBLES_RUNTIME_H

#include <stdint.h>
#include "marbles_gen.h"

#define MARBLES_HISTORY 8u

typedef struct {
    marbles_rng_t rng;
    uint8_t history[MARBLES_HISTORY];
    uint8_t history_count;
    uint8_t history_pos;
    uint8_t last_note;
    uint8_t has_note;
    int16_t x;
    int16_t y;
} marbles_runtime_t;

typedef struct {
    uint8_t trigger;
    uint8_t note;
    int16_t x;
    int16_t y;
} marbles_step_t;

static inline void marbles_runtime_seed(marbles_runtime_t *s, uint32_t seed)
{
    uint32_t i;
    marbles_rng_seed(&s->rng, seed);
    for (i = 0; i < MARBLES_HISTORY; i++)
        s->history[i] = 60u;
    s->history_count = 0u;
    s->history_pos = 0u;
    s->last_note = 60u;
    s->has_note = 0u;
    s->x = 0;
    s->y = 0;
}

static inline uint8_t marbles_runtime_history_at(const marbles_runtime_t *s, uint32_t index)
{
    uint32_t oldest = (s->history_pos + MARBLES_HISTORY - s->history_count) % MARBLES_HISTORY;
    return s->history[(oldest + index) % MARBLES_HISTORY];
}

static inline marbles_step_t marbles_runtime_step(marbles_runtime_t *s,
                                                   uint32_t density,
                                                   uint32_t spread,
                                                   uint32_t deja_vu,
                                                   uint32_t freeze,
                                                   uint32_t root,
                                                   uint16_t scale,
                                                   int32_t transpose)
{
    marbles_step_t out;
    uint32_t i;
    if (!freeze || !s->has_note) {
        int32_t degree;
        s->x = (int16_t)(marbles_rng_next(&s->rng) >> 16);
        s->y = (int16_t)(marbles_rng_next(&s->rng) >> 16);
        if (s->history_count && marbles_chance(&s->rng, deja_vu)) {
            i = marbles_rng_bounded(&s->rng, s->history_count);
            s->last_note = marbles_runtime_history_at(s, i);
        } else {
            degree = marbles_degree(&s->rng, 0, spread);
            i = marbles_quantize_note(degree, root, scale);
            i = (uint32_t)clamp(i + transpose, 0, 127);
            s->last_note = (uint8_t)i;
            s->history[s->history_pos] = s->last_note;
            s->history_pos = (uint8_t)((s->history_pos + 1u) % MARBLES_HISTORY);
            if (s->history_count < MARBLES_HISTORY)
                s->history_count++;
        }
        s->has_note = 1u;
    }
    out.trigger = (uint8_t)marbles_chance(&s->rng, density);
    out.note = s->last_note;
    out.x = s->x;
    out.y = s->y;
    return out;
}

#endif
