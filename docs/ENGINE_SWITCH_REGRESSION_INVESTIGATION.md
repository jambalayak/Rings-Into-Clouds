# Engine-switch regression investigation

## Current evidence

Run 121's main regression reports 90 of 91 audio golden renders and all 720 engine-switch sequences differ from the 1.4 references. The independent Felucca-Engines suite passes all 122 renders, and the second-core comparison passes all 28 scenes. Those passing suites do not prove the integrated track/voice/mixer path is unchanged.

The engine-switch test is in `tests/union_test.c`. Its hash is the complete stereo mix, not the output of the part under test alone. Each sequence switches `trk[0]` through a pair or A→B→A sequence, and also changes the engine on `trk[2]` after every primary step:

```c
uplay(&trk[0], e[k], pi + k, 60, wait_ms);
uplay(&trk[2], UE[(k + 3u) % UNE], pi, 55, 10);
```

Consequently, a changed hash cannot by itself identify whether the difference came from the primary part, the concurrently changing companion part, or their interaction in the shared voice budget and mixer. The test description says the other part plays "alongside", but does not call out that its engine changes throughout the sequence.

## State-sharing hypothesis

`firmware/src/engines.c` keeps one engine-memory region per part. When an engine that needs that region claims it after another memory-using engine, the region is zeroed. Engines with no per-part memory leave the owner marker unchanged. This memory-saving design may not be bit-identical to retaining separate state arrays for every engine across switches.

The 1.4 reference hashes remain authoritative regression evidence until a controlled comparison explains the differences. Do not update `tests/union_golden.txt` merely to silence failures.

## Next diagnostic sequence

1. Preserve the existing test and its 1.4 references unchanged.
2. Add diagnostic variants that hold the companion part on one fixed, memory-free engine and, separately, omit the companion part. Keep the primary part's exact note, preset, wait and switch sequence unchanged.
3. Report primary-only and companion-present hashes separately, so the source of a difference is identifiable rather than inferred from a complete mix.
4. Compare single-switch A→B, switch-back A→B→A, and the two timing cases (switch after 10 ms and during the fade).
5. If the shared-state reset is confirmed as the cause, decide whether to preserve per-engine state selectively, explicitly reinitialize state on every switch, or document changed switch semantics. Evaluate every choice against the memory budget and musical behaviour.
6. Re-run the host regression suite and target build. Keep all legacy golden files unchanged until the cause and intended behaviour are reviewed.

## Status

Investigation only. No audio code or golden reference was changed by this document. Rings/Clouds DSP integration remains a separate unfinished milestone.
