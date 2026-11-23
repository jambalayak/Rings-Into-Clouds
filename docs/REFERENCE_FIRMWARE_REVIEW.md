# Reference firmware review

## Executive finding

FM1_Locus is the strongest existing FM-1 reference for the first RINGS INTO CLOUDS sound path. It contains Emilie Gillet's original Mutable Instruments Rings and Clouds DSP, sourced from fixed upstream commits, and demonstrates a working firmware architecture around both processors.

It is a reference and potential DSP source, not a ready-made modular platform. Its author explicitly says the project has been exercised in a host simulator and FM-1 emulator but not yet on a physical FM-1. RINGS INTO CLOUDS must independently build, test and validate any integration.

## FM1_Locus: what it provides

Repository: https://github.com/stevexfer/FM1_Locus

Relevant source:

- firmware/apps/locus/locus_engine.cc — Rings Part and Strummer, Clouds GranularProcessor, resampling, routing, FIFOs and dual-core scheduling.
- firmware/apps/locus/app.c — FM-1 controls, pages, parameter handling, MIDI, storage and graphics.
- firmware/apps/locus/locus.h — shared parameter and view definitions.
- third_party/eurorack/rings — original Rings DSP.
- third_party/eurorack/clouds — original Clouds DSP.
- third_party/eurorack/stmlib — required Mutable Instruments support library.
- third_party/eurorack/PATCHES.md — exact source commits and FM-1-specific changes.

The documented upstream DSP revisions are:

- Rings and Clouds: pichenettes/eurorack commit 08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4.
- stmlib: pichenettes/stmlib commit d18def816c51d1da0c108236928b2bbd25c17481.

The documented Rings implementation runs at the FM-1 codec rate (about 48.0769 kHz), with a small source patch to use the actual clock. Clouds runs at about 32.051 kHz and is connected through a 3:2 polyphase resampler. The reference uses separate static memory for Rings, Clouds and their buffers, and prepares the expensive Clouds state outside the audio interrupt.

Its signal path supports resonator input, resonator-to-granular processing, USB audio routing, direct outputs and level-controlled parallel paths. It also provides a useful display concept: waveform, grain positions, playhead and recording-window visualisation.

## Limitations and caveats

- The reference is a fixed two-processor instrument, not an arbitrary module graph.
- It does not contain Beads, Ripples, Peaks, Marbles, Yarns or Plaits as full module implementations.
- The Rings string-and-reverb model and its 64 KB reverb are omitted to make room for granular buffers.
- The Rings Disastrous Peace Easter egg is removed.
- Clouds' processing rate conversion introduces documented latency and high-frequency trade-offs.
- Its CPU figures are emulator measurements, not physical-device measurements.
- The reference README explicitly says it has not yet been tested on a physical FM-1.

These are documented design choices, not reasons to discard the project. They must be carried into our fidelity and resource tracking.

## Relationship to the current RINGS INTO CLOUDS base

RINGS INTO CLOUDS currently uses the full Felucca-derived firmware tree rather than FM1_Locus's smaller app-oriented platform. This gives the project an established four-part voice engine, sequencer, FX buses, UI and storage, but its current architecture is different from Locus.

The most useful approach is therefore selective integration:

1. Keep the current Felucca-derived platform and its existing instrument features as the base.
2. Vendor the exact Rings, Clouds and stmlib source revisions from FM1_Locus, preserving their MIT notices and patch history.
3. Port the DSP integration layer into the current build system; do not copy Locus's entire platform or assume its app API is compatible.
4. Reconcile its audio scheduling and dual-core assumptions with the current audio ISR, second-core fallback and block size.
5. Allocate Rings and Clouds state explicitly; do not put simultaneous module state into the existing per-part engine-memory union.
6. Keep the first Rings-to-Clouds path as a dedicated, testable subsystem before generalising it into the modular graph.
7. Re-run source-level, host render, sanitizer, memory and target timing tests after each integration step.

## Other useful references

### GATOR

Repository: https://github.com/npi3pak/fm1-gator

GATOR is a Plaits-inspired FM-1 macro-oscillator firmware. Its README documents 24 synthesis models and a modulation matrix. It is the strongest reference for a Plaits-family oscillator port and its model-selection/control approach. The 24-model set should not be confused with Plaits' original 16 models; each implementation must be checked against the exact upstream Plaits revision and mode list.

### Jangada

Repository: https://github.com/zednaked/jangada

Jangada is useful for advanced FM-1 UI, modulation, sequencer, visualiser and second-core techniques. Its code and documentation are a reference for platform features and interaction design, not a substitute for the original Mutable DSP.

## Recommended source strategy

| Module | Primary source strategy |
|---|---|
| Rings | Start from the exact original DSP already ported in FM1_Locus; restore omitted features only if memory and CPU allow |
| Clouds | Start from the exact original DSP already ported in FM1_Locus; retain its sample-rate and buffer requirements unless validated otherwise |
| Beads | Port from its own original upstream source; do not treat Clouds plus reverb as Beads |
| Ripples | Port its original filter DSP and verify each filter mode and response |
| Peaks | Port the original envelope/LFO algorithms and trigger behaviour |
| Marbles | Port original random, quantisation, clock and gate algorithms; adapt outputs to FM-1 control/event routing |
| Yarns | Port original sequencing/MIDI behaviour where hardware I/O supports it |
| Plaits | Use GATOR as an FM-1 integration reference, but compare against the original Plaits 16-model source and preserve exact model identity |

## Licensing

FM1_Locus identifies Rings, Clouds and stmlib as MIT-licensed and preserves their source commits and patch notes. RINGS INTO CLOUDS must carry the corresponding copyright and licence notices for any source it adopts, alongside the GPL-3.0-only obligations of its Felucca-derived platform. Do not copy code without its notices or assume all code in a reference repository shares one licence.

## Status

This is a source and documentation review. No FM1_Locus code has been copied into RINGS INTO CLOUDS, no module has been integrated, and no physical FM-1 validation is claimed.


## Deeper FM1_Locus adapter review (2026-11-23)

Reviewed the current upstream `main` implementation at `stevexfer/FM1_Locus` (tree commit `3d92fde385db83a36d746e2e916fb454a362277e`), especially `firmware/apps/locus/locus_engine.cc`, `locus.h` and `app.c`. This supplements the pinned third-party Rings/Clouds source review above; the Locus application source itself is a moving reference and must not be copied without pinning its exact commit.

### Rings setup and processing patterns worth retaining

- Locus owns exactly one persistent `rings::Part` and one persistent `rings::Strummer`, each constructed in statically reserved aligned memory with placement new. `Part::Init(NULL)` and `Strummer::Init(0.01f, rings::kSampleRate / rings::kMaxBlockSize)` are performed during engine initialization.
- The part is configured with `set_model()`, `set_polyphony()`, then `Configure()`. Locus explicitly notes that a four-voice configuration can take about 2 ms because filter initialization performs expensive tangent calculations. Therefore model/polyphony changes must be staged outside the hard audio deadline and never triggered unexpectedly in a sample callback.
- Locus uses 24-frame Rings blocks. Its 48-frame tick calls Rings twice, at offsets 0 and 24. The strummer is processed for each block before `Part::Process`.
- A block-level `PerformanceState` is assembled with `internal_exciter`, `internal_strum`, `internal_note`, `tonic`, `note`, `fm`, and chord. A sequencer or queued event sets a one-shot strum; accent raises brightness for that event. Explicit strums are preserved even if the Strummer does not independently detect an onset.
- Locus uses a 16-entry bounded event queue for main-loop-to-audio events. The queue carries strum/grain/accent flags and a note; overflow drops new events. Our adapter should preserve bounded event delivery but use the richer per-track note lifecycle already specified for Felucca, not copy this simplified event format as a substitute.
- Continuous controls are smoothed toward targets at 5% per tick; discrete model/polyphony/excitation/mode/quality/freeze controls are applied immediately. This is a useful starting policy, but smoothing coefficients must be expressed in time constants at the actual FM-1 control rate, not copied blindly.
- Locus mixes Rings' two outputs independently: `Part::Process` produces `out` and `aux`; the routing stage can send these to Clouds or directly to left/right outputs. This reinforces that a mono-only Felucca `post()` callback is insufficient for full stereo/aux fidelity.

### What must not be copied as if it solved our architecture

- Locus contains one global Rings Part and one Strummer, not two independently stateful Rings modules. It does not satisfy the RINGS A / RINGS B requirement.
- Its selectable Rings polyphony is 1, 2 or 4 internal resonator voices for that one Part. That is not the same as two independent Parts, and does not provide independent model/patch/excitation state.
- Its audio engine uses a fixed 48-frame tick, 24-frame Rings blocks and a 32-frame Clouds block at two-thirds sample rate. The Felucca base has a different audio rate and 128-frame half-buffer; this scheduler and resampler are reference algorithms, not drop-in timing constants.
- Locus uses a second-core batch pipeline with two batch buffers, input/output FIFOs and roughly one tick of added latency. Felucca's CPU2 ownership and current audio callback must be audited before adopting any dual-core split.
- Locus's Rings note model is sequencer/strum-centric: `last_note` is retained and updated on strum events. It does not demonstrate the full independent host note-on/off, voice-steal and release semantics required for two FM-1 tracks.

### RINGS A/B implementation implications

The first implementation should create two explicit per-instance runtime records, each containing its own aligned `rings::Part`, `rings::Strummer`, `PerformanceState`, `Patch`, event mailbox, excitation scratch, stereo out/aux scratch, configuration cache and diagnostics. Initialization and any `Configure()` work must be scheduled outside the audio interrupt. The records must not alias Locus-style singleton globals.

A shared helper may implement identical DSP processing for both instances, but all mutable state and buffers must be distinct. Tests must process different notes/models/parameters in A and B at once, then prove changing one instance does not change the other's output/state. The shared FM-1 voice ceiling remains eight; the Rings Parts' own internal polyphony settings must be budgeted independently and reconciled with that ceiling rather than simply multiplying voice counts.

The Locus reference is valuable evidence that Rings' two-output processing, Strummer sequencing, event-triggered excitation and out-of-interrupt reconfiguration are practical on FM-1. It is not evidence that two Parts plus Clouds fit the current Felucca memory/CPU budget.
