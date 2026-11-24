# RINGS INTO CLOUDS — Project direction

## Product identity
RINGS INTO CLOUDS is a dedicated FM-1 instrument, not a reskin of SLOOP, HORATIO or Clipper. Felucca is the hardware and firmware foundation; the instrument architecture, sound design, interface and presets are developed for this project. The central experience is to play a resonator as an expressive instrument, then transform its sound through granular processing.

## Signal architecture
Default patch: `Exciter / Oscillator → Resonator → Granular Processor → Stereo Output`. This is not a fixed chain. Planned routing includes resonator before or after granular processing, granular feedback/freeze workflows, external or USB audio into granular processing where supported, and parallel dry/processed paths. A dedicated reverb may be added later as an optional modular processor. The inherited global tempo delay, chorus and reverb buses have been removed to keep the base instrument focused and free memory for Rings and Clouds. The inherited performance-loop recorder and its recording buffer, repeat/reverse, tape-stop, freeze, octave-shifter and global delay/reverb throws are also removed. Only the lightweight performance filters, flanger/phaser and track mutes remain.

## Sound systems
### Single Rings resonator
Use exactly one original Mutable Instruments Rings DSP instance, identified internally as `rings_main`, feeding the shared Clouds processor. Keep one `rings::Part`, one `rings::Strummer` and one set of model/parameter state. The five supported models are Modal, Sympathetic Strings, String, FM Voice and Quantized Sympathetic Strings. Exclude the String-and-Reverb model; Clouds retains its own native reverb. Do not expose or allocate a second Rings instance. See `docs/DUAL_RINGS_REQUIREMENTS.md` (now the single-instance decision record).

### Resonator
Develop a Rings-inspired resonator with Modal, Sympathetic and Inharmonic models, plus pluck, strike, bow and noise excitation. Keep a Rings-derived FM voice distinct from a separate six-operator DX-style FM synthesizer. Investigate the Disastrous Peace Easter-egg engine separately, subject to source and implementation verification.

### Granular processor
Develop a Clouds-inspired processor with granular/texture modes, buffer position and size, density, overlap, pitch, stereo spread, freeze and controlled feedback. Verify RAM and CPU cost before deciding how many simultaneous instances are practical.

### MIDI synchronisation
MIDI clock and transport synchronisation with external hardware is a must-have. The instrument must follow external MIDI clock and transport, and must also be able to act as a clock master where the FM-1 interfaces support it. Sequencer, arpeggiator, tempo-synchronised modulation, rhythmic effects and generative clocked modules must share a stable phase/timebase. Support USB-MIDI and TRS MIDI paths where verified, with clear source selection, clock-loss handling and protection against duplicate clocks/feedback. See `docs/MIDI_SYNC_REQUIREMENTS.md`.

## Modulation and performance
Plan for Peaks-inspired envelopes and LFOs; a Marbles-inspired generative CV/trigger system; a Yarns-inspired arpeggiator; and a conventional step sequencer. These are distinct systems, not one generic random sequencer.

### Removed legacy feature

Felucca SLICER is intentionally excluded from RINGS INTO CLOUDS. Do not carry over its gate/stutter insert, sample-recording buffers, step-pattern controls or menu entries. The project retains the sequencer itself and its MIDI clock/transport timing; removing SLICER must not remove or alter those shared timing systems. See `docs/MEMORY_PROFILE_OPTIONS.md` for the approved decision and memory accounting.

## Supporting synthesis and effects
Evaluate only the supporting modules that serve this instrument. The inherited global tempo delay, global chorus and global reverb have been removed. A dedicated optional reverb module remains a future goal; it must have a measured memory/CPU budget and be patchable/bypassable. Keep useful per-track distortion and insert processing only where it supports the modular design.

## FM-1 control and interface
- Keep the physical keyboard playable on the main performance page.
- Map every function to verified FM-1 controls; confirm hardware labels and firmware input handling before finalising the map.
- Use context-sensitive parameter controls with on-screen labels and values.
- Give each module a recognisable identity inspired by Mutable Instruments' visual organisation.
- Use original illustrations, symbols, colour combinations and layouts; do not reproduce Mutable Instruments logos or panel artwork.
- Prioritise legibility on the FM-1 screen. Eurorack panels are a grouping reference, not a literal screen layout.
- Presets should save the complete instrument state, including routing and modulation assignments.

## Visual language
- Strong module-specific colour families and restrained backgrounds.
- Geometric and organic illustrations that communicate the sound process.
- Clear hierarchy between module name, model, parameter labels and values.
- Compact parameter groupings and consistent knob/encoder semantics.
- Original artwork and typography with a coherent RINGS INTO CLOUDS identity.
Verify display dimensions, font rasterisation and UI drawing limits before producing final screen assets.

## Engineering constraints
1. Build the inherited firmware unchanged and record the baseline.
2. Map CPU1/CPU2 responsibilities, audio block size, sample rate, voice limits, memory pools and FX routing.
3. Measure CPU and RAM for each proposed DSP component independently.
4. Test worst-case polyphony and combinations; avoid dropouts and buffer underruns.
5. Keep host regression tests and golden audio renders updated for intentional DSP changes.
6. Verify package identity, versioning, recovery path and `.fwsc` installation before hardware release.

## Staged milestones
### Milestone 0 — Baseline and inventory
- Build the inherited firmware unchanged.
- Inspect UI, controls, audio graph, voice allocation and dual-core scheduling.
- Confirm submodule revisions and licence obligations.
- Record build/test results and CPU budgets.

### Milestone 1 — First playable RINGS → CLOUDS instrument
- Implement one reliable Rings resonator voice path and one granular processor with single-instance state ownership.
- Connect keyboard and physical controls.
- Add a small starter preset bank and original module-inspired performance screen.
- Validate audio, stability, CPU and memory on emulator and physical FM-1.

### Milestone 2 — Resonator and granular depth
- Add and validate the five supported Rings models and excitation choices on the single instance.
- Add granular texture, freeze and buffer controls.
- Add safe routing options and preset persistence.

### Milestone 3 — Modulation and generative performance
- Add envelopes and LFOs.
- Implement Marbles-style random pitch/voltage and trigger behaviour.
- Add a separate arpeggiator and conventional step sequencer.
- Expose assignable modulation destinations.

### Milestone 4 — Additional engines and effects
- Add the six-operator FM engine and other oscillator sources.
- Add filtering and a dedicated optional modular reverb after the Rings/Clouds core is measured. Global delay and chorus are intentionally excluded from the base instrument.
- Profile supported combinations and define sensible voice limits.

### Milestone 5 — Finish and release
- Complete original module-inspired UI and artwork.
- Finalise preset management, save/restore, MIDI and global settings.
- Run regression, CPU, memory, package and recovery tests.
- Publish labelled experimental and stable `.fwsc` builds with complete source and notices.

## Safeguards
- Do not promise that every module can run simultaneously until target profiling proves it.
- Do not call an engine a faithful Rings, Clouds, Marbles or Peaks implementation until its DSP/behaviour is integrated and tested.
- Do not copy proprietary artwork, logos, fonts or panel layouts verbatim.
- Preserve upstream copyright notices and licence files.
- Keep untested work off `main`.