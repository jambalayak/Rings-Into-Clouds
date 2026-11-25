# Sequencer Integration Audit — MARBLES + STANDARD

Branch: `rings-into-clouds-dev`
Status: source inspection complete; no sequencer runtime code changed in this audit.

## Existing implementation found

The current sequencer is in `firmware/src/seq.c`, included by `felucca.c` after `song_chain.c`. Its core data structures are in `core.h`.

The existing STANDARD sequencer is already substantial:

- Four track patterns, up to `NSTEP` (64) steps per track.
- Per-track length, division, swing and gate.
- Note, rest, tie, slide, accent, ratchet, nudge and live recording behavior.
- Step conditions (including loop-count conditions) and fill behavior.
- Scale/root/quantise handling.
- Existing arpeggiator with multiple playback modes.
- Internal transport and USB/TRS MIDI clock handling, including fractional timing carries and clock-loss handling.
- Existing project formats serialize the per-track step patterns; project loading converts older formats.

The sequencer's central contract is useful: `seq_tick()` ultimately triggers `trk_note_on()` / `trk_note_off()`. The synth engine does not need to know whether a note came from Standard, Marbles, the keyboard, MIDI, or the arpeggiator.

## Recommended integration shape

### Keep STANDARD intact

- Do not rewrite `seq_tick()` or replace `step_t`.
- Do not repurpose existing step fields, track parameters, or project bytes.
- Preserve the existing project pattern format and all current recording/editing behavior.
- Existing projects load in STANDARD mode.

### Add MARBLES as a second sequencer mode

Recommended first implementation: a bounded, per-track generative event source that shares the existing transport clock and note-on/note-off functions, but owns its own generated state.

- Each track gets a mode selection: STANDARD or MARBLES.
- MARBLES generates the next note/gate/modulation events at sequencer tick boundaries. It must not generate unbounded work inside the audio loop.
- MARBLES must not overwrite `track_t.step[]`; stored Standard patterns remain available and intact.
- A deterministic per-track PRNG state allows repeatable sequences after reset/seed.
- Pitch generation uses the existing root/scale data and clamps to the supported MIDI note range.
- Probability, density, bias, spread, memory/looping, gate behavior and clock rate are bounded controls.
- X/Y-style generated modulation should be exposed through clearly defined modulation sources or lanes and routed through the existing modulation system where possible.
- The two modes use the same transport start/stop, clock source, tempo, MIDI clock, track mute/level, and note routing.
- Mode switching must release notes owned by the previous mode cleanly, without killing unrelated keyboard/MIDI-held notes.

A shared global mode is not recommended: per-track mode selection lets a user run a predictable bass sequence while generating evolving notes on another track. The UI can still provide a convenient all-tracks mode action later.

## Timing and ownership risks to solve before coding

1. **Note ownership:** current `seq_release()` releases notes held in the Standard sequencer's `seq_notes[]`. MARBLES needs its own note/gate ownership state so switching modes or stopping transport does not release live keyboard/MIDI notes or another track's arp notes.
2. **Clock domain:** `seq_tick()` receives block sample counts, with MIDI clock conversion handled by `midi_grid_advance()`. MARBLES should consume the same transport/tick timing rather than create a second independent clock.
3. **Mode switching:** define whether the new mode takes effect immediately or on the next step boundary; release the previous mode's owned notes deterministically.
4. **Recording:** Standard live recording must remain unchanged. Decide whether Marbles can record its generated notes into a Standard pattern as an explicit capture action; do not silently write generated notes into `step[]`.
5. **Persistence:** the project writer currently uses a versioned binary format (FUN10 in the inspected source). Do not add fields to `track_t` and assume they are automatically saved. Add a versioned, checksummed project extension or use a verified reserved region only after auditing pack/unpack size and compatibility.
6. **MIDI:** define Start, Continue, Stop, clock-loss and reset behavior for MARBLES. Reuse the existing MIDI clock and transport lifecycle.
7. **CPU:** use fixed-size state and bounded integer operations; no heap allocation, blocking work, or floating-point generation in the audio ISR.
8. **Testing:** add deterministic tests for seeded repeatability, scale/root quantisation, note/gate bounds, density/probability, clock sync, stop/restart, mode switching, and unchanged Standard project round trips.

## Proposed MARBLES control groups

- CLOCK: rate/division and internal/external sync behavior.
- PITCH: root, scale, bias and spread.
- GENERATION: density, probability and variation.
- MEMORY: repeat/hold versus evolving sequence.
- GATE: gate probability and length.
- X / Y: two generated modulation lanes, assignable to destinations through the existing modulation matrix.

Names and exact ranges remain provisional until the FM-1 display and parameter conventions are checked.

## Decision

Build one selectable **MARBLES mode** alongside the existing **STANDARD mode**. Do not create a second synth engine. Keep the current sequencer implementation and stored patterns as the compatibility baseline.
