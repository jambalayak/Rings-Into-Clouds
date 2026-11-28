# Single Rings + Clouds + Marbles routing specification

## Selected topology

- One complete Rings instance (`rings_main`) feeds one Clouds processor by default.
- Rings keeps the five supported models, original eight-string capacity, natural decay and native stereo OUT/AUX.
- Clouds remains a processor with its own state and buffer; it is not a second synth engine.
- Marbles supplies pitch CV, parameter modulation and trigger events to the one Rings instance.
- The dedicated DRUM engine remains on Track 4.
- The FM-1 keyboard, MIDI input and sequencer remain valid note sources for Rings.

## Marbles-to-Rings mapping

### Pitch

- X1 and X2 are each independently routable to the single Rings pitch input.
- When both are enabled, combine them in a documented pitch-CV summing stage with independent attenuation and offset per source. Do not add two unscaled full-range voltages implicitly.
- Preserve the original Marbles output distributions, quantisation, jitter and Deja Vu behaviour before applying the destination scaling.
- The base keyboard/sequencer note remains the pitch reference. Marbles CV is a modulation offset, not a replacement for the note.
- Exact defaults and scaling range must be established with musical regression tests before implementation is called complete.

### Strum triggers

- T1 and T2 remain independent trigger-event sources.
- Merge their rising-edge events into the one Rings Strummer event stream. A distinct edge from either source must be capable of producing a strum even when the other source is active; do not implement this as a simple level-OR gate that loses overlapping events.
- Preserve T1 random-gate and T2 master-pulse semantics, pulse timing and clock synchronisation.
- T3 retains its original Marbles semantics and is not assigned to Rings until its destination behaviour is explicitly validated.

### Parameter modulation

- X3 and Y remain independently available as modulation sources.
- Each can target any supported Rings control: Structure, Brightness, Damping or Position; Frequency modulation is handled as a pitch offset with defined scaling rather than a fabricated Patch field.
- Each assignment stores destination, amount and polarity/attenuation. The current modulation value is visible on the Rings performance page.
- Preserve Marbles timing and output behaviour; destination scaling must not modify the generator itself.

## Rings performance screen

- Always show Frequency, Structure, Brightness, Damping and Position.
- Frequency is an offset from the incoming keyboard/sequencer/MIDI note.
- Four physical FM-1 rotary controls edit four assigned parameters; SELECT cycles the assignment to the fifth.
- Highlight the active assignment and update its displayed value immediately.
- Screen state and physical controls must address the actual Rings DSP parameter state.

## Signal path and stereo

- Default route: excitation/keyboard or sequencer -> Rings -> Clouds -> stereo mixer/output.
- Keep Rings OUT and AUX as distinct native channels until a deliberate routing/mix stage.
- Provide a dry Rings path and a processed Clouds path where the mixer graph can support them without duplicating DSP state.
- Clouds preparation runs outside the audio interrupt; audio processing uses preallocated buffers and bounded work.

## Resource and fidelity constraints

- No second Rings Part, Strummer, delay bank, preset state or UI selector is allocated.
- Do not remove any of the five models, reduce the eight-string bank, shorten Rings decay, or change upstream coefficients to fit memory.
- Keep Clouds at 32 kHz / 16-bit quality as the target. Do not shorten its recording window without a separate explicit decision supported by a target memory measurement.
- Target link must demonstrate at least 4 KiB ordinary-RAM and 8 KiB POOL headroom after all buffers, resamplers, FIFOs, routing state and stack reservations are included.
- Verify CPU deadlines with CPU2 enabled and unavailable.

## Acceptance tests

1. One Rings Part and one Strummer are constructed and initialised exactly once.
2. All five models render and respond correctly to keyboard/MIDI/sequencer pitch, excitation and all five performance controls.
3. X1 and X2 independently modulate the same pitch input; combined routing has bounded, documented scaling.
4. T1 and T2 each generate distinct strum events, including overlapping-trigger cases.
5. X3 and Y independently modulate selected parameters with saved destination/amount settings.
6. Clouds receives the intended stereo signal without channel swaps, FIFO drift, clipping or underruns.
7. Preset save/recall restores Rings, Clouds, routing and Marbles assignments.
8. Existing DRUM-on-Track-4 behaviour and legacy project compatibility remain intact.
9. Host regression, target linker, CPU, Harbor/emulator and physical FM-1 results are reported separately.

## Status

This document records the selected architecture and routing contract. It does not claim that Marbles DSP, the Rings audio path, Clouds routing or the performance screen is already implemented or hardware-tested.
