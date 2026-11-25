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
- The earlier 13-byte estimate omitted the three common AFTERTOUCH parameters added after the 1.5 layout. In the current source, the complete packed region leaves four bytes before FM6 and only one byte before `PROJ_MIDI_OFF`.
- A four-byte per-track selector cannot be inserted into the ordinary parameter stream without overlapping the MIDI extension or failing `proj_pack()`.

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

## 10. Canonical generator helper selected

The duplicate helper API has now been consolidated:

- Keep `firmware/src/marbles_gen.h` and `tests/marbles_gen_test.c` as the single canonical helper implementation and test.
- Remove `firmware/src/marbles_core.h` and `tests/marbles_core_test.c`; remove the latter's invocation from `tests/run_tests.sh`.
- The canonical quantizer is explicitly ROOT-relative, matching `seq.c`'s `scale_snap()` mask convention. A non-zero-root major-scale regression case is included in the generator test.

This is source consolidation only. The test suite has not been executed here, and the helper is still not included by `felucca.c`. The note-ownership and engine-switch queue gates remain open.


## 11. Corrected current FUN10 budget

The earlier arithmetic in this document used the 1.5-era parameter count and omitted the three AFTERTOUCH parameters introduced later. The current source before the selector has `P_COUNT = 114` and `P_E0 = 106), not 111 / 103.

The actual packed cursor is:

- Per track: `114 + 2 + 64 * 9 = 692` bytes.
- Track region: `68 + 4 * 692 = 2836`.
- Chain and motion: `84 + 388 = 472` bytes (`sizeof(motion_store_t) == 388`, asserted in `core.h`).
- End cursor: `2836 + 472 = 3308`.
- FM6 patch block begins at 3312, leaving four bytes; `PROJ_MIDI_OFF` is 3309, leaving only one byte before the three-byte MIDI extension.

The definitive guard is the real `proj_pack()` cursor check and the `midi_track_fmt()` regression assertion, not an estimate based on stale format notes. The new selector must not be added as an ordinary fourth byte per track without a separately verified encoding.

## 12. Per-track selector persistence implementation

The selector is now represented by `P_SEQMODE` before `P_E0`, with `STANDARD = 0` as its descriptor default and `MARBLES = 1`. The regular parameter stream deliberately omits this one value:

- FUN10 byte 65 carries a marker in bit 7 and one selector bit per track in bits 0..3.
- Byte 66 remains 114, the previous firmware's common-plus-engine parameter count. The regular parameter bytes are therefore still the exact old 1.8 layout, so older firmware can load the project and safely ignore the new reserved-byte selector (it will play STANDARD).
- New firmware unpacks the regular 114 values through `params_by_count()`, then restores each track's selector from byte 65. Older FUN10 projects have byte 65 clear and therefore default to STANDARD.
- The compile-time size guard uses `P_COUNT - 1` in the packed track formula, ensuring the out-of-line selector does not consume the existing MIDI IN TRACK extension or move the FM6 patches.
- Project tests now cover per-track mode round-trip, the legacy 114-parameter FUN10 default, and the earlier 103/104-parameter FUN10 migrations. User-preset parameter mapping retains the selector in its full parameter stream and defaults it for older records.

This is a compact backward-compatible encoding in the existing reserved header byte, not a new FUN11 format. The test suite has been updated but has not yet been run in this environment.
