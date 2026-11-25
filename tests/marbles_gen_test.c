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
    /* Scale masks are ROOT-relative, matching seq.c's scale_snap(). */
    assert(marbles_quantize_note(0, 2, (1u << 0) | (1u << 2) | (1u << 4) | (1u << 5) | (1u << 7) | (1u << 9) | (1u << 11)) == 62u);
    assert(marbles_quantize_note(1, 2, (1u << 0) | (1u << 2) | (1u << 4) | (1u << 5) | (1u << 7) | (1u << 9) | (1u << 11)) == 64u);
    assert(marbles_quantize_note(-1, 0, (1u << 0) | (1u << 4) | (1u << 7)) == 55u);
    assert(marbles_quantize_note(1000, 0, 0x0FFFu) == 127u);
    assert(marbles_quantize_note(-1000, 0, 0x0FFFu) == 0u);
    assert(marbles_quantize_note(0, 14u, (1u << 0) | (1u << 2) | (1u << 4) | (1u << 5) | (1u << 7) | (1u << 9) | (1u << 11)) == 62u);

    /* Every built-in seq.c scale mask stays ROOT-relative across a pitch sweep. */
    {
        static const uint16_t masks[] = {
            0xFFFu,
            (1u << 0) | (1u << 2) | (1u << 4) | (1u << 5) | (1u << 7) | (1u << 9) | (1u << 11),
            (1u << 0) | (1u << 2) | (1u << 3) | (1u << 5) | (1u << 7) | (1u << 8) | (1u << 10),
            (1u << 0) | (1u << 2) | (1u << 3) | (1u << 5) | (1u << 7) | (1u << 9) | (1u << 10),
            (1u << 0) | (1u << 2) | (1u << 4) | (1u << 5) | (1u << 7) | (1u << 9) | (1u << 10),
            (1u << 0) | (1u << 2) | (1u << 4) | (1u << 7) | (1u << 9),
            (1u << 0) | (1u << 3) | (1u << 5) | (1u << 7) | (1u << 10),
            (1u << 0) | (1u << 2) | (1u << 3) | (1u << 5) | (1u << 7) | (1u << 8) | (1u << 11),
            (1u << 0) | (1u << 1) | (1u << 3) | (1u << 5) | (1u << 7) | (1u << 8) | (1u << 10),
            (1u << 0) | (1u << 2) | (1u << 4) | (1u << 6) | (1u << 7) | (1u << 9) | (1u << 11),
            (1u << 0) | (1u << 1) | (1u << 3) | (1u << 5) | (1u << 6) | (1u << 8) | (1u << 10),
            (1u << 0) | (1u << 2) | (1u << 3) | (1u << 5) | (1u << 7) | (1u << 9) | (1u << 11),
            (1u << 0) | (1u << 3) | (1u << 5) | (1u << 6) | (1u << 7) | (1u << 10),
            (1u << 0) | (1u << 2) | (1u << 4) | (1u << 6) | (1u << 8) | (1u << 10),
            (1u << 0) | (1u << 1) | (1u << 3) | (1u << 4) | (1u << 6) | (1u << 7) | (1u << 9) | (1u << 10),
            (1u << 0) | (1u << 2) | (1u << 3) | (1u << 5) | (1u << 6) | (1u << 8) | (1u << 9) | (1u << 11)
        };
        uint32_t s, d;
        for (s = 0; s < sizeof masks / sizeof masks[0]; s++)
            for (d = 0; d <= 32u; d++) {
                int32_t degree = (int32_t)d - 16;
                uint8_t note = marbles_quantize_note(degree, 5u, masks[s]);
                uint32_t pc = (uint32_t)(((int32_t)note - 65 + 120) % 12);
                assert(masks[s] & (1u << pc));
            }
    }
    return 0;
}
