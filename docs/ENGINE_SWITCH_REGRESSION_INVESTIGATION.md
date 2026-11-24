# Engine-switch regression investigation

## Current evidence

Run 124 reproduces the same failure: 90 of 91 audio golden renders and all 720 engine-switch sequences differ from the 1.4 references. The 91-render summary reports zero health failures, zero voice/routing failures, zero CPU-budget overruns and zero crashes. The independent Felucca-Engines suite passes all 122 renders, and the second-core comparison passes all 28 scenes. Those passing suites do not prove the integrated track/voice/mixer path is unchanged. The independent Felucca-Engines suite passes all 122 renders, and the second-core comparison passes all 28 scenes. Those passing suites do not prove the integrated track/voice/mixer path is unchanged.

The engine-switch test is in `tests/union_test.c`. Its hash is the complete stereo mix, not the output of the part under test alone. Each sequence switches `trk[0]` through a pair or A→B→A sequence, and also changes the engine on `trk[2]` after every primary step:

```c
uplay(&trk[0], e[k], pi + k, 60, wait_ms);
uplay(&trk[2], UE[(k + 3u) % UNE], pi, 55, 10);
```

Consequently, a changed hash cannot by itself identify whether the difference came from the primary part, the concurrently changing companion part, or their interaction in the shared voice budget and mixer. The test description says the other part plays "alongside", but does not call out that its engine changes throughout the sequence.

## State-sharing hypothesis

`firmware/src/engines.c` keeps one engine-memory region per part. When an engine that needs that region claims it after another memory-using engine, the region is zeroed. Engines with no per-part memory leave the owner marker unchanged. This memory-saving design may not be bit-identical to retaining separate state arrays for every engine across switches.

The 1.4 reference hashes remain authoritative regression evidence until a controlled comparison explains the differences. Do not update `tests/union_golden.txt` merely to silence failures.

## Diagnostic implementation

`tests/union_test.c` now has an opt-in `UNION_DIAG=1` mode. It repeats each of the 720 sequence definitions in three independent renders: primary part only, companion part only, and the original combined arrangement. It reports separate aggregate hashes. The normal golden test remains unchanged and continues to compare the original combined render against the 1.4 references. The workflow runs the diagnostic after the ordinary host suite, even when that suite fails.

This first isolation pass does not yet establish a root cause: the isolated runs have no historical per-part golden references, and a combined-vs-isolated hash difference is expected because the rendered arrangement differs. Its purpose is to provide a controlled breakdown of the two track paths. A fixed memory-free companion variant remains a follow-up if needed.

## Run 124 memory result

The lean target build (Slicer excluded) and linker diagnostics completed successfully despite the host regression failure. The linker reports `.data + .bss = 56,036 bytes of 73,728 bytes` and `.pool = 145,720 bytes of 368,640 bytes`; `.ram_text` is 3,124 bytes. These are the lean baseline image's placements, not proof that Rings and Clouds objects or their audio buffers fit. The development firmware artifact was correctly skipped because the host suite failed. The diagnostic linker files are retained in Actions artifact `rings-into-clouds-linker-diagnostics-5de46d5aaa185fb89a59f8f238f2fdfd773d9bd1`.

## Status

The original 1.4 golden files remain unchanged. Run 124 built the FM-1 firmware, passed target ABI and upstream DSP compile-only checks, passed the compact Rings delay-line host comparison, and completed lean memory diagnostics. Its host suite failed on the legacy audio and engine-switch hashes described above. The isolated track diagnostic is queued in Run 126. No production Rings-to-Clouds audio integration exists yet; that remains a separate unfinished milestone.
