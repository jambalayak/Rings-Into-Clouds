/* SPDX-License-Identifier: GPL-3.0-only
 * Host tests for the Marbles-style control-rate event generator. */
#include <stdio.h>
#include "../firmware/src/marbles_engine.h"
static int fails;
#define CHECK(x) do { if (!(x)) { printf("FAIL line %d: %s\n", __LINE__, #x); ++fails; } } while (0)
int main(void)
{
    marbles_control_t c; marbles_engine_t a, b; marbles_event_t x, y;
    unsigned i, gates = 0u;
    marbles_control_init(&c); c.value[MARBLES_RANDOM_T] = 65535u;
    c.value[MARBLES_CLOCK_JITTER] = 65535u;
    marbles_engine_init(&a, 12345u); marbles_engine_init(&b, 12345u);
    for (i = 0; i < 256u; ++i) {
        x = marbles_engine_next(&a, &c, 48000u); y = marbles_engine_next(&b, &c, 48000u);
        CHECK(x.pulse == 1u && x.gate == 1u);
        CHECK(x.note >= 36u && x.note <= 127u && x.interval_samples >= 1u && x.interval_samples <= 72000u);
        CHECK(x.step < marbles_control_steps(&c));
        CHECK(x.note == y.note && x.gate == y.gate && x.interval_samples == y.interval_samples);
        gates += x.gate;
    }
    CHECK(gates == 256u);
    c.value[MARBLES_RANDOM_T] = 0u; c.value[MARBLES_CLOCK_JITTER] = 0u;
    marbles_control_init(&c); c.value[MARBLES_RANDOM_T] = 0u;
    marbles_engine_init(&a, 7u); x = marbles_engine_next(&a, &c, 48000u);
    CHECK(x.gate == 0u && x.pulse == 1u);
    CHECK(x.interval_samples >= 19000u && x.interval_samples <= 26000u);
    c.enabled = 0u; x = marbles_engine_next(&a, &c, 48000u);
    CHECK(x.pulse == 0u && x.gate == 0u);
    if (fails) return 1;
    puts("Marbles event generator: all tests passed"); return 0;
}
