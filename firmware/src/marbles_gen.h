/* SPDX-License-Identifier: GPL-3.0-only
 * RINGS INTO CLOUDS — bounded Marbles-inspired generator primitives.
 *
 * Original implementation; no Mutable Instruments source is included.
 * Pure integer helpers: safe for host tests and bounded audio-thread use.
 */
#ifndef RIC_MARBLES_GEN_H
#define RIC_MARBLES_GEN_H

#include <stdint.h>

typedef struct {
    uint32_t state;
} marbles_rng_t;

static inline void marbles_rng_seed(marbles_rng_t *r, uint32_t seed)
{
    r->state = seed ? seed : 0x6D2B79F5u;
}

static inline uint32_t marbles_rng_next(marbles_rng_t *r)
{
    uint32_t x = r->state;
    /* xorshift32: non-zero state is maintained by marbles_rng_seed(). */
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    r->state = x ? x : 0x6D2B79F5u;
    return r->state;
}

/* Uniform integer in [0, bound). A zero bound safely returns zero. */
static inline uint32_t marbles_rng_bounded(marbles_rng_t *r, uint32_t bound)
{
    return bound ? (uint32_t)(((uint64_t)marbles_rng_next(r) * bound) >> 32) : 0u;
}

/* Percent test, with endpoints exact: 0 never, 100 always. */
static inline int marbles_chance(marbles_rng_t *r, uint32_t percent)
{
    if (percent == 0u) return 0;
    if (percent >= 100u) return 1;
    return marbles_rng_bounded(r, 100u) < percent;
}

/* A signed, bounded pitch-degree offset. bias is -64..63, spread is 0..127.
 * Returns a scale-degree displacement, not a MIDI note. */
static inline int32_t marbles_degree(marbles_rng_t *r, int32_t bias, uint32_t spread)
{
    int32_t width = (int32_t)(spread > 127u ? 127u : spread);
    int32_t lo = -width / 2;
    int32_t hi = width - (uint32_t)(width / 2);
    int32_t value = lo + (int32_t)marbles_rng_bounded(r, (uint32_t)(hi - lo + 1));
    bias = bias < -64 ? -64 : (bias > 63 ? 63 : bias);
    return value + bias;
}

/* Map a signed scale degree to MIDI note using a 12-bit pitch-class mask.
 * root is 0..11; empty masks fall back to chromatic. Result clamps 0..127. */
static inline uint8_t marbles_quantize_note(int32_t degree, uint32_t root, uint16_t mask)
{
    int32_t octave, index, count = 0, semitone = 0, n;
    uint32_t pc;
    root %= 12u;
    if (!(mask & 0x0FFFu)) mask = 0x0FFFu;
    for (pc = 0; pc < 12u; pc++)
        if (mask & (1u << pc)) count++;
    octave = degree / count;
    index = degree % count;
    if (index < 0) { index += count; octave--; }
    for (pc = 0; pc < 12u; pc++) {
        uint32_t candidate = (root + pc) % 12u;
        if (mask & (1u << candidate)) {
            if (index-- == 0) { semitone = (int32_t)pc; break; }
        }
    }
    n = 60 + octave * 12 + semitone;
    return (uint8_t)(n < 0 ? 0 : (n > 127 ? 127 : n));
}

#endif
