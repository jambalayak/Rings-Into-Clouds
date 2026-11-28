# Marbles sequencer — implementation audit

Status: sequencer page, control model and a lightweight original event generator are implemented and host-test sources exist. The official Mutable Instruments Marbles DSP is not ported, and the generator is not connected to transport, MIDI clock, Rings note/strum routing or audio DSP.

## Implemented

- `firmware/src/params.c`: dedicated `GR_MARBLES` page in the Sequencer family, after AUTOMATION. Its control state is currently static runtime UI state; it is not persisted.
- `firmware/src/ui_input.c`: K1–K4 edit the selected bank; OCT− selects CLOCK and OCT+ selects RANDOM.
- `firmware/src/ui_graph.c`: dedicated compact CLOCK/RANDOM renderer. STEPS is shown as a step count.
- `firmware/src/ui_help.c`: Marbles page help hint.
- `firmware/src/marbles_control.h`: eight-control model, two banks and helper functions.
- `firmware/src/marbles_engine.h`: deterministic, lightweight, control-rate event generator with bounded jitter, sequence memory/Deja Vu, pitch shaping and gate probability.
- `tests/marbles_engine_test.c` and `tests/run_tests.sh`: host tests for the standalone generator. These do not establish firmware audio integration or target performance.

## Not implemented

- Official Mutable Instruments Marbles DSP port and upstream revision audit.
- Clock/transport adapter, external-clock selection, event scheduler and gate/pulse duration routing.
- Marbles-to-Rings pitch/strum/CV modulation routing.
- Actual Rings DSP implementation in the live audio path; current generator output must not be routed into an unrelated legacy engine as a substitute.
- RUN/enable interaction and explicit start/stop behaviour.
- Versioned persistence for Marbles controls and modulation assignments.
- Full FM-1 target validation of the latest UI and generator changes.

## Architecture constraints

- The target live instrument has two parts: Rings (live part 1) and Drums (live part 2). The frozen FUN1..FUN10 project/protocol layout remains four tracks; legacy project Track 4 maps to live Drums part 2. Do not change `NPART`, `NTRK`, serialized layouts or checksum logic without completing the migration audit.
- Marbles is a sequencer/modulation source for Rings, not an audio track or third voice engine.
- Clouds is an optional/bypassable processor on Rings, not a separate track.
- Keep the five Rings models, eight-string capacity and natural decay. Do not reduce sound quality to work around memory failures.
- Do not consume FUN10 reserved bytes casually. Its 3840-byte size and checksum are frozen.
- External clock must take priority when selected; RATE only controls internal clock. JITTER must remain bounded within the current step.
- t controls Marbles gate probability; it must never randomly mute the Rings audio signal itself.
- T1 and T2 must preserve independent trigger edges, including overlaps; a level-OR implementation is insufficient.
- X1/X2 pitch offsets are summed with explicit bounded scaling. X3/Y modulation destinations, amount and polarity require defined mappings and persistence.
- Keep all audio work bounded and allocation-free in the interrupt. Verify CPU2 enabled and unavailable.

## Next implementation sequence

1. Stabilise the current branch CI and confirm the UI regression tests and host generator tests pass.
2. Complete a standalone host-testable clock/transport adapter with explicit RUN/STOP, external-clock priority, bounded jitter and pulse scheduling. Do not emit audio notes yet.
3. Add tests for step count, repeatability, Deja Vu memory, pitch range, gate probability extremes, clock changes, pulse overlap and disabled silence.
4. Complete the pinned upstream Rings source integration, then validate Rings alone against the FM-1 linker, RAM, POOL and CPU budgets. The current diagnostic profile has exceeded the app image and ordinary-RAM limits; resolve this with measured state/buffer savings, not reduced Rings fidelity.
5. Only after Rings DSP is in the live path, connect Marbles events to its note/strummer and modulation inputs. Preserve keyboard, MIDI and ordinary sequencer note sources.
6. Add versioned persistence outside the frozen FUN10 layout and migration tests.
7. Validate host regression, target linker, CPU, Harbor/emulator and physical FM-1 separately. Never report emulator or host tests as hardware validation.

## Current honest status

The Marbles UI and standalone generator are partial implementation. They are not yet a working Marbles-to-Rings instrument. Rings/Clouds live audio integration and hardware validation remain incomplete.
