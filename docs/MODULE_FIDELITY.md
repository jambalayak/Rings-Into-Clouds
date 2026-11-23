# RINGS INTO CLOUDS — Module fidelity standard

## User requirement

The modules should be as close as technically possible to their Mutable Instruments originals on the M-VAVE FM-1. The target is faithful musical behaviour, not merely a similar name, colour scheme, or broad sound category.

This document is a design and engineering requirement. It does not claim that the modules listed below have already been ported or implemented.

## Fidelity rules

For every module:

1. Use the original Mutable Instruments source code and official documentation as the primary reference wherever the source licence permits.
2. Preserve the original sound-generation or processing algorithm, operating modes, parameter ranges and response curves, modulation behaviour, trigger behaviour, and meaningful interactions between controls.
3. Preserve original mode names and the distinction between stock firmware features and optional third-party firmware features.
4. Keep parameter scaling and control behaviour faithful. Do not substitute unrelated controls simply because the FM-1 has fewer physical encoders.
5. Prefer a direct, tested port of the original DSP. If the FM-1 requires fixed-point conversion, lower sample rates, reduced polyphony, shorter buffers or other optimisation, document each change and measure its audible and CPU impact.
6. Keep the original module's signal path and routing semantics where possible. Do not silently replace audio-rate modulation with slow control-rate modulation, or remove feedback, stereo, freeze, or trigger behaviour.
7. Validate against reference renders from the original module: identical test signals, notes, parameter values and sample rates where possible. Compare waveforms, spectra, envelopes, decay times, stereo behaviour and CPU cost. Listening tests are also required.
8. A module must be labelled **faithful port**, **adapted port**, or **inspired implementation** according to the evidence. Never call an inspired implementation a full port.

## Module targets

### Mutable Instruments Rings

Target: the original Rings resonator, not just a generic modal synthesizer.

- Port the original resonator models and their distinctive interactions.
- Preserve the Modal, Sympathetic and String model families and their original model-selection behaviour.
- Preserve excitation behaviour, internal/external excitation options where the FM-1 signal architecture permits, polyphony/voice behaviour, damping, brightness, position, structure, and relevant FM behaviour.
- Preserve the original sympathetic-string response rather than using a generic delay-line substitute.
- Investigate and document the original Disastrous Peace Easter-egg mode separately; do not claim it exists until verified against the selected Rings source revision.
- The existing PHYS engine is a useful starting point, not proof of a complete Rings port. Its current source explicitly documents reduced mode counts, shortened delay lines, fewer sympathetic strings and other differences.

### Mutable Instruments Clouds

Target: the original Clouds granular audio processor.

- Reproduce the original audio-buffer architecture and granular engine, not only sample playback with grains.
- Preserve the original Texture, Pitch shifting, Looping delay and Spectral modes and their mode-specific controls.
- Preserve buffer capture, freeze, position, size, density, texture, pitch, blend, feedback, stereo spread and trigger behaviour as applicable to the original firmware.
- Preserve the relationship between incoming audio, the recording buffer and the granular output.
- Treat Parasites and other third-party firmware features as optional extras, clearly separated from stock Clouds.
- The existing GRAIN engine is a useful starting point but is sample-zone based and is not a complete Clouds implementation.

### Mutable Instruments Beads

Target: a separate Beads-inspired processor, with its own source reference and feature audit.

- Do not reduce Beads to a generic reverb. Beads is a granular processor with its own buffer, playback modes, recording behaviour, randomisation and built-in reverb.
- If Beads is included as a distinct module, preserve its distinctive granular and reverb behaviour rather than duplicating the Clouds page under another name.
- Document any features omitted or shared with the Clouds engine because of FM-1 memory and CPU limits.

### Mutable Instruments Ripples

- Preserve the original filter topology and filter responses, cutoff/resonance interaction, mode selection and modulation behaviour for the chosen Ripples revision.
- Keep low-pass, band-pass and high-pass behaviour only where present in the selected original version; do not mix features from different Ripples revisions without identifying them.
- Test resonance, self-oscillation and audio-rate modulation behaviour against reference renders.

### Mutable Instruments Peaks

- Preserve the original envelope and modulation modes, trigger/retrigger behaviour, curve shapes, time ranges and cycling behaviour for the chosen firmware revision.
- Keep envelope and LFO functions distinct where the original does.
- Preserve clock/reset synchronisation and modulation output scaling where supported by the FM-1 architecture.

### Mutable Instruments Marbles

- Implement the actual Marbles-style generative behaviour rather than a generic random sequencer.
- Preserve the roles of the X and Y outputs, clock generation/conditioning, bias, spread, Deja Vu/repetition, loop/recycle behaviour, quantisation and trigger probabilities.
- Keep the pitch and gate/trigger streams distinct and allow them to be routed to compatible destinations.
- Any reduced output count or simplified clock architecture must be documented as an adaptation.

### Mutable Instruments Yarns

- Use the original Yarns behaviour as the reference for the arpeggiator/MIDI subsystem.
- Preserve supported arpeggio patterns, octave range, note ordering, clock division, gate length, hold/latch, chord handling and MIDI behaviour as applicable to the selected Yarns firmware.
- Do not claim complete Yarns compatibility if the FM-1 cannot provide its original MIDI I/O or CV/gate outputs.

### Mutable Instruments Plaits

- Preserve all 16 original synthesis models, their model-specific parameter meanings, modulation inputs and model transitions.
- Use the original model order and names. Do not replace the models with similarly named but unrelated Felucca engines.
- Verify each model against reference audio and document any models that need reduced quality or polyphony on the FM-1.

## FM-1 constraints and adaptation policy

The FM-1 is not a Eurorack module system. It has a small display, a limited number of physical controls, a constrained embedded processor and memory, and a fixed audio I/O architecture. Therefore, some physical patch points and simultaneous processing configurations may not be possible.

Adaptation priority:

1. Preserve the sound and algorithm.
2. Preserve all important modes and musical controls.
3. Preserve modulation and routing behaviour.
4. Preserve polyphony and simultaneous module operation as far as measured CPU and memory budgets permit.
5. Adapt the user interface only where necessary to fit the FM-1 controls and screen.

Use pages, encoder focus, shift functions and an explicit routing matrix to expose controls that cannot be placed on dedicated knobs. A control being on another page is acceptable; removing its function or changing its response without reason is not.

When resource limits force a compromise, prefer a transparent selectable quality/polyphony setting over silently degrading every mode. Profile worst-case simultaneous use and protect the audio deadline.

## Verification checklist

For each module, maintain a source/revision record, licence record, feature matrix and test results:

- [ ] Original source and firmware revision identified
- [ ] Licence and required notices reviewed
- [ ] DSP port or adaptation identified
- [ ] Every original mode accounted for
- [ ] Every important control and its scaling accounted for
- [ ] Trigger, clock, modulation and routing behaviour accounted for
- [ ] Reference audio tests created
- [ ] CPU and memory measured on the FM-1 target
- [ ] Regression tests pass
- [ ] Listening comparison completed
- [ ] Remaining differences documented
- [ ] Correct fidelity label assigned

## Current known status

The inherited Felucca base includes a Rings-derived fixed-point sympathetic-string implementation inside PHYS and a separate sample-based GRAIN engine. The source documents meaningful differences from the original Rings and Clouds. These must be treated as partial foundations only.

No complete Rings, Clouds, Beads, Ripples, Peaks, Marbles, Yarns or Plaits port is established by this document. Implementation status must be updated only after source inspection, integration and tests.


## Rings original model coverage — pinned source audit (2026-11-23)

The pinned upstream `rings/dsp/part.h` at eurorack commit `08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4` defines six selectable `ResonatorModel` values:

| Source enum | Original mode |
|---|---|
| `RESONATOR_MODEL_MODAL` | Modal resonator |
| `RESONATOR_MODEL_SYMPATHETIC_STRING` | Sympathetic strings |
| `RESONATOR_MODEL_STRING` | String resonator |
| `RESONATOR_MODEL_FM_VOICE` | FM voice |
| `RESONATOR_MODEL_SYMPATHETIC_STRING_QUANTIZED` | Quantized sympathetic strings |
| `RESONATOR_MODEL_STRING_AND_REVERB` | String and reverb |

The sixth mode is not merely an optional global reverb effect. In upstream `Part::Process`, it changes string damping, performs stereo pickup cross-mixing, configures the Rings reverb from damping/brightness, processes the reverb and inverts the auxiliary output before the final limiter. It is a distinct original Rings mode. **Product decision (2026-11-23): RINGS INTO CLOUDS will omit this mode and its dedicated reverb to save memory.**

FM1_Locus clamps its selected model to `RESONATOR_MODEL_SYMPATHETIC_STRING_QUANTIZED` (enum value 4), thereby excluding `STRING_AND_REVERB` (value 5). RINGS INTO CLOUDS has now explicitly approved the same model omission as a resource trade-off. The supported Rings model set is therefore the first five modes in the table; do not expose or advertise String and Reverb in the UI. This is an adapted Rings port, not complete six-model stock Rings.

The original `Part` has a maximum of four internal resonator voices. `set_polyphony()` clamps to this maximum and marks the instance dirty; configuration is deferred until `Process()` calls `ConfigureResonators()`. The upstream API's `Part::Process` also owns the final stereo/aux split and limiter. Our integration must preserve these semantics, while moving expensive dirty configuration out of the audio deadline as a deliberate real-time-safe scheduling adaptation.

The original Strummer is a stateful onset detector with an inhibit timer. Its internal-strum behaviour depends on whether the note and exciter are internal or externally supplied. RINGS A and B each require their own Strummer instance; sharing one would couple onset history and inhibit state across modules.
