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


## 7. Narrow ownership bridge candidate

A less invasive first implementation may be possible without redesigning every existing input source. Keep all existing callers on the current legacy note API and add a dedicated Marbles note API:

- Rename the current voice operations internally to raw track-note operations.
- Keep `trk_note_on/off()` as the legacy path, tracking whether the legacy path currently owns each pitch.
- Add `trk_marbles_note_on/off()`, tracking Marbles ownership separately per track and pitch.
- A raw note-off is issued only when the releasing owner was active and no other owner still holds that pitch.
- If Marbles starts a pitch already owned by the legacy path, record its ownership but do not issue a second raw note-on. This avoids duplicate entries collapsing in the mono stack.
- If the legacy path starts a pitch already owned by Marbles, it may retrigger normally; Marbles' later release is suppressed while legacy ownership remains.
- Clear both ledgers in `trk_all_off()` and on every path that invalidates a track's voices (preset/project panic, track silence, and any equivalent reset).

This two-owner bridge preserves the current aggregate semantics among keyboard, MIDI, arp and Standard sequencing, while preventing Marbles from releasing their pitch. It is a candidate, not an approved implementation: it still needs tests for note-on ordering, mono priority, poly allocation, unison, engine-switch pending notes, mute, panic and track reset. In particular, every call path that can bypass `trk_note_on/off()` or invalidate voices must be accounted for. Use fixed-size per-track bitsets (128 MIDI pitches) rather than dynamic allocation, and keep the ledger out of `track_t` unless its alignment / memory budget is re-audited.


## 8. Verified FUN10 spare-byte correction

A closer read of the current serializer's actual offset comments corrects the preliminary budget in section 4 above.

- FUN10 has 16 spare bytes between the variable per-track parameter/step/chain/motion region and the FM6 patch block.
- The existing MIDI IN TRACK routing extension consumes the final 3 bytes of that gap at `PROJ_MIDI_OFF`.
- Therefore 13 bytes remain before the FM6 block, not four.
- A single additional per-track byte parameter is serialized as four bytes total (one per track), so it appears to fit with nine bytes remaining, subject to the exact `proj_pack()` cursor check and compile-time bounds.

The safe compatibility approach remains append-only common parameter insertion immediately before `P_E0`, with the default selector value meaning STANDARD. `params_by_count()` then maps older project and preset parameter counts into the new layout and supplies the new parameter's descriptor default. The project and user-preset migrations, motion parameter IDs, editor protocol and learned MIDI CC mapping must all be tested because `P_E0` shifts when a common parameter is inserted.

Do not change FUN10's magic or size merely to add this selector if the exact pack/unpack cursor and checksum tests prove the reserved byte budget is sufficient. Older firmware already rejects FUN10 records whose parameter count is greater than its own, so document that expected downgrade behavior.

This correction supersedes the "exactly four bytes" budget sentence in section 4. No serializer code has been changed yet.

## 9. Runtime call-site audit (2026-11-25)

The focused source inspection confirms the ownership boundary and adds several concrete constraints:

- The only definitions of `trk_note_on()`, `trk_note_off()` and `trk_all_off()` are in `firmware/src/voice.c` (around lines 395, 442 and 475 in the audited revision).
- The engine-switch completion path in `voice.c` replays the pending `xp_note[] / xp_vel[]` queue by calling `trk_note_on()` directly. A Marbles-specific pending note must therefore retain its owner across the four-block engine fade; replaying all pending notes as legacy would lose ownership.
- In `seq.c`, the arpeggiator has its own note-on/off calls (around lines 299, 307, 315, 454), live input has note-on/off calls (around 682 and 699), and the Standard sequencer releases its tracked notes and starts new notes (around 926, 1058 and 1064). Track panic/reset calls `trk_all_off()` (around 1433).
- The arpeggiator also has `arp_forget()`, which ends its currently sounding notes through the ordinary note-off API. The Standard sequencer has its own `seq_notes[]` list. These are separate lifecycle owners in the callers even though the voice layer currently merges them.
- `trk_note_off()` first removes a pitch from the mono stack and pending engine-switch queue, then releases every matching gated voice. It has no note-instance token. `trk_all_off()` releases all voices and clears mono and pending-note state. Engine-switch completion independently hard-clears all old voices before replaying queued notes. Those invalidation paths must clear any new ledger consistently.
- The audited `felucca.c` does not include either Marbles helper header, and no Marbles runtime scheduler is currently wired into the firmware translation unit.

### Helper consolidation warning

Two different pure Marbles helper headers currently exist:

- `firmware/src/marbles_gen.h` defines `marbles_rng_t`, seeded xorshift, multiply-high bounded draws, `marbles_chance()`, scale-degree displacement and degree-to-note quantisation. `tests/marbles_gen_test.c` exercises this API.
- `firmware/src/marbles_core.h` defines a pointer-state RNG API, modulo bounded draws, probability, and note-based scale snapping. `tests/marbles_core_test.c` exercises this different API.

The host test script contains separate test invocations for both helpers. Neither header is included by `felucca.c` in the audited revision. These are not interchangeable APIs: the bounded-draw algorithms and quantisation semantics differ. Before runtime wiring, select one canonical implementation, reconcile its tests and design notes, and remove or explicitly retain the other as a compatibility/test fixture. Do not include both and accidentally create divergent random streams or scale behavior.

### Revised implementation gate

The narrow two-owner bridge in section 7 is not yet sufficient as written unless the pending engine-switch queue also stores source ownership. A safe first runtime milestone should either:
1. add owner metadata to each pending-note slot and replay through the matching owner API; or
2. keep Marbles notes out of the existing pending queue and explicitly cancel their ownership when an engine switch begins.

Option 1 preserves notes through an engine switch and is preferred if the queue can be extended without breaking its bounded capacity or legacy behavior. Tests must cover a Marbles note started during the fade, released before the fade completes, and replayed after the new engine is active.

The existing source families are not yet individually separated at the voice boundary. A dedicated Marbles owner alongside the legacy aggregate is still the least disruptive design, but Marbles must never be silently converted into a legacy pending note.
