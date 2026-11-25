/* SPDX-License-Identifier: GPL-3.0-only
 * RINGS INTO CLOUDS — fixed-size source ownership for pitch-based note APIs.
 *
 * Two owners are intentionally modelled: the existing aggregate firmware note
 * path, and the independent Marbles generator. Existing keyboard/MIDI/ARP/
 * STANDARD semantics remain grouped exactly as before.
 */
#ifndef RIC_NOTE_OWNERSHIP_H
#define RIC_NOTE_OWNERSHIP_H

#include <stdint.h>

#define NOTE_OWNERSHIP_WORDS 4u
#define NOTE_OWNERSHIP_PITCHES 128u

enum { NOTE_OWNER_LEGACY = 0u, NOTE_OWNER_MARBLES = 1u };

typedef struct {
    uint32_t legacy[NOTE_OWNERSHIP_WORDS];
    uint32_t marbles[NOTE_OWNERSHIP_WORDS];
} note_ownership_t;

static inline uint32_t note_ownership_mask(uint32_t note)
{
    return 1u << (note & 31u);
}

static inline int note_ownership_has(const uint32_t *bits, uint32_t note)
{
    return note < NOTE_OWNERSHIP_PITCHES &&
           (bits[note >> 5] & note_ownership_mask(note)) != 0u;
}

/* Returns 1 only when this owner did not already hold the pitch. */
static inline int note_ownership_acquire(note_ownership_t *o, uint32_t owner, uint32_t note)
{
    uint32_t *bits;
    if (note >= NOTE_OWNERSHIP_PITCHES || owner > NOTE_OWNER_MARBLES)
        return 0;
    bits = owner == NOTE_OWNER_MARBLES ? o->marbles : o->legacy;
    if (note_ownership_has(bits, note))
        return 0;
    bits[note >> 5] |= note_ownership_mask(note);
    return 1;
}

/* Returns 1 only when this owner actually held and released the pitch. */
static inline int note_ownership_release(note_ownership_t *o, uint32_t owner, uint32_t note)
{
    uint32_t *bits;
    if (note >= NOTE_OWNERSHIP_PITCHES || owner > NOTE_OWNER_MARBLES)
        return 0;
    bits = owner == NOTE_OWNER_MARBLES ? o->marbles : o->legacy;
    if (!note_ownership_has(bits, note))
        return 0;
    bits[note >> 5] &= ~note_ownership_mask(note);
    return 1;
}

static inline int note_ownership_other_has(const note_ownership_t *o, uint32_t owner, uint32_t note)
{
    if (note >= NOTE_OWNERSHIP_PITCHES)
        return 0;
    return note_ownership_has(owner == NOTE_OWNER_MARBLES ? o->legacy : o->marbles, note);
}

static inline int note_ownership_any(const note_ownership_t *o, uint32_t note)
{
    return note_ownership_has(o->legacy, note) || note_ownership_has(o->marbles, note);
}

static inline void note_ownership_clear(note_ownership_t *o)
{
    uint32_t i;
    for (i = 0; i < NOTE_OWNERSHIP_WORDS; i++) {
        o->legacy[i] = 0u;
        o->marbles[i] = 0u;
    }
}

#endif
