# M0 Engineering Audit — 2026-11-25

Branch: `rings-into-clouds-dev`

## Confirmed base architecture

- The repository is a fork of Felucca for the M-VAVE FM-1. The firmware is a single compilation unit assembled in `firmware/src/felucca.c`; include order is significant.
- The base currently identifies itself as Felucca 1.8.3 in its README and firmware version macros.
- Hardware support and engine DSP are separate git submodules:
  - `firmware/engines` → `hugelton/Felucca-Engines`, pinned at `1fa016b9702a76e2767b2bd9f108333f7c46e592`.
  - `firmware/bsp` → `hugelton/felucca-bsp`, pinned at `9670b5d34082700d0a7413eb6264abe1756c0ece`.
- The project builds the FM-1 target package `felucca.fwsc`; it is not a generic desktop firmware build. The documented full build requires the JieLi toolchain and AC79 SDK. The browser demo is an emulator and does not emulate USB, TRS MIDI, updates, or user sample slots.

## Audio path and hard constraints

- Audio is rendered by the FM-1 ALNK0/I2S interrupt. The current sample rate is approximately 44.1 kHz.
- `HALF_FRAMES` is 128 and `CTL`-sized blocks are rendered inside each half-buffer interrupt. The comments in `audio.c` describe the real-time path.
- `mix_block` in `fx.c` processes events, synth parts, per-track effects, sends, shared buses and master output.
- There are four synth parts (`NPART=4`) but a shared total sounding-voice budget of eight (`NVOICE=8`). This is a global budget, not eight voices per part.
- An optional second core is already supported, but is a menu-selectable beta feature and defaults OFF at runtime. It must not be assumed available for the new engine's worst-case budget.
- The audio ISR already has overload detection and voice shedding. This is a safety net, not spare DSP capacity.
- Existing effects already allocate substantial shared delay/reverb buffers. Engine state is allocated from a per-part union pool in `engines.c`, with `ENG_MEM_PART=12888` bytes (or 13344 with ADPCM enabled). New per-engine state must be measured against this compile-time limit.
- Existing host CPU baselines and target disassembly budgets are in `tests/cpu_baseline.txt` and `tests/target_budget.txt`. Existing engine costs vary substantially; GRAIN's target render loop is notably expensive. New DSP must be benchmarked rather than assumed to fit.

## Relevant existing capabilities

- The firmware already has GRAIN, a granular engine over built-in/user sample sets, with bounded grain scheduling, seek indexes and reverse windows. It is a useful reference for Clouds-like granular behaviour, but it is not a substitute for a full Clouds port.
- PHYS provides physical-model voices and is a useful reference for resonator-like sound design, but it is not Mutable Instruments Rings.
- The firmware already has FM6, modulation routing, LFOs, envelopes, a four-part sequencer, MIDI, chord keys, insert effects, chorus, delay and multiple reverbs.
- Engine IDs are persisted in presets/projects and in the editor protocol. New engines must be appended; existing IDs must never be reordered or repurposed.
- Preset browsing order is explicitly maintained in the engine table/order. UI changes must preserve the editor protocol and existing preset compatibility.

## Initial implementation decisions

1. Do not replace or reorder the existing engines.
2. Add new engine IDs only at the end of the engine table and update all engine-count, menu, preset, editor and regression-test paths together.
3. Start with a single-voice/small-polyphony Rings-inspired resonator prototype and a conservative granular processor. Profile each separately, then profile the combined path.
4. Reuse the existing modulation, envelopes, MIDI, keyboard, preset and sequencing infrastructure wherever practical.
5. Prefer a switchable insert/processor path over an always-on global effect initially. Include an explicit bypass and safe default levels.
6. Keep new DSP state within the engine memory pool where feasible; if it cannot fit, make a documented memory-budget change only after checking linker sections and total RAM.
7. Do not enable second-core-only DSP assumptions. The instrument must degrade gracefully on the one-core path.
8. Preserve a clean fallback preset/engine and verify the boot/update path after any build-affecting change.

## Current blockers / items requiring later target validation

- The FM-1 hardware is required to validate actual CPU headroom, audio stability, physical controls, display legibility, MIDI and update/recovery. Host tests and the browser demo cannot prove these.
- A full target build cannot be claimed from GitHub inspection alone; it needs the documented JieLi toolchain and AC79 SDK.
- Exact imported source revisions and licences for Rings/Clouds/Beads (and any sequencer references) must be recorded before importing code. The UI should be an original interpretation and must not copy proprietary graphics or panel artwork.

## M0 outcome

The existing firmware already contains several useful building blocks, but Rings + Clouds should be integrated as new, independently testable DSP components. The primary technical risks are real-time CPU cost, engine-state RAM, and compatibility of persisted engine IDs—not the basic audio/MIDI plumbing.
