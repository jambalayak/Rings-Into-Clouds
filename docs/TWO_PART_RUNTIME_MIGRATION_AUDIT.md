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


## Existing regression-test coverage audit

Inspected `tests/project_test.c`, `tests/fun10_test.c`, `tests/seq155_test.c` and `tests/motion_test.c`.

Already covered and therefore important to preserve:

- `project_test.c` verifies old FUN2/FUN3 Track 4 GM drums become part 4 / DRUM, and checks old drum levels, grid conversion, legacy PHYS/SAMPLE drum conversions, FUN5/FUN6 compatibility, FUN8/FUN10 parameter migration, FM6 patch placement and motion-event migration.
- `fun10_test.c` checks the 3840-byte FUN10 layout, four-lane song-chain serialization, four-track motion records, MIDI IN TRACK serialization and routing, and older FUN6/FUN7/FUN8 conversions.
- `seq155_test.c` exercises song-chain sections, silent lanes, boundary transitions, sequencer conditions, drum-grid behavior and MIDI program changes.
- `motion_test.c` exercises motion capture, shared event capacity, project round trips, legacy motion IDs and song-chain automation.

New tests required for the two-part architecture (not currently demonstrated by those existing four-part assertions):

1. Import a current FUN10 project with distinct sounds/patterns on all four tracks. Verify live Rings receives only old Track 1, live Drums receives old Track 4, and old Tracks 2/3 are not rendered or mapped onto either live part.
2. Repeat with a pre-1.0 project (`parts == 0`) where Track 4 is the legacy GM drum lane; verify drum grid, kit defaults, level and preserved step timing.
3. Verify current four-part FUN10 data (`parts == 4`) and old GM-drum projects both migrate correctly without changing the serialized byte layout or checksum rules.
4. Exercise every song-chain row combination for the two active mapped lanes, including either/both silent, and confirm inactive legacy lanes cannot become the section clock or emit notes.
5. Verify song-chain snapshots pull old Track 1 and Track 4 from each project, not project tracks 1 and 2 by accident.
6. Test motion events and locks encoded for all four old track indices. Only the mapped Rings and Drums events may play; inactive Track 2/3 events must not be reassigned.
7. Verify MIDI IN TRACK assignments for old Tracks 1 and 4 map to the two live destinations, while old Tracks 2/3 remain inert. Test block routing, OMNI/OFF and program changes.
8. Assert the live runtime has exactly two track objects and two engine-memory regions, while all serialized project structures and fixed FUN10 size/offset assertions remain unchanged.
9. Add a regression test proving the Rings part remains Rings and the drum part remains DRUM after project load, autosave restore, project save/reload and chain playback.

The existing tests are strong on the old four-track format; they do not yet establish the new two-part runtime mapping.


## Follow-up source trace: project capture/restore and section execution

A second pass traced the concrete runtime boundary in `firmware/src/project.c` and `firmware/src/song_chain.c` (branch `rings-two-part-rings-drums-exp`).

### Project capture and restore are currently identity-mapped four-track operations

- `project_capture()` serializes `trk[i]` into `p->t[i]`, serializes each `fm6_patch[i]`, and copies all four `song.mch[i]` channel assignments. It writes `parts = NPART`.
- `project_restore_runtime()` validates and migrates the project, then iterates all four indices. For each index it restores the engine request, parameters, preset, steps and FM6 patch into `trk[k]`; it also restores `song.mch[k]`.
- The selected track is restored from `p->sel` against `NTRK`, so a future two-part UI selection must not reuse this old index directly without translating it.
- Legacy GM drums are normalized by `proj_drums_to_part()` before restore. That function still writes project record 3 (old Track 4), not a live runtime slot.
- Save, rename, erase, slot summaries and autosave-related capture still treat the serialized four-track project as the source of truth. The safe boundary is therefore a conversion between a four-track project object and two live runtime parts—not shrinking project structs.

### Song-chain execution requires a lane projection, not just a smaller array

- `chain_apply()` currently calls `seq_release()` and `motion_restore()` for every live `trk[i]`, then assigns each runtime track the same-index slot from the four-lane row and the corresponding source snapshot.
- `chain_start()` and `chain_stop()` save/restore timing and quantize for every runtime track. `chain_tick()` uses `chain.clk`, which currently comes from the first non-silent stored lane.
- `chain_clock()` scans all four row lanes and returns the first non-silent lane; if every lane is silent it returns index 0. This legacy behavior cannot be retained unchanged when the only live parts are old Track 1 and old Track 4: old Track 2 or 3 must never become the section clock, and the all-silent fallback must be the Rings lane (or the defined fixed silent-bar clock).
- `seq_steps()` indexes the chain source with the runtime track pointer's index. Once runtime indices become 0=Rings and 1=Drums, source steps/timing/motion must be fetched from serialized indices 0 and 3 respectively.
- Stored chain rows and source projects must remain four-lane/four-track in the compatibility representation. The runtime projection must translate the two active lanes and force the other two lanes silent without rewriting the saved row or snapshot.

### Safe implementation boundary now established

The mapping helpers added to `core.h` are only a declared contract. They are not yet used by project capture/restore, song-chain preparation/execution, MIDI routing or motion playback. The runtime still has four `trk[]` objects and four engine-memory slots. Do not reduce `NPART` or `NTRK` until the projection is wired through every consumer and covered by host tests.

No runtime behavior or serialized format changed in this follow-up audit.


## Follow-up implementation gate: serialization shadows, song clock, and build budget

The concrete restore path adds an important constraint beyond the earlier mapping summary.

### Project loading and saving need an explicit four-track compatibility image

- `project_restore_runtime()` first runs all legacy conversions on a complete four-track `project_t`, then restores every track, all four FM6 patches, all four MIDI channel assignments, and the selected-track index.
- `project_capture()` currently serializes all four live tracks and all four FM6 patches directly. When the live runtime becomes two parts, it cannot keep doing this by index: live part 1 is old project Track 4, not project Track 2.
- A two-part runtime therefore needs a deliberate project compatibility image:
  - serialized record 0 is populated from live Rings part 0;
  - serialized record 3 is populated from live Drums part 1;
  - records 1 and 2 must follow a documented retirement policy (not copied from the wrong live part and not silently reinterpreted);
  - the saved selection must translate live Rings/Drums to serialized 0/3 and translate back on load;
  - MIDI channels and FM6 patch records must follow the same mapping, with inactive records set to safe defaults or retained in an explicitly bounded compatibility store.
- This policy must be decided and tested before changing `project_capture()`. Simply mapping live indices in the restore loop is insufficient: autosave, project save/reload, new-project defaults and project summaries all share the four-record representation.
- The legacy Track 4 GM-drum conversion must remain in the import layer before projection, so the old lane is normalized as DRUM and then copied to live part 1.

### Song-chain runtime projection requirements

- The stored FUN10 row is still four lane bytes plus repeat. The runtime needs to project row lane 0 to Rings and lane 3 to Drums; runtime lanes 1/2 must always be silent.
- The chain clock must be selected only from the active legacy lanes 0 and 3. If both are silent, use the defined fixed silent-bar clock (Rings lane timing) rather than allowing old lane 1 or 2 to drive the section.
- Chain source snapshots must project project tracks 0 and 3 into runtime tracks 0 and 1 for steps, timing, quantize, motion and locks.
- `chain_start()` / `chain_stop()` must save and restore only the two runtime timing records after the array shrinks; the serialized chain config and project snapshots remain four-track.
- The existing four-track chain implementation is internally consistent today; no live projection has been applied yet.

### CI result for run 46142538236

The workflow is **not green**:
- Target ABI smoke probe, Rings/Clouds compile-only step, compact-delay host evaluation, and firmware regression-test build completed.
- Host regression suite was marked cancelled, so it provides no pass result for this run.
- The optional compact-effects golden-render/artifact steps failed.
- The diagnostic firmware link exposed the already-known size constraints: image 595,920 B exceeds the app slot; `.data + .bss` is 90,836 B against 73,728 B (17,108 B over). POOL is 351,472 B of 368,640 B, leaving 17,168 B.
- Rings/Clouds symbols were retained in the diagnostic link (Rings Part 110,384 B, Strummer 524 B, Clouds processor 8,684 B, large buffer 86,144 B, small buffer 32,768 B). This is a diagnostic, not a release build.

The two-part runtime should eventually reduce per-track RAM and engine POOL allocation, but the build must be remeasured after each step. The two-part reduction alone is not yet proven to solve the 17,108 B ordinary-RAM overage or the flash image overage. Keep full Rings quality and all five models; solve the budget through measured removal of non-Rings engines/state, not by weakening Rings DSP.
