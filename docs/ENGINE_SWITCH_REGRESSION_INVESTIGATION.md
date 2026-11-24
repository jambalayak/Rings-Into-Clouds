# Engine-switch regression investigation

## Current evidence

Run 127 (commit `c1112fd`) completed its target build and diagnostics but the host regression suite failed. The 91-render suite reports 90 changed renders, zero missing renders, zero health failures, zero voice/routing failures, zero CPU-budget overruns and zero crashes. The independent Felucca-Engines suite passes all 122 renders, and the second-core comparison passes all 28 scenes. Those passing suites do not prove the integrated track/voice/mixer path is unchanged.

The host suite also reports 15 UI checks failing across SONG row/lanes, FX key handling and LEDs, knob/page behavior, and help text. These failures appear in repeated UI test configurations. They must be investigated separately from the audio engine-switch hashes; do not assume they share one cause.

The engine-switch test is in `tests/union_test.c`. Its hash is the complete stereo mix, not the output of the part under test alone. Each sequence switches `trk[0]` through a pair or A→B→A sequence, and also changes the engine on `trk[2]` after every primary step:

```c
uplay(&trk[0], e[k], pi + k, 60, wait_ms);
uplay(&trk[2], UE[(k + 3u) % UNE], pi, 55, 10);
```

Consequently, a changed hash cannot by itself identify whether the difference came from the primary part, the concurrently changing companion part, or their interaction in the shared voice budget and mixer.

## State-sharing hypothesis

`firmware/src/engines.c` keeps one engine-memory region per part. When an engine that needs that region claims it after another memory-using engine, the region is zeroed. Engines with no per-part memory leave the owner marker unchanged. This memory-saving design may not be bit-identical to retaining separate state arrays for every engine across switches.

The 1.4 reference hashes remain authoritative regression evidence until a controlled comparison explains the differences. Do not update `tests/union_golden.txt` merely to silence failures.

## Diagnostic results and next test

Run 127's first opt-in `UNION_DIAG=1` pass repeated the 720 sequence definitions in three independent renders and reported these aggregate hashes:

- Primary-only: `965688b3e43bf1a2`
- Companion-only: `c8cb0cbd59d79e85`
- Combined: `286fa5c353bb683c`

These are diagnostic fingerprints, not historical per-part references. A combined-vs-isolated difference is expected because the rendered arrangement differs, so these values do not identify a root cause.

The next diagnostic adds two controlled variants: both parts still render and consume the shared voice budget, but the companion is muted at the mix; then the primary is muted. Comparing each muted-companion result against primary-only, and each muted-primary result against companion-only, will test whether the other part's continued rendering/resource use changes the audible part. It still will not recreate historical per-part 1.4 references, but it can expose cross-part interference. The ordinary combined golden test and all old hashes remain unchanged.

## Run 127 memory result

The lean target build (Slicer excluded) and linker diagnostics completed successfully despite the host regression failure. The linker reports `.data + .bss = 56,036 bytes of 73,728 bytes` and `.pool = 145,720 bytes of 368,640 bytes`; `.ram_text` is 3,124 bytes. These are the lean baseline image's placements, not proof that Rings and Clouds objects or their audio buffers fit. The development firmware artifact was correctly skipped because the host suite failed. The linker diagnostic artifact is `rings-into-clouds-linker-diagnostics-c1112fd29f8099c31e9b55d126162c139a379c9e`.

## Status

The original 1.4 golden files remain unchanged. Run 127 passed target ABI and pinned Rings/Clouds DSP compile-only checks, the compact Rings delay-line host comparison, the FM-1 firmware build, and lean memory diagnostics. It failed the host regression suite as described above. No production Rings-to-Clouds audio integration exists yet; that remains a separate unfinished milestone.
