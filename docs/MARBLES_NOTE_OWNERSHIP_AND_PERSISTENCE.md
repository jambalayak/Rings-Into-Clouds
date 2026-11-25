# Marbles note ownership and project persistence decision

Status: design gate before runtime integration.

## 1. Note-off behavior: confirmed conflict

The current note API is pitch-based, not source-based:

- `trk_note_on(track, note, velocity)` allocates/retriggers voices or adds the pitch to the mono stack.
- `trk_note_off(track, note)` removes that pitch from the mono stack and releases every gated voice on the track whose `voice.note` equals that pitch.
- `trk_all_off(track)` releases every voice and clears the mono and engine-switch pending-note state.
- The Standard sequencer keeps its own `seq_notes[]` list, but its eventual release still calls the same pitch-only `trk_note_off()`.
- The arpeggiator, keyboard, MIDI input, step sequencer, and engine-switch pending-note path all converge on the same note API.

Consequently, a Marbles note-off for pitch N can release a keyboard, MIDI, arp, or Standard note on the same track and pitch. Avoiding duplicate Marbles pitches only prevents duplicates inside its own stream; it does not solve cross-source collisions. This is a correctness blocker, not a cosmetic edge case.

## 2. Required ownership design before Marbles playback

Do not add a Marbles call to the current pitch-only note-off path.

The preferred direction is a source-aware note ownership layer at the track note boundary, with distinct owners for at least:

- keyboard / live input (including MIDI input);
- Standard sequencer;
- arpeggiator;
- Marbles generator;
- transient audition / preview where applicable.

A source releases only the note instance it acquired. The layer must preserve current pitch, velocity, mono priority, legato, unison, voice stealing, engine-switch queueing and recording behavior. In particular, it must not simply count all note-ons by pitch and decrement on every note-off: repeated notes, arp retriggers, ties, chords and mono-stack priority need explicit semantics.

Before implementation, map every note-on/off call site and decide whether ownership belongs in caller wrappers or in a compact per-track ledger. The legacy Standard / keyboard / MIDI behavior must remain bit-for-bit unchanged in the no-Marble case. Add regression cases for same-pitch overlap in both release orders, different pitches in mono priority modes, poly voice allocation, unison, arp overlap, ties, stop/panic, engine switching and mute.

## 3. Existing Standard sequencer integration point

The safe scheduling point remains the existing `seq_tick()` path. It already owns transport timing, internal and external MIDI clock progression, per-track division and elapsed-sample accounting. Standard sequencing should remain intact and keep its `step_t` patterns and `seq_notes[]` bookkeeping.

Once ownership is solved, dispatch the selected per-track source at the existing tick boundary:

- STANDARD: execute the existing code without behavioral changes.
- MARBLES: generate bounded events from a separate fixed-size state object and send them through the same track note / modulation / recording contracts.

Do not create a second clock or mutate Standard pattern memory to store Marbles history.

## 4. FUN10 persistence budget

The current project format is FUN10, 3840 bytes. The project serializer stores each track's parameter array as one biased byte per parameter, then engine/preset bytes and 64 packed 9-byte steps. It separately stores chain, motion, MIDI-track routing, FM6 patches and project name. Project hashing covers the serialized bytes.

The current FUN10 layout has exactly four bytes of space before the FM6 patch block after accounting for the chain and motion blocks. One additional per-track parameter consumes exactly four bytes across four tracks. Therefore a single appended global track parameter (for example, an append-only sequencer source selector) appears to fit the existing FUN10 reserved budget without moving the chain, motion, MIDI routing, patches or name.

This is a layout calculation, not yet a code change. Before using it:
- verify the current `P_COUNT`, `P_E0`, parameter insertion/migration rules and all user-preset/editor protocol mappings;
- verify `proj_pack()` still lands at or before `PROJ_MIDI_OFF` for the new count;
- add round-trip and corruption/hash tests for the new selector;
- confirm older FUN10 records load with STANDARD as the default;
- document that older firmware may reject a newer FUN10 whose parameter count exceeds its own, consistent with the existing version behavior.

Do not store volatile PRNG history in unused project bytes by assumption. Decide separately whether Marbles restarts from a deterministic project seed, a saved seed, or a fresh session seed. The selector must default to STANDARD for all older projects and presets.

## 5. Test-first sequence

1. Add host-testable pure helpers for seeded PRNG, bounded random ranges, scale-mask pitch selection and probability/density decisions. No audio globals or hardware dependencies.
2. Test deterministic replay, zero/full probability, edge pitch clamps, every supported scale mask, and bounded execution.
3. Implement and test source ownership independently of Marbles generation.
4. Integrate the Marbles scheduler into `seq_tick()` behind the per-track selector; keep STANDARD path unchanged.
5. Add transport, clock-loss, MIDI clock, reset, freeze, mode-switch and note-release tests.
6. Add FUN10 and preset/editor persistence coverage.
7. Run the full host suite, target CPU budget and firmware build before claiming runtime integration complete.

## 6. Current status

No runtime sequencer or voice code is changed by this decision. The existing note-off API is insufficient for safe independent Marbles note ownership, and the next implementation step is a focused source-ownership design plus host tests. The one-Rings-engine requirement remains unchanged; Marbles and Standard are sequencer modes, not synth engines.
