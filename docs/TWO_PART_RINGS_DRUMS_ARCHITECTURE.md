# Two-part Rings + Drums architecture

## Product target

- Part 1 / Track 1: one authentic Mutable Instruments Rings instrument.
- Part 2 / Track 2: the dedicated eight-lane DRUM engine.
- Marbles remains a sequencer / modulation source for Rings; it is not an audio part.
- Clouds remains an optional, bypassable processor for Rings; it is not an audio part.
- No other melodic synth engines are selectable or built into the final instrument.

## Compatibility strategy

The existing firmware deliberately uses `NTRK = NPART = 4` for live parts, project records, MIDI routing, and song-chain lanes. The FUN10 project layout serializes four track records and four MIDI channel assignments. Do not simply change `NTRK` to 2: that changes serialized structure sizes and breaks the frozen project formats.

Separate the concepts:
- Keep a frozen four-lane storage/protocol count for reading and writing existing FUN1..FUN10 projects.
- Introduce an explicit two-part live-performance count / mapping.
- Live part 0 maps to Rings.
- Live part 1 maps to Drums.
- On project import, migrate the old Track 4 drum part to live Track 2; keep the old Track 1 pattern and settings as the source for Rings where valid.
- Ignore or preserve inactive legacy Tracks 2 and 3 without rendering them. Never silently reinterpret their sound as Rings.
- Convert song-chain rows and per-track MIDI routing through the same mapping. Preserve four-slot project storage and make unsupported/inactive legacy lanes explicitly silent.
- Save projects in a backward-compatible form only after the migration and round-trip tests prove the mapping. If the existing FUN10 format cannot represent the two-part mapping safely, introduce a versioned format rather than changing FUN10 in place.

## Memory and build strategy

- Reduce active audio-part count and per-part engine memory only after all live loops use the active-part count.
- Keep Rings DSP, all five Rings models, original decay and resonator quality intact.
- Keep the full drum engine.
- Remove non-Rings melodic engine DSP, tables, factory presets and selection UI from the target image only after confirming no project importer, preset converter, protocol, or host test depends on their symbols. Retain migration code / stable engine IDs where needed.
- Marbles and Clouds allocations are handled independently; neither is removed to save track memory.
- Do not assume a bypassed Clouds processor releases its allocated buffers.

## Required validation

1. Host project round-trip tests for FUN1..FUN10, including old Track 4 drum projects.
2. Song-chain tests for all slot/silent-lane combinations and section transitions.
3. MIDI input/output routing tests, including old channel assignments and drum-grid input.
4. Sequencer, recording, probability, conditions, ratchets, nudges, automation and parameter-lock regression tests.
5. Rings model / audio regression tests and drum regression tests.
6. Target linker diagnostics for ordinary RAM, POOL and flash; compare against the current baseline.
7. Full CI on this isolated branch. No merge or promotion without explicit approval.

## Current status

This branch is an architecture checkpoint only. No runtime code or project format has been changed yet. The main risks identified are the shared four-track live/storage constant and the historical Track 4 drum migration.