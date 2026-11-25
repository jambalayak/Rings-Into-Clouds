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

## Run 134 — one-voice companion diagnostic and linker checkpoint (2026-11-25)

Run 134 (`45511891223`, commit `733acca93ae06e14c142e919ee24aa71f3104fe8`) completed with **failure**. Target setup, ABI smoke, pinned Rings/Clouds compile-only checks, compact Rings delay-line host comparison, normal firmware build, engine-switch diagnostic, and lean memory diagnostic all completed successfully. The tested development firmware artifact was skipped because host regression failed.

The new counterfactual diagnostic constrained the companion to one LEGATO voice while leaving it rendering and muted at the mixer. DRUM sequences were excluded because DRUM's `oneshot` policy forces polyphony. Across 384 matched eligible sequences it reported:
- Primary + mono companion: `558a162ca31d0554`
- Matched primary-only: `4f2f3dfb4780a7c1`
- Matched primary + muted polyphonic companion: `11cbfc7fd013575a`

These are aggregate hash fingerprints, not numerical distances: different hashes cannot be described as “closer” or “farther.” The one-voice result differs from both matched controls, so this experiment does **not** establish that companion voice count is the sole cause, nor does it exonerate shared voice allocation. Next isolate allocator effects with per-part victim/kill counters or a test-only mode that prevents companion allocation while preserving the same render schedule. If the primary-only hash is not restored, investigate per-part engine-memory ownership and shared/global modulation or random state.

The lean linker artifact confirms the same baseline section sizes:
- `.data`: 352 bytes
- `.bss`: 55,684 bytes
- `.data + .bss`: 56,036 bytes of 73,728 bytes ordinary RAM
- `.pool`: 145,720 bytes of 368,640 bytes
- `.ram_text`: 3,124 bytes
- `.text`: 471,232 bytes

This is still the lean baseline only. It contains no live Rings/Clouds processor state or audio buffers, so it is not a Rings/Clouds memory-fit result. The artifact is `rings-into-clouds-linker-diagnostics-733acca93ae06e14c142e919ee24aa71f3104fe8`.

The host regression suite's UI test reports 15 distinct failing assertions in the first configuration, repeated in the CPU2-off and FM4/ADPCM configurations. They cover: empty OTHER preset list; SONG row change and lane playback; FX key press/release and combo handling; FX LEDs; FX GLO/SCL knob handling; FX depth direction; SEQ TOOLS/ARP division stepping; FX LED breathing; and HELP text layout. The suite also reports 90/91 golden renders changed and all 720 engine-switch sequences differ from the 1.4 references. Health, voice/routing, CPU-budget and crash checks remain separate and must not be mistaken for a clean regression. Do not regenerate golden hashes or weaken tests.

## Status

The original 1.4 golden files remain unchanged. Run 134 passed target ABI and pinned Rings/Clouds DSP compile-only checks, compact delay-line host comparison, normal FM-1 firmware build, engine-switch diagnostic execution, and lean memory-diagnostic build. It failed the host regression suite. No production Rings-to-Clouds audio integration exists yet; that remains a separate unfinished milestone.



## Run 139 — note-free engine-switch counterfactual (2026-11-25)

Run 139 (commit `273663cb8b544503d367ec6af8dd0762a430988c`) completed with **failure**. Target ABI smoke, pinned Rings/Clouds compile-only checks, compact Rings delay-line host comparison, and the normal FM-1 firmware regression build passed. The host regression suite failed; the tested development build artifact was therefore not a release candidate.

The corrected mode-7 diagnostic now uses `uswitch()` for the companion: it changes the companion engine and preserves the wait/render schedule without sending note-on or note-off events. The companion is also muted at the mixer. Across the matched eligible sequences the output was:
- Primary + note-free engine-switching companion: `8293e8d6902f8147`
- Matched primary-only: `4f2f3dfb4780a7c1`
- Matched primary + muted rendering companion: `11cbfc7fd013575a`

The note-free engine-switching companion still changes the aggregate fingerprint. This rules out companion note allocation as a necessary condition for this particular observed difference, but does not by itself identify the cause. Hashes remain fingerprints, not distance measurements.

### Newly identified shared-RNG path

Source inspection identifies a specific and testable global-state mechanism. In `firmware/src/voice.c`, `track_lfo_tick()` advances every rendered track's LFO. When its phase wraps, it calls `lfo_rand()`; for parts 1–3 this calls the shared `rng()` generator (`LFO_SHARED_RNG == 3`). The fourth part uses its own xorshift. The source comment explicitly notes that the shared sequence also seeds engine noise in PHYS/VOICE and other engines.

The note-free companion still passes through `track_render()`, and therefore still advances its LFO. Engine preset changes can change the companion's LFO rate/sync parameters. That can change when its LFO wraps and how many values it consumes from the shared RNG, shifting later random values observed by the primary part and its engines. This is a strong candidate explanation for why a muted companion that receives no notes can alter the primary mix.

This is source-level evidence for a plausible causal path, **not yet a confirmed root cause**. Next add a diagnostic counterfactual that keeps the companion engine-switch/render schedule identical but prevents that companion from consuming the shared RNG (without disabling its rendering or changing the primary's random stream). Compare it with the same matched primary-only and mode-7 sequences. If the primary fingerprint is restored, isolate the least invasive fix: per-part deterministic LFO random streams or a narrowly scoped RNG stream for LFO sample-and-hold, with golden-render coverage. Do not simply freeze the companion LFO or reseed the global generator in production.

The existing shared voice allocator remains a separate possible contributor in the ordinary note-playing modes, but it cannot explain the note-free mode-7 difference through companion note allocation.

## Current regression summary — Run 139

The 91-render audio golden suite reports 90 changed renders and zero missing renders. The 720 engine-switch golden sequences differ from the 1.4 references. Health, voice/routing, CPU-budget and crash checks report zero failures. UI tests report 15 failing assertions in each tested configuration, covering preset-list handling, SONG, FX keys/LEDs/knobs, sequencer tools/ARP division, and HELP layout. Do not regenerate golden hashes or weaken the assertions.


## Run 142 — shared-LFO-RNG counterfactual (2026-11-25)

Run 142 (`45524656333`, commit `5e6f80138fb7c6bf2ca80922e351f9323650959e`) completed with **failure**. The target ABI smoke probe, pinned Rings/Clouds compile-only check, compact Rings delay-line host comparison, normal FM-1 firmware build, engine-switch diagnostic, and lean memory-diagnostic build all completed successfully. The host regression suite failed, so the tested development firmware artifact was skipped. A linker-diagnostics artifact was uploaded.

The mode-8 counterfactual preserved the note-free companion's engine-switch/render schedule and muted it, but isolated that companion's LFO random draws from the shared RNG using a host-only test hook. Its aggregate fingerprint was:
- Primary + RNG-isolated engine-switching companion: `ac341378dd96f829`
- Matched primary-only: `4f2f3dfb4780a7c1`
- Matched primary + muted rendering companion: `11cbfc7fd013575a`
- Primary + ordinary note-free engine-switching companion (Run 139): `8293e8d6902f8147`

The RNG-isolated fingerprint is distinct from both matched controls. This counterfactual therefore does **not** restore the primary-only result. It weakens the hypothesis that companion LFO consumption of the shared RNG, by itself, explains the mode-7 difference. It does not prove the shared RNG is irrelevant: other shared-RNG consumers (including engine noise), changed RNG call ordering, or interactions with other global state remain possible. Do not change production RNG behavior based on this result.

Next isolate other shared state while keeping the companion note-free and preserving the same render/engine-switch schedule. Prioritize auditing engine-memory ownership and all global RNG consumers reached during render; add narrow host-only counters or counterfactuals that identify which shared resource changes. Keep the production path untouched until a causal test restores the matched primary-only fingerprint and golden-render coverage exists. Hashes are fingerprints, not numerical distances.

### Run 142 host regression and memory results

The host suite still reports 90 of 91 audio golden renders changed (zero missing), and all 720 engine-switch sequences differ from the 1.4 references. The UI test reports 15 failing assertions per tested configuration, in the same SONG, FX key/LED/knob, sequencer division, and HELP-layout areas recorded above. The UI render/layout phase also emitted a segmentation fault while generating render assets; the script continued to later checks, so this is an additional host-test warning to investigate rather than evidence that the target build failed. Health, voice/routing, CPU-budget and crash checks remain distinct from the golden-hash failures; do not regenerate golden hashes or weaken assertions.

The lean target linker diagnostic passed with:
- `.data + .bss`: 56,036 bytes of 73,728 bytes ordinary RAM
- `.pool`: 145,720 bytes of 368,640 bytes
- `.ram_text`: 3,124 bytes
- `.text`: 471,232 bytes
- Firmware image: 474,708 bytes; packaged `.fwsc`: 610,286 bytes

These are still lean-baseline figures and do not include live Rings/Clouds state or audio buffers. They do not establish final Rings/Clouds memory fit or provide a firmware release. The linker artifact is `rings-into-clouds-linker-diagnostics-5e6f80138fb7c6bf2ca80922e351f9323650959e`.

## Current status after Run 142

The shared-LFO-RNG-only explanation is not supported by the mode-8 counterfactual: isolating the companion LFO RNG does not restore the primary-only fingerprint. The next investigation should examine other shared render state and RNG consumers, while keeping the production firmware unchanged. Rings/Clouds remain compile-tested only; there is still no production Rings-to-Clouds audio path or final target memory-fit result.


## Run 144 — matched RNG-isolated no-switch control (2026-11-25)

Run 144 (`45530719898`, commit `f46584a80298345b931b7dec43524a4f1964fde8`) completed with **failure**. Target ABI smoke, pinned Rings/Clouds compile-only checks, compact Rings delay-line host comparison, normal FM-1 firmware build, engine-switch diagnostic, and lean memory-diagnostic build all completed successfully. The host regression suite failed; upload of the tested development firmware was skipped. A lean linker-diagnostics artifact was uploaded.

The new mode-9 control uses the same note-free, mixer-muted companion and isolated LFO RNG as mode 8, with the same render/wait schedule, but does not switch the companion's engine. The diagnostic reported:
- Primary + RNG-isolated engine-switch companion (mode 8): `ac341378dd96f829`
- Matched primary + RNG-isolated no-switch companion (mode 9): `ac341378dd96f829`

The fingerprints are exactly equal. In this controlled configuration, engine switching adds no detectable change beyond the matched note-free companion render schedule. This is evidence against engine switching itself being the necessary trigger for the mode-8 aggregate difference. It does **not** restore the matched primary-only fingerprint (`4f2f3dfb4780a7c1`) or the ordinary muted-rendering companion fingerprint (`11cbfc7fd013575a`), and it does not identify the remaining shared-state mechanism. Keep hash interpretation binary (equal/different), never as a numerical distance. Do not change production RNG or engine-switch behavior based on this test.

The earlier PHYS-reset/global-RNG candidate is not supported for this host configuration: the host build enables `FELUCCA_CPU2=1`, for which `PHYS_RSEED(t)` uses per-part `noise32()`, not the global `rng()`. Continue auditing other state touched by rendering a note-free companion, including per-track LFO/control state, global modulation state, and any shared buffers or scheduling side effects. A useful next counterfactual should isolate one candidate at a time while preserving the same primary input, companion render schedule, and matched wait durations.

### Run 144 regression and linker result

The host suite reports 90 of 91 audio golden renders changed (zero missing), and all 720 engine-switch sequences differ from the 1.4 references. Health, voice/routing, CPU-budget and crash checks remain at zero failures. The same UI test assertions recorded in Run 134 remain a separate failure category; do not regenerate golden hashes or weaken assertions.

The lean linker diagnostic reports:
- Image: 474,708 bytes
- `.data + .bss`: 56,036 bytes of 73,728 bytes ordinary RAM
- `.pool`: 145,720 bytes of 368,640 bytes
- `.ram_text`: 932 instructions, no calls

These are lean baseline figures only. They contain no linked Rings/Clouds processor state or audio buffers and do not establish final memory fit. The artifact is `rings-into-clouds-linker-diagnostics-f46584a80298345b931b7dec43524a4f1964fde8`.

## Current status after Run 144

The matched mode-8/mode-9 equality shows that engine switching is not required to produce the isolated-companion fingerprint in this test. The remaining discrepancy is associated with some aspect shared by the two companion-render conditions, but its cause is unresolved. Production audio/RNG code remains unchanged. Rings and Clouds remain compile-tested only: no production Rings-to-Clouds audio path, final target memory-fit result, or physical FM-1 validation exists.
