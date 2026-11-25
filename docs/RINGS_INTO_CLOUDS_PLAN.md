# RINGS INTO CLOUDS — Development Plan

RINGS INTO CLOUDS is an independent M-VAVE FM-1 firmware project based on the Felucca hardware platform. The aim is a playable hybrid instrument, not a visual mock-up.

## Product direction

- Core voice: Mutable Instruments Rings-inspired resonator synthesis feeding a Clouds-inspired granular processor.
- Playability: immediate preset selection, chromatic keyboard input, MIDI input, and hands-on parameter control.
- Generative layer: a Marbles-inspired probabilistic sequencer and a Yarns-inspired arpeggiator.
- Modulation: Peaks-inspired envelopes/LFOs and assignable modulation routing.
- Tone shaping: Ripples-inspired multimode filtering.
- Effects: Beads-inspired granular/time effects.
- Additional engines: optional hidden six-operator DX-style FM and Disastrous Peace-inspired experimental engine.
- Sequencing: retain a conventional step sequencer alongside generative modes.

Names describe functional and sonic references. Implementations must be original ports/reimplementations or properly licensed code; do not copy proprietary artwork, trademarks, or assets. Preserve all upstream and third-party licence notices.

## Interface direction

Create an original visual language inspired by Mutable Instruments' modular-panel design: clear module groupings, strong typographic hierarchy, purposeful colour coding, compact parameter labels, and graphic signal-flow motifs. Keep the FM-1 screen readable and controls discoverable. Do not reproduce Mutable Instruments artwork or panel layouts verbatim.

## Architecture principles

1. Preserve the FM-1 hardware support, boot/update path, storage, MIDI, and audio plumbing from the Felucca base.
2. Keep the upstream base isolated from new instrument code where practical; use small, reviewable changes.
3. Build DSP modules behind explicit interfaces so the Rings voice, Clouds processor, filters, modulation, and sequencers can be tested independently.
4. Treat CPU, RAM, flash, voice count, latency, and audio stability as hard constraints. Profile each DSP stage on the target before enabling combinations by default.
5. Keep a known-good bootable build and test path throughout development.

## Milestones

### M0 — Baseline and build reproducibility
- Record the upstream commit and submodule revisions.
- Confirm the existing build and host regression tests.
- Identify audio callback, voice allocation, parameter, preset, MIDI, UI, and memory-budget interfaces.
- Keep upstream firmware behaviour available as a fallback.

### M1 — First playable instrument
- One Rings-inspired voice with keyboard/MIDI note control.
- Clouds-inspired processing in the audio path with safe bypass and conservative CPU settings.
- Small preset bank and persistent user preset support.
- Minimal dedicated UI pages for voice, processor, and output.
- Host tests plus target build validation.

### M2 — Performance controls
- Add modulation assignments, envelopes/LFOs, filter, and performance macros.
- Add clear preset browsing and parameter feedback.

### M3 — Sequencing
- Add the conventional step-sequencer workflow.
- Add Marbles-inspired generative sequencing and Yarns-inspired arpeggiation as selectable modes.

### M4 — Extended sound engines and effects
- Add Beads-inspired effects and experimental engines, including DX-style six-operator FM and the Disastrous Peace-inspired engine, only after profiling and interface stability.

### M5 — Hardware validation and release
- Validate audio stability, control mapping, storage, MIDI, preset compatibility, update/recovery, and screen readability on a physical FM-1.
- Publish reproducible build instructions, licence inventory, release notes, and recovery guidance.

## Immediate engineering audit

Before changing the audio engine, inspect:
- `firmware/src/` application and audio entry points
- `firmware/engines/` engine interfaces and submodule revision
- `firmware/bsp/` FM-1 audio, controls, display, storage, and update interfaces
- `tests/` regression and CPU-budget baselines
- `assets/` fonts, icons, samples, and their licences

Do not assume desktop/browser emulation proves target performance. The physical FM-1 is the final authority for CPU headroom, audio stability, and control feel.

## Licensing and attribution

The upstream Felucca code is GPL-3.0-only. Its engine and board-support submodules retain their own licences. Any imported Mutable Instruments code must retain its applicable licence and notices; verify the exact source and licence of each module before integration. Keep a per-component attribution record and do not copy artwork or sample assets without compatible permission.
