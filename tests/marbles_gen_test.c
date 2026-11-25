/* SPDX-License-Identifier: GPL-3.0-only
 * Host tests for the pure Marbles-inspired generator primitives.
 * Build: cc -std=c99 -Wall -Wextra -Werror tests/marbles_gen_test.c -o /tmp/marbles_gen_test
 */
#include <assert.h>
#include <stdint.h>
#include "../firmware/src/marbles_gen.h"

int main(void)
{
    marbles_rng_t a, b;
    uint32_t i;
    marbles_rng_seed(&a, 12345u);
    marbles_rng_seed(&b, 12345u);
    for (i = 0; i < 10000u; i++)
        assert(marbles_rng_next(&a) == marbles_rng_next(&b));

    marbles_rng_seed(&a, 1u);
    for (i = 0; i < 10000u; i++) {
        uint32_t v = marbles_rng_bounded(&a, 7u);
        assert(v < 7u);
    }
    assert(marbles_rng_bounded(&a, 0u) == 0u);

    marbles_rng_seed(&a, 7u);
    for (i = 0; i < 100u; i++) {
        assert(!marbles_chance(&a, 0u));
        assert(marbles_chance(&a, 100u));
    }

    marbles_rng_seed(&a, 99u);
    for (i = 0; i < 10000u; i++) {
        int32_t d = marbles_degree(&a, 0, 12u);
        assert(d >= -6 && d <= 6);
    }
    assert(marbles_quantize_note(0, 0, 0x0FFFu) == 60u);
    assert(marbles_quantize_note(0, 0, 0u) == 60u);
    assert(marbles_quantize_note(0, 0, (1u << 0) | (1u << 4) | (1u << 7)) == 60u);
    assert(marbles_quantize_note(1, 0, (1u << 0) | (1u << 4) | (1u << 7)) == 64u);
    assert(marbles_quantize_note(-1, 0, (1u << 0) | (1u << 4) | (1u << 7)) == 55u);
    assert(marbles_quantize_note(1000, 0, 0x0FFFu) == 127u);
    assert(marbles_quantize_note(-1000, 0, 0x0FFFu) == 0u);
    return 0;
}
