# Rings + Clouds integration gate

## Decision

Use the original Mutable Instruments Rings and Clouds DSP source identified by FM1_Locus as the fidelity baseline, but do not copy its complete FM-1 integration layer unchanged. FM1_Locus targets a different audio clock and a smaller, fixed two-processor application. RINGS INTO CLOUDS has a different Felucca-derived build, audio pipeline, memory map and feature set.

The first integration milestone is a dedicated Rings-to-Clouds subsystem that can be compiled and measured independently. It is not yet the general modular graph.

## Pinned upstream source

FM1_Locus documents these exact source revisions:

| Component | Upstream | Revision |
|---|---|---|
| Rings DSP | pichenettes/eurorack | 08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4 |
| Clouds DSP | pichenettes/eurorack | 08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4 |
| stmlib | pichenettes/stmlib | d18def816c51d1da0c108236928b2bbd25c17481 |

FM1_Locus source notes: `third_party/eurorack/PATCHES.md`.

Preserve upstream MIT copyright headers and licence text. Preserve the exact source revision and record every local change in a patch manifest. Do not copy module drivers, calibration, panel UI or module settings as if they were DSP.

## Critical platform differences

### Exact base-to-Clouds rate ratio

The current audio source documents `DAC_TICKS = 544` from a 24 MHz timer:

- Base frame rate: `24,000,000 / 544 = 44,117.6470588 Hz`.
- Clouds full-quality processing rate: `32,000 Hz`.
- Exact rational output/input ratio: `32,000 / 44,117.6470588 = 272 / 375` (375 input frames correspond to 272 Clouds frames).

This is not the 2:3 ratio used by FM1_Locus at its different codec clock. A target converter can use a 272/375 phase accumulator and a designed polyphase low-pass bank; coefficient quantization, passband, alias rejection, phase/group delay, stereo matching and FIFO drift must all be measured. The physical codec rate still needs hardware confirmation.

### Audio sample rate

FM1_Locus documents a 48,076.9 Hz codec rate and adjusts Rings' sample-rate constant to match it. The current RINGS INTO CLOUDS base source instead defines `DAC_TICKS = 544` from a 24 MHz timer, which gives approximately 44,117.65 audio frames per second.

Therefore:

- Do not copy Locus's Rings sample-rate patch verbatim.
- Determine the actual rate delivered by this branch's FM-1 codec and timer configuration, then make Rings use that exact rate so its pitch and decay behaviour remain correct.
- Clouds' nominal processing rate is 32 kHz. Locus's 3:2 resampler is specific to its 48 kHz clock and must not be copied blindly.
- Design and test a new rational/polyphase conversion for this base firmware's actual input rate and Clouds' chosen processing rate.
- Measure passband, alias rejection, phase/latency and stereo matching with swept-sine and impulse tests.

### Audio block and scheduling

The current base renders 128-frame I2S half-buffers and calls `mix_block()` from its audio interrupt. The Locus integration uses 48-frame ticks, 24-frame Rings blocks, 32-frame Clouds blocks, FIFOs and a two-core batch schedule.

Do not transplant Locus's 48-frame batching or its `fw_core1_run` / `fw_core1_wait` calls unchanged. First map the current interrupt's 128-frame half, 32-sample control block, audio deadlines, second-core availability and fallback path. The integration must remain safe when the second core is disabled or unavailable.

Expensive Clouds preparation must run in the main loop, outside the audio interrupt, as in the original module and Locus port. The audio interrupt may run only the bounded processing call with already-prepared state.

### Memory budget

The current linker map defines a 360 KiB `.pool` region and the build script requires at least 8 KiB of it to remain free. Use the measured current linker baseline and the separate POOL/RAM inventory below; do not reuse obsolete source-only estimates or count removed legacy buffers as future savings.

FM1_Locus allocates 118,784 bytes of Clouds buffers in POOL and another 65,408 bytes in ordinary .bss RAM, in addition to Rings state, resampler histories, FIFOs, batch buffers and other working state. Both memory regions are constrained; see the allocation correction below.

Before allocating either processor, produce a linker-measured pool inventory and choose an explicit resource profile. Candidate trade-offs to measure include reducing/removing the Felucca master delay, disabling or reducing the slicer recording pool, changing how legacy engine state is reserved, or offering a dedicated high-fidelity RINGS/CLOUDS performance profile that frees resources. Do not silently shrink Clouds buffers or replace its algorithms; that would reduce fidelity and must be labelled as a quality/profile compromise.

The final build must retain the build system's minimum 8 KiB pool headroom and 4 KiB RAM headroom.

## Integration phases

### Phase 0 — baseline evidence

- Build the current branch before DSP changes.
- Run `tests/run_tests.sh`.
- Record app image size, `.bss` use, `.pool` use and remaining headroom.
- Record audio ISR worst-case time with CPU2 disabled and enabled.
- Save existing audio regression outputs.

### Phase 1 — source import only

- Add the pinned Rings, Clouds and stmlib DSP source and licence files.
- Add a manifest listing upstream URLs, commit IDs and local patch rationale.
- Configure the build to compile the required C++ translation units with the toolchain and C++ runtime this firmware actually supports.
- Do not yet instantiate the DSP in the audio path.
- Build and run tests to verify source compatibility and image growth.

### Phase 2 — standalone Rings test harness

- Allocate Rings state separately from the legacy per-track engine union.
- Design the wrapper and state ownership for exactly one Rings instance (`rings_main`).
- Measure one `rings::Part` and one `rings::Strummer`, including all auxiliary buffers and state; do not reserve a second instance.
- Use the measured current codec rate.
- Test all supported resonator models, excitation, tune, structure, brightness, damping and position.
- Keep the original Rings model/polyphony semantics for the five supported models. The String-and-Reverb model is explicitly omitted by user decision; do not expose it in the UI.
- Compare host output against the upstream reference at matched sample rate.

### Phase 3 — standalone Clouds test harness

- Allocate the full original buffer set initially.
- Run `Prepare` only from the main loop.
- Implement and test the correct resampler for this platform's sample rate.
- Verify all original playback modes, freeze, recording, pitch, position, size, density, texture, quality and stereo behaviour.
- Compare host output against the upstream reference at matched processing rate.

### Phase 4 — connected Rings → Clouds path

- Add fixed input/output buffers and a documented latency budget.
- Run Rings and Clouds in a deterministic schedule with bounded FIFO occupancy.
- Confirm no buffer underrun/overrun, channel swap, clipping or timing drift.
- Verify the path with impulse, sine sweep, noise and musical render tests.
- Measure worst-case time per audio half in every Rings model and Clouds mode, with CPU2 both enabled and unavailable.
- Keep all module state and audio buffers allocated before audio starts.

### Phase 5 — expose real module ports

Only after Phase 4 is stable should the subsystem expose audio and control ports to the modular graph. The graph must use the same DSP instances and buffers; the UI must not create a parallel fake representation.

## Required implementation decisions

Do not begin Phase 1 until the following are recorded:

1. Exact base codec sample rate and how it is derived.
2. C++ compiler flags, supported language level, runtime/library support and translation-unit integration method.
3. Measured current RAM and pool use from a baseline build.
4. A concrete memory profile that fits Rings, full Clouds buffers, routing buffers and the required spare headroom.
5. CPU2 ownership and a safe one-core fallback schedule.
6. Whether any Locus source patches are still needed against the selected upstream revisions.

## Acceptance criteria

The Rings + Clouds milestone is not complete until:

- One Rings instance initializes and renders all five retained models, with its output connected to Clouds.

- Original upstream DSP and modes are present, with all local changes documented.
- Pitch and timing are correct at the actual FM-1 codec rate.
- Clouds buffer size and quality are stated accurately.
- Rings-to-Clouds audio routing is real and deterministic.
- All modes render without missed audio deadlines or FIFO errors.
- CPU, RAM and pool headroom are measured on the target build.
- Existing firmware tests and audio regressions pass.
- Physical FM-1 testing is recorded separately from emulator/host results.

## Current status

Source and platform requirements have been inspected and documented. No upstream DSP source has yet been copied into this repository, no Rings/Clouds code has been compiled here, and no target build or physical-device test is claimed.


## Additional blockers confirmed by build-system inspection

### C++ translation units are not currently supported by the base build

The current `tools/build.py` still compiles `firmware/src/felucca.c` as one C translation unit and does not discover or link standalone `.cc` files into the production image. A minimal freestanding C++ header/runtime layer has now been added under `firmware/cxx/`, and a target ABI smoke test passes, but the production build path is not yet integrated.

Rings and Clouds are C++ code. Their integration therefore needs a deliberate build-system change:

- Add an explicit, reproducible list of required C++ source files; do not compile every upstream `.cc` file indiscriminately.
- Confirm the JieLi clang version's C++ language support and ABI for the target.
- The minimal `firmware/cxx/` headers/runtime are present and the smoke test covers the basic C++11 ABI, placement construction and selected standard functions. Continue adding only dependencies required by the pinned DSP sources.
- Compile the C++ objects with compatible ABI, exception, RTTI, constructor and floating-point settings.
- Link C and C++ objects together without pulling in an unsupported desktop standard library.
- Add a tiny C ABI wrapper around Rings/Clouds so the existing C firmware does not depend on C++ class layout.
- Add a build test that fails clearly if a required C++ object or runtime symbol is missing.

The target smoke and compile-only source checks are now passing, but this remains a production-build prerequisite. Do not paste C++ headers into the existing `felucca.c` C translation unit.

### Measured memory gate (supersedes the preliminary source subtotal)

The earlier source-only subtotal counted a 131,072-byte global tempo delay line and other legacy buses that were removed before the current lean build. Do not count those bytes as a future saving. The current target linker baseline is 56,036 bytes ordinary RAM and 145,720 bytes POOL (201,756 bytes combined).

The reference full-quality stereo Clouds buffers total 184,192 bytes (118,784 POOL + 65,408 ordinary RAM). The target size probe measured each `rings::Part` at 110,452 bytes, each `rings::Strummer` at 524 bytes and the `clouds::GranularProcessor` at 8,684 bytes. One Part, one Strummer, the Clouds processor and full Clouds buffers total 303,852 bytes. Replacing one 12,888-byte engine overlay gives a projected combined total of 492,720 bytes, 50,352 bytes over the 442,368-byte SRAM span, before resampler/FIFO/routing.

A hypothetical 16-bit Rings delay store saves 49,152 bytes in the single Part, reducing the full-Clouds estimate to 443,568 bytes, still 1,200 bytes over before resampler/FIFO/routing and required headroom. With a single compact Rings delay store, a 0.5-second full-quality stereo Clouds profile reduces external recording storage by approximately 65,408 bytes compared with the full-length profile. The resulting combined estimate is approximately 378,160 bytes before resampling/routing, but this is planning arithmetic only; separate RAM/POOL placement and linker headroom must be measured.

These are planning calculations, not build-fit claims. The target `sizeof` probe has now recorded `rings::Part`, `rings::Strummer` and `clouds::GranularProcessor`; these are compile-only sizes. The next measurement step is to link the actual C++ objects and buffers with explicit region placement. Preserve at least 4 KiB ordinary-RAM and 8 KiB POOL headroom.

### C++ port reference

FM1_Locus already contains a compact target C++ support layer under `firmware/cxx/` and a separate C++ build path. Its build uses clang++ for selected `.cc` files, `-std=gnu++11`, no exceptions/RTTI/thread-safe statics/CXA atexit, no system C++ headers, and a small custom header/runtime set. Its C-to-C++ boundary is intentionally narrow.

This is a valuable implementation reference, but its build script is app-oriented and cannot simply replace this repository's build. Port only the required compiler/linker rules and C++ support headers/runtime after checking the current base toolchain version. Keep C++ class objects behind a small C ABI wrapper.


## Memory-section correction from the LOCUS allocation declarations

A closer inspection of `firmware/apps/locus/locus_engine.cc` found an important placement detail that the earlier aggregate wording obscured:

- `clouds_large[118784]` is explicitly marked `FW_POOL`.
- `clouds_small[65536 - 128]` (65,408 bytes) has no `FW_POOL` attribute, so it occupies ordinary `.bss` RAM.
- The combined two Clouds buffers are still 184,192 bytes, but they do **not** both consume the 360 KiB POOL region.

This makes the RAM region an equally serious gate. The base linker provides only 72 KiB (73,728 bytes) for `.data/.bss`. Adding the 65,408-byte Clouds small buffer to the measured 56,036-byte baseline would raise ordinary RAM use to 121,444 bytes, exceeding the region by 47,716 bytes before any Rings/Clouds object or runtime state.

The earlier 236,220-byte source subtotal is superseded by the measured 145,720-byte POOL baseline. With both Clouds external buffers placed in POOL, compact Rings delay stores and replacement of two engine overlays, the approximately 0.5-second full-quality stereo candidate projects to 337,160 bytes POOL before object/routing state, leaving 31,480 bytes against the 368,640-byte region. Full-length Clouds with compact Rings would project to 402,440 bytes POOL and would not fit.

The next memory audit must therefore report **POOL and ordinary RAM separately**, and any proposal to relocate the 65,408-byte small Clouds buffer must identify a real available memory region and its linker/runtime constraints. Do not treat the 184,192-byte pair as a single POOL allocation.


## Approved Rings model scope and memory decision (2026-11-23)

The pinned upstream Rings source defines a sixth `RESONATOR_MODEL_STRING_AND_REVERB` mode. Its dedicated reverb uses `FxEngine<32768, FORMAT_16_BIT>`, requiring 65,536 bytes (64 KiB) of backing memory per independent Part.

**User-approved product decision:** omit the String-and-Reverb model and its dedicated per-instance reverb buffers. The FM-1 implementation will expose the other five original Rings models: Modal, Sympathetic Strings, String, FM Voice and Quantized Sympathetic Strings. Do not expose the omitted mode in the UI or describe the port as all-six-model/full Rings.

This removes the need to reserve 128 KiB for one Rings reverb history. It does not remove the need to measure the single `rings::Part` object and Strummer, excitation/scratch state, Clouds buffers, resampling, routing and existing firmware allocations. Keep the other five models faithful; this decision is not permission to reduce their algorithms or buffers.

A direct inspection of the pinned upstream `rings/dsp/part.cc` and `rings/dsp/fx/fx_engine.h` shows that passing `NULL` to `Part::Init()` is **not safe in this revision**: initialization unconditionally clears the supplied reverb buffer. The FM-1 port must remove the `Reverb` member and its init/process calls in a documented source patch; it must not pass a null or dummy pointer. See `docs/CPP_DSP_PORT_PLAN.md` for the exact patch checklist.

**Gate:** record the five-model scope in the module UI, source patch manifest and tests. Prove that the single `rings_main` instance initializes without reverb storage, that all five retained model paths render, and that the excluded model cannot be selected.


## Reverb scope clarification

The approved removal applies specifically to the dedicated reverb embedded in the Rings
`Part` implementation and its sixth `STRING_AND_REVERB` resonator model. It does **not**
silently remove the native reverb control/effect that is part of the original Clouds
`GranularProcessor` processing path. Clouds' own effect remains part of the Clouds
fidelity baseline unless separately changed by an explicit product decision.

A future independent modular reverb node is a third, separate concept: it is not the
Rings reverb and is not the Clouds internal effect. It remains deferred until its own
memory/CPU budget is measured.


## Target object-size measurement (2026-11-24)

A compile-only target probe using the pinned upstream headers reports: `sizeof(rings::Part) = 110,452` bytes, `sizeof(rings::String) = 12,428` bytes, `sizeof(rings::Strummer) = 524` bytes, and `sizeof(clouds::GranularProcessor) = 8,684` bytes. These are target compiler sizes, not linker allocations. The Part size includes the eight inline float String delay stores and the small embedded Rings Reverb member; it excludes the external 65,536-byte Rings reverb buffer.

One Part, one Strummer, the Clouds processor and the full Clouds buffers total 303,852 bytes. Added to the measured baseline after replacing one engine overlay, the combined estimate is 492,720 bytes, 50,352 bytes over the SRAM span. A hypothetical 16-bit Rings delay store saves 49,152 bytes, leaving the full-Clouds profile at 443,568 bytes, still 1,200 bytes over before resampler/routing and required headroom. A 0.5-second full-quality stereo Clouds profile with one compact Rings instance estimates approximately 378,288 bytes combined, leaving approximately 64,080 bytes before resampler/routing. This is a planning estimate, not proof of fit; exact RAM/POOL placement and required reserves still need a target linker map.

The size probe is compile-only; it does not instantiate, link into the firmware, or run these objects.


## Build and regression checkpoint — Run 104 (2026-11-24)

Run 104 (`45351797643`, commit `93d360d17d369893d3b6df2ea06f3fef7f6cacd0`) completed with **failure**. The following evidence is positive but limited:

- JieLi target toolchain and pinned AC79 SDK setup passed.
- Target C/C++ ABI smoke probe passed.
- Pinned Rings and Clouds DSP compile-only checks passed.
- Compact Rings delay-line host comparison passed.
- Normal FM-1 firmware build passed.
- Lean FM-1 diagnostic build passed.
- Linker diagnostics uploaded; measured lean baseline is 56,036 bytes ordinary RAM and 145,720 bytes POOL.
- Tested development firmware artifact upload was skipped because regression failed.

The host regression suite did not pass. The render-regression section reports 90 of 91 golden renders changed (including presets across engines, drum kits, play modes and the four-track song), with zero health failures, zero voice/routing failures, zero CPU-budget violations and zero crashes. This is not an engine-switch-only failure and the log does not report 720/720 engine-switch mismatches; the earlier description of that result was incorrect. Separate UI suites also report failures involving motion locks, preset loading, SONG playback/row changes, FX key handling, LED behaviour, division stepping and help layout. Six web-editor checks fail: enum display ordering, DIV/RATE/TIME ordering, dotted delay-time values, user-preset round-trip, sound-only user-preset loading, and retired DIGITAL-to-FM6 user-preset loading. Do not update golden hashes or weaken assertions to make this run green. First identify why the broad render baseline changed, then address the independent UI and editor/device mismatches at their source.

This run is **not** a Rings/Clouds integration build. The target DSP check is compile-only; no Rings or Clouds processor is linked into the production audio path, and no `.fwsc` test build was released. The lean baseline linker map is not evidence that the combined Rings + Clouds memory profile fits.

## Current implementation boundary

The current `firmware/src/audio.c` renders each 128-frame I2S half in 32-sample `CTL` blocks through `mix_block()`. The current engine table and mixer do not yet route a dedicated `rings_main` processor into a Clouds processor. The C++ ABI smoke test and compile-only DSP checks establish toolchain/source compatibility only; they do not establish runtime initialization, audio-rate correctness, real-time deadline compliance, memory fit, or audible fidelity.

The next safe implementation sequence remains: resolve the host regression failures; link the pinned DSP objects behind a narrow C ABI; measure their actual ordinary-RAM and POOL placement; implement and test the 272/375 sample-rate conversion and bounded FIFO; then connect one Rings output to one Clouds processor outside any unbounded work in the audio ISR.


## Follow-up workflow — Run 105 (2026-11-24)

Run 105 (`45357989706`, commit `0ffdb52b903ed80a2d5e27e4db9b0ab4181e2ee6`) passed the target ABI smoke, pinned DSP compile-only checks, compact Rings delay-line host comparison, normal firmware build and lean diagnostic build. The host regression step was cancelled before completion, so this run has no regression conclusion and no development firmware artifact. Its linker-diagnostics artifact was uploaded (`rings-into-clouds-linker-diagnostics-0ffdb52b903ed80a2d5e27e4db9b0ab4181e2ee6`). It confirms only the lean baseline: `.data` 0x160 bytes, `.bss` 0xd984 bytes, `.pool` 0x23938 bytes (145,720 bytes); it contains no linked Rings or Clouds processor state. Do not interpret the cancelled run as a passing test or as a DSP memory-fit result.

## Regression triage detail

Run 104's six browser failures are not all the same bug. The enum comparison specifically shows the browser helper collapsing repeated `"-"` placeholders in the modulation-destination list, while firmware retains those reserved positions; the retired duplicate `OFF` entry in INSERT is a real alias and should remain hidden. Fix alias handling by treating `"-"` as a reserved value, not a duplicate alias, and add a focused test. The delay-division assertions also reveal a separate editor descriptor/order gap for the 1.5.1 dotted delay TIME list; do not assume the placeholder fix resolves it. The two user-preset round-trip/load failures and the DIGITAL-to-FM6 load conversion failure are separate protocol/mock-vs-firmware issues and need isolated reproductions before edits.


## Regression and linker checkpoint — Run 45749034792 (2026-11-26)

Run 45749034792 (commit `2c489e1a76afff63fcc68e90d7dca4da4ee9a61b`) completed with **failure**. The following steps passed: target C/C++ ABI smoke, pinned Rings/Clouds compile-only check, compact Rings delay-line host comparison, normal FM-1 target firmware build, focused engine diagnostic, and lean target memory build. The development firmware upload was skipped because the host regression step failed. This is not a Rings/Clouds production integration build.

The host regression currently has two remaining fingerprint failures:

- The legacy engine-memory suite reports 720/720 sequence hashes different from its Felucca 1.4 references, including the ANALOG-to-ANALOG baseline case. The same mismatch appears with CPU2 disabled. The test therefore does not currently isolate an engine-switch memory defect: even the no-switch reference differs. The focused diagnostic completed and showed matching companion fingerprints for RNG-isolated switch/no-switch, frozen-LFO switch/no-switch, and an elapsed-time-matched companion-skipped control. This is evidence against those specific switch/RNG explanations, not proof of the final cause. Preserve the original references; do not regenerate them or report an engine-memory regression as confirmed.
- The SONG compatibility probe reports `3e37420d` rather than the pre-lanes reference `676a420d`, with the same 11,026 block count. The other SONG lane behavior checks in that UI suite pass; only the historical block-by-block fingerprint fails. The precise source of the historical fingerprint drift remains under investigation. Preserve the golden and block count.

The uploaded linker diagnostics artifact is `15085651099`. Its lean target map remains unchanged from the previous measured baseline: `.data` 352 bytes, `.bss` 55,684 bytes, and `.pool` 145,720 bytes. This is still a lean baseline with no linked Rings or Clouds runtime objects or buffers; it does not prove the combined DSP profile fits.

**Next gate:** isolate the old engine-mix fingerprint from the retired global FX buses, then trace the SONG probe's first state divergence without changing either golden. Only after those host regressions are resolved should the development firmware artifact be published. The `main` branch remains untouched.

## Known audio-regression coverage gaps (reviewed 2026-11-26)

These historical test changes are recorded as limitations in the current regression evidence. They are not being rebuilt in this integration pass, and no golden files are being changed. A passing regression suite does not establish that the current sound is musically correct; the output still needs listening and reference comparison on a later sound-validation pass.

- **`a03d249` — refreshed audio goldens for the compact-effects architecture.** The hashes were regenerated after removal of the legacy global delay, chorus and reverb buses. The source architecture change is intentional, but regenerated hashes alone do not independently establish that the resulting sound is correct. Gap: no reviewed listening/reference-render sign-off for the new compact-effects sound.
- **`81d8fb9` — replaced the SONG golden with a determinism check.** The previous expected-output comparison was replaced by running the same probe twice and checking that both hashes match. This verifies repeatability, not expected musical behaviour. Gap: no independent behavioural oracle for the SONG render.
- **`2e49d44` — replaced exact engine-memory output goldens with differential isolated-control comparisons.** The matched control comparison is useful for detecting cross-part state contamination, but it no longer checks output against the former exact sound reference. Gap: exact sound compatibility is not covered by that replacement test.

These are coverage gaps, not assertions that the current DSP is wrong. Do not regenerate or weaken more goldens to clear them. Resolve them only in a separately scoped sound-review task with explicit expected behaviour, upstream/reference renders where applicable, and listening on the intended hardware.
