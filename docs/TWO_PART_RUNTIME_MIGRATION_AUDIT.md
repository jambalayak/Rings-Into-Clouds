# Two-part runtime migration: source audit

Branch: `rings-two-part-rings-drums-exp`
Audit baseline: `aac3432bbad17483c20a2d0ac5e8139e6a987d4d`
Status: source inspection only; no runtime code changed.

## Confirmed source layout

The firmware source is under `firmware/src/`, not `src/`.

### Shared counts are coupled today

In `firmware/src/core.h`:

- `NPART` is 4 and is documented as synth parts / Tracks 1..4.
- `NTRK` is defined as `NPART`, with an explicit comment that formats and protocol count the same tracks.
- `C1_NP` derives from `NPART` and sizes second-core per-part state.
- `chain_row_t.slot` is `slot[NTRK]`; song-chain lane count is therefore four.
- `track_t` contains substantial per-part runtime state. The global live track array and all consumers must be audited before reducing its length.

In `firmware/src/engines.c`:

- `eng_mem[NPART]` allocates one engine-memory region per part in POOL.
- `eng_mem_owner[NPART]` and `ENG_MEM(p)` use the same part index.
- `snd_said[NTRK]` is per track.
- `TRK_DEF[NPART][3]` defines four power-on parts: ANALOG, FM6, LOFI, DRUM.
- Engine browsing and engine IDs are append-only protocol / preset identifiers. Removing melodic engines must not renumber these IDs or break old preset/project conversion.

### Project formats are explicitly four-track formats

In `firmware/src/project.c`:

- Current `project_t` contains `t[NTRK]`, `fm6[NTRK]`, and `mch[NTRK]`.
- Historical FUN5/FUN6 structs and FUN1..FUN4 readers also declare `t[NTRK]`; their byte sizes and offsets are frozen.
- FUN10 stores a four-lane song-chain configuration and motion data. The format comments calculate fixed offsets and reserved bytes from four tracks.
- The project header's `parts` byte currently means `NPART`; zero identifies the old layout where Track 4 was the GM drum part.
- `proj_drums_to_part()` operates on `q->t[NTRK - 1]`, and skips conversion when `q->parts == NPART`. It converts the legacy GM drum data in Track 4 to the DRUM engine while preserving its pattern and relevant mix settings.
- `project_restore_runtime()` copies all four project records, MIDI assignments and chain lanes into the four live `trk[]` parts.
- `project_save()` and project defaults iterate over all `NTRK` records.

Consequently, changing either `NPART` or `NTRK` to 2 in place would alter current struct sizes, frozen legacy readers, FUN10 offsets, project checksums, song-chain storage, MIDI arrays and engine-memory allocation. It is not a safe first patch.

### Song chain is four-lane at runtime

In `firmware/src/song_chain.c`:

- Each chain source stores `step[NTRK][NSTEP]`, per-track timing and quantize.
- Each row has one slot per `NTRK` lane.
- `chain_apply()`, `chain_start()`, `chain_stop()` and `chain_tick()` iterate/index all tracks.
- `seq_steps()` selects a saved source slot for the current track index.
- `chain_prepare()` copies every track from each referenced project.

The live two-part mapping must be applied consistently to both the active sequencer lanes and chain snapshots. Merely making the UI display two tracks would leave hidden tracks consuming memory and potentially sequencing.

## Migration hazards to address before changing runtime arrays

1. **Legacy Track 4 drum conversion:** currently it converts the last project record in place. The new live mapping must explicitly copy legacy project Track 4 to live part 1 (Track 2), and legacy Track 1 to live part 0. It must not assume project Track 4 is still live index 3.
2. **Current-format projects:** projects with `parts == 4` already contain four live parts, with Track 4 normally being DRUM. Projects with `parts == 0` use the older GM drum convention. Both cases need defined import behavior.
3. **Inactive Tracks 2 and 3:** do not map their synth sounds onto Rings or silently discard their saved data during import. Preserve them in the four-record project representation where possible; make them inactive/silent in the new runtime.
4. **Song-chain rows:** preserve the four stored lane values, but translate the two supported live lanes. The new runtime should read old Track 1 for Rings and old Track 4 for drums; inactive legacy lanes must be silent, including their section-clock behavior.
5. **MIDI routing:** preserve the four serialized channel assignments and define the live mapping explicitly. Verify both block routing and per-track routing, including old project defaults.
6. **Motion / automation:** motion events encode a track index in `place >> 6`. Import and chain snapshots must translate or suppress inactive lane events without accidentally applying Track 2/3 automation to Rings or drums.
7. **Engine memory and second core:** only after the runtime array is genuinely two parts should `eng_mem`, `eng_mem_owner`, `C1_NP`, render loops and related state shrink. Verify all pointer/index calculations against the new live count.
8. **Preset and engine compatibility:** retain stable engine IDs and legacy conversion paths. Remove non-Rings melodic DSP only after all project, user-preset, factory-preset and protocol paths have been tested.

## Recommended next implementation sequence

1. Introduce explicit constants for the four-record project/protocol layout and the two-part live runtime. Do not redefine the existing frozen format count.
2. Add a single documented mapping helper for live part -> project track (0 -> 0 / Track 1 Rings; 1 -> 3 / Track 4 Drums), plus the inverse mapping where required.
3. Add host tests for old GM-drums projects, current four-part projects, empty/default projects, all four MIDI assignments, motion events and all song-chain lane combinations.
4. Route project restore, save, autosave and chain preparation through that mapping while keeping serialized FUN1..FUN10 byte layouts unchanged.
5. Only then reduce the live `trk[]` array, engine-memory regions and second-core state to two parts; compile and run all host regressions.
6. Finally, remove non-Rings melodic engine build/UI code behind the compatibility boundary, retaining stable IDs and conversion code.

## Validation gate

Do not change the FUN1..FUN10 struct definitions, offsets, magic values, checksums or fixed-size assertions as part of the live-part-count change. Require round-trip tests for all supported formats, legacy Track 4 drum migration tests, song-chain tests, MIDI/motion tests, sequencer regression tests, target RAM/POOL/flash diagnostics and full CI before considering this architecture complete.

No firmware behavior, project format or binary was changed by this audit.
