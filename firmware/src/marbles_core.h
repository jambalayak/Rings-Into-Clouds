/* SPDX-License-Identifier: GPL-3.0-only
 * Copyright (C) 2026 Leo Kuroshita (@kurogedelic), Hügelton Instruments */
/* Host-testable primitives for the Marbles-inspired sequencer.
 * No audio globals, allocation, floating point, or hardware dependencies. */
#ifndef RINGS_INTO_CLOUDS_MARBLES_CORE_H
#define RINGS_INTO_CLOUDS_MARBLES_CORE_H

#include <stdint.h>

/* xorshift32: each track owns its own state; never consume the firmware's shared rng(). */
static inline uint32_t marbles_rng_next(uint32_t *state)
{
    uint32_t x = *state;
    if (!x)
        x = 0x6D2B79F5u; /* zero is the xorshift absorbing state */
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

/* Unbiased bounded draw. A zero bound is defined as zero, avoiding division by zero. */
static inline uint32_t marbles_rng_bounded(uint32_t *state, uint32_t bound)
{
    uint32_t x, threshold;
    if (!bound)
        return 0;
    threshold = (uint32_t)(-bound) % bound;
    do {
        x = marbles_rng_next(state);
    } while (x < threshold);
    return x % bound;
}

/* Probability in percent. Endpoints consume no random number, which keeps deterministic
 * streams stable when a control is parked at 0 or 100. */
static inline int marbles_probability(uint32_t *state, uint32_t percent)
{
    if (!percent)
        return 0;
    if (percent >= 100u)
        return 1;
    return marbles_rng_bounded(state, 100u) < percent;
}

/* Snap down to a scale mask, matching the firmware keyboard/sequencer convention.
 * Notes are clamped to MIDI range. If no allowed pitch exists below MIDI note 0,
 * scan upward to the first allowed pitch instead. */
static inline int32_t marbles_scale_snap(uint16_t mask, int32_t root, int32_t note)
{
    int32_t pc, i;
    if (!mask)
        return note < 0 ? 0 : note > 127 ? 127 : note;
    if (note < 0) note = 0;
    if (note > 127) note = 127;
    root %= 12;
    if (root < 0) root += 12;
    for (i = 0; i < 12; i++) {
        pc = (note - root) % 12;
        if (pc < 0) pc += 12;
        if ((mask >> pc) & 1u)
            return note;
        if (note > 0)
            note--;
        else
            break;
    }
    for (i = 0; i < 12 && note < 127; i++) {
        note++;
        pc = (note - root) % 12;
        if (pc < 0) pc += 12;
        if ((mask >> pc) & 1u)
            return note;
    }
    return note;
}

#endif
