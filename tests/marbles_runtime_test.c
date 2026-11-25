/* SPDX-License-Identifier: GPL-3.0-only
 * Host tests for the bounded Marbles-inspired runtime state machine.
 */
#include <assert.h>
#include <stdint.h>
#include "../firmware/src/marbles_runtime.h"

int main(void)
{
    marbles_runtime_t a, b;
    marbles_step_t x, y;
    uint32_t i;
    marbles_runtime_seed(&a, 0x12345678u);
    marbles_runtime_seed(&b, 0x12345678u);
    for (i = 0; i < 1000u; i++) {
        x = marbles_runtime_step(&a, 73u, 14u, 25u, 0u, 2u, 0x0AAAu, 0);
        y = marbles_runtime_step(&b, 73u, 14u, 25u, 0u, 2u, 0x0AAAu, 0);
        assert(x.trigger == y.trigger && x.note == y.note && x.x == y.x && x.y == y.y);
        assert(x.note <= 127u && a.history_count <= MARBLES_HISTORY);
    }

    marbles_runtime_seed(&a, 99u);
    x = marbles_runtime_step(&a, 0u, 12u, 0u, 0u, 0u, 0x0FFFu, 0);
    assert(!x.trigger);
    y = marbles_runtime_step(&a, 100u, 12u, 0u, 0u, 0u, 0x0FFFu, 0);
    assert(y.trigger);

    /* Deja Vu always selects a member of the bounded eight-note history. */
    marbles_runtime_seed(&a, 7u);
    for (i = 0; i < 20u; i++)
        x = marbles_runtime_step(&a, 100u, 16u, 0u, 0u, 5u, 0x0AAAu, 0);
    assert(a.history_count == MARBLES_HISTORY);
    y = marbles_runtime_step(&a, 100u, 16u, 100u, 0u, 5u, 0x0AAAu, 0);
    {
        uint32_t found = 0;
        for (i = 0; i < a.history_count; i++)
            found |= marbles_runtime_history_at(&a, i) == y.note;
        assert(found);
    }

    /* Freeze holds pitch and X/Y, while the gate probability can keep running. */
    x = marbles_runtime_step(&a, 100u, 16u, 0u, 1u, 5u, 0x0AAAu, 0);
    y = marbles_runtime_step(&a, 100u, 16u, 0u, 1u, 5u, 0x0AAAu, 0);
    assert(x.note == y.note && x.x == y.x && x.y == y.y && x.trigger && y.trigger);

    marbles_runtime_seed(&a, 1u);
    x = marbles_runtime_step(&a, 100u, 12u, 0u, 0u, 0u, 0x0FFFu, 1000);
    assert(x.note == 127u);
    marbles_runtime_seed(&a, 1u);
    x = marbles_runtime_step(&a, 100u, 12u, 0u, 0u, 0u, 0x0FFFu, -1000);
    assert(x.note == 0u);
    return 0;
}
