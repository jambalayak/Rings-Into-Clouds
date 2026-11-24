# Engine-switch regression investigation

## Current evidence

Run 127 (commit `c1112fd`) completed its target build and diagnostics but the host regression suite failed. The 91-render suite reports 90 changed renders, zero missing renders, zero health failures, zero voice/routing failures, zero CPU-budget overruns and zero crashes. The independent Felucca-Engines suite passes all 122 renders, and the second-core comparison passes all 28 scenes. Those passing suites do not prove the integrated track/voice/mixer path is unchanged.

Run 129 completed the target build, pinned Rings/Clouds compile-only check, compact delay-line host comparison, and lean memory-diagnostic build. The host regression suite failed; the development firmware artifact was skipped. Its 720-sequence diagnostic reported:
- Primary-only: `965688b3e43bf1a2`
- Companion-only: `c8cb0cbd59d79e85`
- Combined: `286fa5c353bb683c`
- Primary with companion muted at mix: `1bc06573a8f3d20b`
- Companion with primary muted at mix: `b25689dc07667bcf`

The muted-track fingerprints differ from the corresponding isolated fingerprints. This establishes that continuing to render the other part changes the audible mix even when its own output level is zero. It does not yet establish whether the mechanism is voice stealing, shared engine memory, global modulation/random state, or another shared resource.

The source supports shared voice-budget interference as a concrete candidate: `firmware/src/voice.c` counts active voices across all three parts in `voices_busy()`; `voice_room()` and `voice_alloc()` can select a victim from another part and call `voice_kill()`. A muted track still creates voices and participates in this allocator. This makes cross-part voice stealing a plausible explanation for the changed muted-track fingerprints, but a targeted counterfactual test is still required before calling it the root cause.

The host suite also reports UI checks failing across SONG row/lanes, FX key handling and LEDs, knob/page behavior, and help text. These failures must be investigated separately from the audio engine-switch hashes; do not assume they share one cause.

## Test structure and interpretation

The engine-switch test is in `tests/union_test.c`. Its hash is the complete stereo mix, not the output of the part under test alone. Each sequence switches `trk[0]` through a pair or A→B→A sequence, and also changes the engine on `trk[2]` after every primary step:

```c
uplay(&trk[0], e[k], pi + k, 60, wait_ms);
uplay(&trk[2], UE[(k + 3u) % UNE], pi, 55, 10);
```

The muted variants keep both parts rendering and consuming shared resources; they mute only the mixer level. Thus the hash differences are evidence of cross-part influence, not proof that the mixer leaks a muted signal. The diagnostic hashes are fingerprints, not historical per-track 1.4 references.

## State-sharing hypothesis

`firmware/src/engines.c` keeps one engine-memory region per part. When an engine that needs that region claims it after another memory-using engine, the region is zeroed. Engines with no per-part memory leave the owner marker unchanged. This memory-saving design may not be bit-identical to retaining separate state arrays for every engine across switches.

A second concrete candidate is the global voice budget. `voices_busy()` totals active voices across all parts, and allocation can steal a held/released voice from another part. The next test should count kills by victim part and compare a sequence with the companion still rendering but prevented from allocating voices against the ordinary muted-companion sequence. Preserve identical primary notes, engine changes, wait times, and render duration. If preventing companion voice allocation restores the primary-only hash, shared voice allocation is implicated; if not, continue with shared engine-memory/global-state isolation.

The 1.4 reference hashes remain authoritative regression evidence until a controlled comparison explains the differences. Do not update `tests/union_golden.txt` merely to silence failures.

## Run 129 memory result

The lean target build (Slicer excluded) and linker diagnostics completed successfully despite the host regression failure. Prior baseline measurements are not proof that Rings and Clouds objects or their audio buffers fit. The exact Run 129 linker artifact should be inspected before quoting new memory figures. The development firmware artifact was correctly skipped because the host suite failed.

## Status

The original 1.4 golden files remain unchanged. Run 129 passed target ABI and pinned Rings/Clouds DSP compile-only checks, the compact Rings delay-line host comparison, the FM-1 firmware build, and lean memory-diagnostic build. It failed the host regression suite. No production Rings-to-Clouds audio integration exists yet; that remains a separate unfinished milestone.
