# MARBLES Generator — Runtime and Data Design

Branch: `rings-into-clouds-dev`
Status: implementation specification based on inspection of `core.h`, `seq.c`, `params.c`, `project.c`, and `felucca.c`.

## 1. Existing firmware contracts

- `felucca.c` includes `core.h`, `engines.c`, `params.c`, `mod.c`, `voice.c`, then `song_chain.c`, `seq.c`, and `audio.c`. Sequencer code can use the already-defined track, parameter and modulation interfaces.
- `seq.c` runs in the audio ISR once per control-sample block. Its `seq_tick(track_t *, n)` receives the same elapsed sample count used by Standard sequencing.
- Standard sequencing owns `track_t.step[NSTEP]`, `seq_pos`, `seq_idx`, `seq_notes[]`, and its recording/tie/ratchet/nudge state.
- Project data is a versioned packed format (currently FUN10). `project.c` explicitly packs and validates fields; adding members to `track_t` does not persist them automatically.
- Existing parameter IDs are part of saved formats and editor protocol. New common parameters are normally inserted before `P_E0`, but doing so changes the common-parameter count and requires deliberate migration testing. Do not casually append runtime mode fields to the parameter enum.

## 2. Runtime state proposal

Introduce a dedicated `marbles_state_t marbles[NTRK]` in the sequencer module. Keep it separate from `track_t.step[]`.

Minimum fixed-size state per track:

- mode: STANDARD or MARBLES;
- PRNG seed/state (nonzero 32-bit);
- generated step counter and phase accumulator;
- current generated note and gate countdown;
- one pending event (note, velocity, gate duration, modulation X/Y);
- previous note / memory value for repeat and Deja-Vu-style behavior;
- reset/freeze flags and a compact history buffer with a fixed upper bound.

The exact structure must be sized with a compile-time assertion. No heap allocation, variable-sized storage, or unbounded loops.

## 3. Event generation and clock

- Continue to call the existing track sequencer tick from the existing audio control loop.
- Dispatch by mode inside the per-track tick: STANDARD executes the current implementation unchanged; MARBLES advances its own bounded state machine.
- Reuse the existing track's `P_SDIV` clock grid and transport. Do not add an independent BPM or MIDI clock implementation.
- MARBLES consumes the same sample-count/tick domain as Standard and observes transport start/stop and external-clock loss.
- A step event is generated only when its clock boundary is reached. A maximum of one generated event per track per boundary is allowed.
- Use integer arithmetic and bounded PRNG work. Seeded state must reproduce the same sequence after the same reset and parameter settings.

## 4. Pitch generation

- Use the existing scale masks and root/quantisation conventions already present in `seq.c`; do not create a second incompatible scale table.
- Generate a bounded scale degree from pitch bias and spread, map it through the selected scale, then clamp to the supported MIDI note range.
- Quantisation must be deterministic. An empty/invalid scale selection falls back safely to chromatic.
- Root, scale and transpose should have one authoritative interpretation shared with the existing keyboard/arp paths.

## 5. Probability, density and memory

- Density determines whether a clock boundary produces a note or rest.
- Probability controls variation independently from density; document the distinction in the UI.
- Bias moves the centre of the generated pitch distribution; spread controls its range.
- Memory controls how strongly the generator repeats or revisits recent values. A compact fixed history is sufficient for the first version.
- Freeze holds the generator's evolving state while clock and transport continue predictably.
- Reset restores the configured seed/state at a well-defined transport reset boundary.
- Avoid copying Mutable Instruments source or artwork unless the exact source/dependency licensing and port requirements are met; the implementation can be an original bounded generator inspired by the module's workflow.

## 6. Note ownership and safe transitions

The existing Standard note list is not a safe ownership container for a second event source.

- Add separate MARBLES note-active and note-number state.
- On a Marbles gate expiry, send note-off only for the note Marbles itself started.
- On mode change, stop, or reset, release only Marbles-owned notes.
- Standard's `seq_release()` must remain the Standard release path and must not release a Marbles note accidentally.
- Do not use a shared boolean that can make a Marbles note-off terminate a live keyboard/MIDI note of the same pitch. Before implementation, inspect the exact `trk_note_on/off` semantics and choose a source-safe ownership strategy (source counters/tokens if needed).
- Mode changes should be latched to the next step boundary, with an explicit immediate-stop path only for transport stop.

## 7. X/Y modulation

First version should produce two normalized signed modulation values in Marbles state. They should be routed through the existing modulation matrix only after confirming the matrix's source enum and per-track update contract. Do not directly overwrite synth parameters or invent source IDs.

## 8. Project persistence strategy

Do not alter the existing Standard step records.

Before changing project serialization:
1. Calculate the exact FUN10 offsets and unused bytes from `PROJ_STORE_SIZE`, `PROJ_NAME_OFF`, and the `proj_pack/proj_unpack` code.
2. Confirm the storage and editor import/export paths preserve any proposed extension.
3. Define a new format marker/version or a strictly validated extension with checksum coverage.
4. Old FUN1–FUN10 projects must import as STANDARD on all tracks.
5. New files must round-trip both mode and Marbles settings.
6. A project with unknown extension data must fail safely or preserve it; never silently reinterpret old step bytes.

For the first runtime prototype, keep Marbles settings at safe defaults and do not claim persistence until the format change and round-trip tests are implemented.

## 9. First implementation sequence

1. Add pure, host-testable integer PRNG and pitch-selection helpers.
2. Add tests for seed repeatability, scale bounds, density, probability, memory and reset.
3. Add fixed-size per-track Marbles state.
4. Add mode dispatch without changing the Standard branch.
5. Implement source-safe note gate ownership and mode/transport transitions.
6. Add clock and MIDI transport tests.
7. Implement versioned project persistence and backwards-compatibility tests.
8. Add UI mode/control access only after the runtime and persistence contracts are stable.

## Acceptance criteria

- Exactly one Rings-inspired resonator engine remains the synth architecture; Marbles is a sequencer mode, not an engine.
- Standard patterns, recording, ratchets, ties, nudges, conditions, and project compatibility remain unchanged.
- A track can select STANDARD or MARBLES independently.
- Multiple tracks can run different modes simultaneously on the same transport.
- Stop/mode switching cannot leave stuck notes or terminate notes owned by another input source.
- All generator work is bounded and deterministic; no heap allocation in the audio ISR.
- No build/test success is claimed until the target toolchain or host test suite has actually run.


## Implementation checkpoint (2026-11-25)

The first isolated, host-testable primitives now exist:

- `firmware/src/marbles_gen.h`: per-state seeded xorshift32 PRNG, multiply-high bounded draws, probability endpoints, bounded scale-degree displacement and ROOT-relative scale quantisation.
- `tests/marbles_gen_test.c`: deterministic replay, bounded output, probability endpoints, degree range, root-relative scale mapping and MIDI bounds.
- `tests/run_tests.sh`: compiles and runs the new test alongside the existing host tests.

The helper is now used by the per-track MARBLES branch in `seq_tick()`. The pitch-only note-off collision is addressed at the voice boundary with a two-owner legacy / Marbles ledger and regression tests. The integrated suite and target build have not been run in this environment; no full build or test pass is claimed.

## Canonical helper implementation (2026-11-25)

The duplicate `marbles_core.h` helper API and its standalone test have been removed. The canonical implementation is `firmware/src/marbles_gen.h`, exercised by `tests/marbles_gen_test.c` and invoked from `tests/run_tests.sh`.

The generator's scale quantizer treats the 12-bit scale mask as ROOT-relative, matching the existing `seq.c` convention: bit 0 is the root, bit 2 the major second, and so on. Tests cover a non-C root and all built-in scale masks. The helper is included by `marbles_runtime.h`, which is called from the live per-track `seq_tick()` branch.

## Sequencer mode parameter and FUN10 persistence (2026-11-25)

The per-track selector groundwork is now committed:

- `P_SEQMODE` is a common parameter immediately before `P_E0`; its values are STANDARD (0, default) and MARBLES (1).
- FUN10 byte 65 carries a marker and one bit per track. Byte 66 remains 114, so the ordinary parameter stream stays compatible with the previous 1.8 layout. Older firmware ignores the reserved byte and therefore safely plays STANDARD.
- The project writer keeps motion event IDs in the old 1.8 namespace on disk; the importer applies the existing parameter-count migration so current firmware restores engine automation IDs correctly.
- Project, user-preset and FUN10 tests were updated for the new selector and old-file defaults. The compile-time pack-size guard accounts for the omitted selector byte.

The selector and FUN10 persistence are implemented, `seq_tick()` dispatches STANDARD or MARBLES per track, the voice boundary has source-safe ownership, and the SEQ quick layer exposes the mode and Marbles controls. The C test suite and target build have not been run here.

## Voice-boundary note ownership (2026-11-25)

The pitch collision is now handled by a fixed two-owner ledger:

- `firmware/src/note_ownership.h` stores legacy and MARBLES ownership as two 128-pitch bitsets per track (32 bytes per track, compile-time asserted).
- `voice.c` keeps the existing keyboard/MIDI/ARP/STANDARD callers on their legacy wrappers and adds `trk_marbles_note_on/off()`. The raw allocator receives a note-off only after the releasing source no longer owns the pitch and the other owner does not hold it.
- Panic/all-off clears both owners. Engine-switch start clears old-engine ownership; new notes during the fade acquire fresh bits and remain represented while the existing pending-note queue is replayed through the raw allocator.
- `tests/note_ownership_test.c` covers the pure ledger, and `tests/fun10_test.c` now exercises same-pitch release ordering, MONO fallback, panic and pending engine-switch behavior.

The standalone ownership helper test was compiled and passed locally with C11, `-Wall -Wextra -Werror`. The standalone Marbles runtime helper and scale-quantizer checks also passed local host checks. The integrated FUN10/UI/modulation tests, full host suite, target CPU budget and FM-1 build remain unrun.

## Per-track runtime dispatch and FM-1 controls (2026-11-25)

The selector is now connected to the existing `seq_tick()` clock path:

- Each track independently chooses STANDARD or MARBLES. STANDARD continues through the existing step, ratchet, tie, condition and note-release path. MARBLES uses the same transport, MIDI clock advancement, division, length and swing timing; it does not create a second clock.
- MARBLES has a bounded per-track PRNG and eight-note Deja Vu history. Density, pitch range, memory/repeat probability, freeze and gate length are driven by existing persisted per-track controls in the Marbles mode: `P_APROB` (density), `P_AOCT` (range), `P_ASWING` (Deja Vu), `P_AHOLD` (freeze), and `P_AGATE` (gate). Root, scale and transpose use the existing track pitch settings.
- Marbles X and Y are exposed as append-only bipolar modulation sources `MX` and `MY`, so they can be routed through the existing four-slot modulation matrix.
- The SEQ quick layer now changes its four knobs by mode: STANDARD keeps LEN / DIV / SWING / GATE; MARBLES shows DENS / RANGE / DEJA / GATE. On synth tracks, black key 1 toggles STANDARD / MARBLES and black key 2 toggles FREEZE. The existing DRUM black-key lane selection is unchanged. OCT- restores both mode and Marbles settings captured when the layer opened.
- Mode changes release the outgoing source and restart the selected sequencer phase at its next tick. Transport stop releases Marbles gates and clears X/Y outputs. Engine changes fade old voices, clear old ownership, preserve any notes queued during the fade, and keep the Marbles generator state running.

Generated Marbles notes currently play through the shared voice allocator but are not yet written back into the Standard step pattern by REC. The integrated sequencer, modulation and UI regression tests have been added, but have not been run; the FM-1 target build and CPU budget remain outstanding.
