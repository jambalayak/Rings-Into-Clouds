/* SPDX-License-Identifier: GPL-3.0-only
 * Host tests for the Marbles control/UI boundary (not upstream DSP validation). */
#include <stdio.h>
#include "../firmware/src/marbles_control.h"
static int fails;
#define CHECK(x) do { if (!(x)) { printf("FAIL line %d: %s\n", __LINE__, #x); ++fails; } } while (0)
int main(void)
{
    marbles_control_t m;
    uint16_t before[MARBLES_PARAM_COUNT];
    unsigned i;
    marbles_control_init(&m);
    CHECK(m.bank == MARBLES_BANK_CLOCK && m.enabled == 1u);
    CHECK(marbles_control_steps(&m) == 32u);
    CHECK(marbles_control_t_probability(&m) == 0u);
    for (i = 0; i < 8u; ++i) CHECK(marbles_control_param((uint8_t)(i / 4u), (uint8_t)(i % 4u)) == i);
    CHECK(marbles_control_param(2u, 0u) == MARBLES_PARAM_COUNT);
    CHECK(marbles_control_param(0u, 4u) == MARBLES_PARAM_COUNT);
    for (i = 0; i < MARBLES_PARAM_COUNT; ++i) before[i] = m.value[i];
    marbles_control_select_bank(&m, MARBLES_BANK_RANDOM);
    CHECK(m.bank == MARBLES_BANK_RANDOM);
    CHECK(marbles_control_set(&m, m.bank, 0u, 1234));
    CHECK(m.value[MARBLES_RANDOM_DEJA_VU] == 1234u);
    for (i = 0; i < 4u; ++i) CHECK(m.value[i] == before[i]);
    CHECK(marbles_control_set(&m, MARBLES_BANK_CLOCK, 1u, -99999));
    CHECK(m.value[MARBLES_CLOCK_JITTER] == 0u);
    CHECK(marbles_control_set(&m, MARBLES_BANK_CLOCK, 1u, 99999));
    CHECK(m.value[MARBLES_CLOCK_JITTER] == 65535u);
    CHECK(marbles_control_jitter_limit(&m, 1000u) == 500u);
    CHECK(marbles_control_set(&m, MARBLES_BANK_CLOCK, 3u, -65535));
    CHECK(marbles_control_steps(&m) == 1u);
    CHECK(marbles_control_set(&m, MARBLES_BANK_RANDOM, 3u, 65535));
    CHECK(marbles_control_t_probability(&m) == 100u);
    CHECK(!marbles_control_set(&m, MARBLES_BANK_RANDOM, 4u, 1));
    CHECK(!marbles_control_set(0, MARBLES_BANK_CLOCK, 0u, 1));
    if (fails) return 1;
    puts("Marbles control boundary: all tests passed");
    return 0;
}
