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
