/* SPDX-License-Identifier: GPL-3.0-only
 * Host tests for fixed-size legacy / Marbles note ownership.
 */
#include <assert.h>
#include "../firmware/src/note_ownership.h"

int main(void)
{
    note_ownership_t o = {{0}, {0}};

    /* Both release orders preserve the other source's pitch. */
    assert(note_ownership_acquire(&o, NOTE_OWNER_LEGACY, 60u));
    assert(note_ownership_acquire(&o, NOTE_OWNER_MARBLES, 60u));
    assert(note_ownership_any(&o, 60u));
    assert(note_ownership_release(&o, NOTE_OWNER_LEGACY, 60u));
    assert(note_ownership_other_has(&o, NOTE_OWNER_LEGACY, 60u));
    assert(note_ownership_any(&o, 60u));
    assert(note_ownership_release(&o, NOTE_OWNER_MARBLES, 60u));
    assert(!note_ownership_any(&o, 60u));

    assert(note_ownership_acquire(&o, NOTE_OWNER_MARBLES, 64u));
    assert(note_ownership_acquire(&o, NOTE_OWNER_LEGACY, 64u));
    assert(note_ownership_release(&o, NOTE_OWNER_MARBLES, 64u));
    assert(note_ownership_other_has(&o, NOTE_OWNER_MARBLES, 64u));
    assert(note_ownership_release(&o, NOTE_OWNER_LEGACY, 64u));
    assert(!note_ownership_any(&o, 64u));

    /* Duplicate acquire/release is idempotent, including pitch 0 and 127. */
    assert(note_ownership_acquire(&o, NOTE_OWNER_MARBLES, 0u));
    assert(!note_ownership_acquire(&o, NOTE_OWNER_MARBLES, 0u));
    assert(!note_ownership_release(&o, NOTE_OWNER_LEGACY, 0u));
    assert(note_ownership_release(&o, NOTE_OWNER_MARBLES, 0u));
    assert(note_ownership_acquire(&o, NOTE_OWNER_LEGACY, 127u));
    assert(note_ownership_release(&o, NOTE_OWNER_LEGACY, 127u));

    /* Different pitches and owners remain independent. */
    assert(note_ownership_acquire(&o, NOTE_OWNER_LEGACY, 35u));
    assert(note_ownership_acquire(&o, NOTE_OWNER_MARBLES, 96u));
    assert(note_ownership_release(&o, NOTE_OWNER_LEGACY, 35u));
    assert(note_ownership_any(&o, 96u));
    note_ownership_clear(&o);
    assert(!note_ownership_any(&o, 96u));
    assert(!note_ownership_any(&o, 35u));

    /* Out-of-range notes and owner IDs are rejected. */
    assert(!note_ownership_acquire(&o, NOTE_OWNER_MARBLES, 128u));
    assert(!note_ownership_acquire(&o, 2u, 60u));
    assert(!note_ownership_release(&o, NOTE_OWNER_MARBLES, 128u));
    return 0;
}
