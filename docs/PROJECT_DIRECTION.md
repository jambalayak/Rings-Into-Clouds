# RINGS INTO CLOUDS — Project direction

## Product identity
RINGS INTO CLOUDS is a dedicated FM-1 instrument, not a reskin of SLOOP, HORATIO or Clipper. Felucca is the hardware and firmware foundation; the instrument architecture, sound design, interface and presets are developed for this project. The central experience is to play a resonator as an expressive instrument, then transform its sound through granular processing.

## Signal architecture
Default patch: `Exciter / Oscillator → Resonator → Granular Processor → Spatial Effects → Stereo Output`. This is not a fixed chain. Planned routing includes resonator before or after granular processing, resonator to reverb, granular feedback/freeze workflows, external or USB audio into granular processing where supported, and parallel dry/processed paths. First map Felucca's existing audio graph, voice allocation, FX buses and inter-core boundaries.

## Sound systems
### Dual independent Rings engines
Provide two simultaneous, independent instances of the same Rings DSP engine, exposed as RINGS A and RINGS B on separate FM-1 parts. Each has its own model, exciter/strummer state, parameters, modulation, preset and audio route. Both must be editable separately and audible together, subject to a measured shared CPU/voice/memory budget. This is a core requirement; see docs/DUAL_RINGS_REQUIREMENTS.md.

### Resonator
Develop a Rings-inspired resonator with Modal, Sympathetic and Inharmonic models, plus pluck, strike, bow and noise excitation. Keep a Rings-derived FM voice distinct from a separate six-operator DX-style FM synthesizer. Investigate the Disastrous Peace Easter-egg engine separately, subject to source and implementation verification.

### Granular processor
Develop a Clouds-inspired processor with granular/texture modes, buffer position and size, density, overlap, pitch, stereo spread, freeze and controlled feedback. Verify RAM and CPU cost before deciding how many simultaneous instances are practical.

### MIDI synchronisation
MIDI clock and transport synchronisation with external hardware is a must-have. The instrument must follow external MIDI clock and transport, and must also be able to act as a clock master where the FM-1 interfaces support it. Sequencer, arpeggiator, tempo-synchronised modulation, rhythmic effects and generative clocked modules must share a stable phase/timebase. Support USB-MIDI and TRS MIDI paths where verified, with clear source selection, clock-loss handling and protection against duplicate clocks/feedback. See `docs/MIDI_SYNC_REQUIREMENTS.md`.

## Modulation and performance
Plan for Peaks-inspired envelopes and LFOs; a Marbles-inspired generative CV/trigger system; a Yarns-inspired arpeggiator; and a conventional step sequencer. These are distinct systems, not one generic random sequencer.

### Supporting synthesis and effects
Evaluate Plaits-inspired oscillator models, Ripples-inspired filtering, Beads-inspired spatial reverb, delay, chorus and distortion. Implement only after profiling the core resonator/granular path.

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
- Implement one reliable resonator voice path and a granular processor, while designing instance APIs and state ownership for two independent Rings engines from the outset.
- Connect keyboard and physical controls.
- Add a small starter preset bank and original module-inspired performance screen.
- Validate audio, stability, CPU and memory on emulator and physical FM-1.

### Milestone 2 — Resonator and granular depth
- Add resonator models and excitation choices; bring up RINGS A and RINGS B as separate instances and validate simultaneous operation.
- Add granular texture, freeze and buffer controls.
- Add safe routing options and preset persistence.

### Milestone 3 — Modulation and generative performance
- Add envelopes and LFOs.
- Implement Marbles-style random pitch/voltage and trigger behaviour.
- Add a separate arpeggiator and conventional step sequencer.
- Expose assignable modulation destinations.

### Milestone 4 — Additional engines and effects
- Add the six-operator FM engine and other oscillator sources.
- Add filtering, dedicated reverb, delay, chorus and distortion.
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