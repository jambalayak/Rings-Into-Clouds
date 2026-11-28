/* SPDX-License-Identifier: GPL-3.0-only
 * RINGS INTO CLOUDS: Marbles control model, independent of the upstream DSP.
 * This is a control/UI boundary, not a Marbles audio generator. */
#ifndef RIC_MARBLES_CONTROL_H
#define RIC_MARBLES_CONTROL_H
#include <stdint.h>

enum {
    MARBLES_CLOCK_RATE, MARBLES_CLOCK_JITTER, MARBLES_CLOCK_LENGTH, MARBLES_CLOCK_STEPS,
    MARBLES_RANDOM_DEJA_VU, MARBLES_RANDOM_SPREAD, MARBLES_RANDOM_BIAS, MARBLES_RANDOM_T,
    MARBLES_PARAM_COUNT
};
enum { MARBLES_BANK_CLOCK, MARBLES_BANK_RANDOM, MARBLES_BANK_COUNT };
#define MARBLES_VALUE_MAX 65535u

typedef struct {
    uint16_t value[MARBLES_PARAM_COUNT];
    uint8_t bank;
    uint8_t enabled;
} marbles_control_t;

/* Neutral starting point: moderate clock, no jitter, full-length sequence,
 * eight steps, no loop lock, centred spread/bias, and t probability off. */
static inline void marbles_control_init(marbles_control_t *m)
{
    static const uint16_t defaults[MARBLES_PARAM_COUNT] = {
        32768u, 0u, 65535u, 21845u, 0u, 32768u, 32768u, 0u
    };
    uint32_t i;
    for (i = 0; i < MARBLES_PARAM_COUNT; ++i) m->value[i] = defaults[i];
    m->bank = MARBLES_BANK_CLOCK;
    m->enabled = 1u;
}
static inline uint8_t marbles_control_param(uint8_t bank, uint8_t knob)
{
    if (knob >= 4u || bank >= MARBLES_BANK_COUNT) return MARBLES_PARAM_COUNT;
    return (uint8_t)(bank * 4u + knob);
}
static inline int marbles_control_set(marbles_control_t *m, uint8_t bank, uint8_t knob, int32_t delta)
{
    uint8_t p = marbles_control_param(bank, knob);
    int32_t v;
    if (!m || p >= MARBLES_PARAM_COUNT) return 0;
    v = (int32_t)m->value[p] + delta;
    if (v < 0) v = 0;
    if (v > (int32_t)MARBLES_VALUE_MAX) v = (int32_t)MARBLES_VALUE_MAX;
    m->value[p] = (uint16_t)v;
    return 1;
}
static inline void marbles_control_select_bank(marbles_control_t *m, uint8_t bank)
{
    if (m && bank < MARBLES_BANK_COUNT) m->bank = bank;
}
static inline uint32_t marbles_control_steps(const marbles_control_t *m)
{
    return 1u + ((uint32_t)m->value[MARBLES_CLOCK_STEPS] * 31u + 32767u) / 65535u;
}
static inline uint32_t marbles_control_t_probability(const marbles_control_t *m)
{
    return ((uint32_t)m->value[MARBLES_RANDOM_T] * 100u + 32767u) / 65535u;
}
static inline uint32_t marbles_control_jitter_limit(const marbles_control_t *m, uint32_t step_samples)
{
    uint32_t half = step_samples / 2u;
    return ((uint32_t)m->value[MARBLES_CLOCK_JITTER] * half + 32767u) / 65535u;
}
#endif
