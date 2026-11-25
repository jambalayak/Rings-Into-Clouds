# RINGS INTO CLOUDS — Sequencer Modes

## Product requirement

RINGS INTO CLOUDS has two selectable sequencer modes:

1. **MARBLES** — a generative sequencer inspired by Mutable Instruments Marbles.
2. **STANDARD** — the existing conventional step sequencer, retained as a predictable programmed sequencer.

These are two modes of one sequencing system, not separate synth engines. The user can choose the active mode from the sequencer page/settings. The RINGS instrument engine remains a single engine.

## MARBLES mode

Design an original, Marbles-inspired generative workflow with:

- Clock source and clock division/multiplication.
- Rate control and clock stability / jitter character.
- Probability and density controls for note generation.
- Quantized pitch generation with selectable scale and root.
- Controlled randomness / deviation from recent notes.
- Bias and spread controls for pitch range.
- Gate probability and gate length variation.
- A loop / random-memory control to move between repeatable patterns and evolving sequences.
- Separate modulation outputs (X/Y-style lanes) for evolving parameter movement, assignable through the existing modulation system.
- Reset and freeze/hold behavior.
- Tempo sync to the internal clock and supported external MIDI clock.

The interface should communicate generative behavior clearly. Avoid copying Marbles' exact panel artwork, labels, graphics, or layout; create an original FM-1 interface consistent with the RINGS INTO CLOUDS visual language.

## STANDARD mode

- Preserve the existing step sequencer and its current project/pattern data.
- Retain direct note entry, rests, ties, step lengths, pattern length, playback direction, and existing supported automation.
- Keep predictable timing and repeatable playback.
- Do not require generative settings to use the standard sequencer.

## Shared behavior and compatibility

- Both modes feed the same synth tracks, MIDI/keyboard routing, clock, transport, and modulation destinations where applicable.
- Mode switching must not erase or rewrite existing standard patterns.
- Existing projects that contain conventional patterns must open in STANDARD mode by default unless a project explicitly stores a different mode.
- Store new MARBLES settings in a versioned, backward-compatible project/preset extension. Do not repurpose existing fields or change the meaning of existing serialized data.
- Define deterministic reset/seed behavior so users can repeat a generative sequence when desired.
- Ensure MIDI clock, transport start/stop, pattern changes, and reset behavior are consistent in both modes.
- Keep generation bounded and real-time safe: no heap allocation in the audio callback; precompute or generate events at control/tick boundaries.
- Keep the standard sequencer usable even if the generative mode is disabled in a build configuration.

## Suggested user-facing controls

MARBLES:
- RATE
- BIAS
- SPREAD
- STEPS / DENSITY
- DEJA VU / MEMORY
- QUANTIZE / SCALE
- GATE
- X MOD
- Y MOD
- RESET / FREEZE

STANDARD:
- Existing pattern and step editing controls, unchanged where possible.

Exact labels and screen layout are provisional and must be checked against the FM-1 display dimensions and existing UI conventions.

## M1/M2 acceptance criteria

- One RINGS instrument engine only.
- Sequencer mode selector offers MARBLES and STANDARD.
- STANDARD mode preserves existing sequencing behavior and existing projects.
- MARBLES mode produces musically useful, controllable generative sequences rather than unbounded arbitrary randomness.
- Both modes are clock-synchronous and integrate with MIDI/transport.
- Mode switching is non-destructive.
- Tests cover deterministic seed/reset, clock sync, note range/scale quantization, event density, and backward compatibility of standard patterns.
