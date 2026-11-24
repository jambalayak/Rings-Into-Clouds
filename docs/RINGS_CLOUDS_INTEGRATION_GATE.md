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

The current linker map defines a 360 KiB `.pool` region and the build script requires at least 8 KiB of it to remain free. The existing firmware already places substantial persistent buffers in that pool:

- Four per-part engine-memory regions: 4 × 12,888 bytes in the normal build.
- Master tempo delay: 65,536 int16 samples (131,072 bytes).
- Chorus, reverb, HALL work state and per-track insert state.
- Four slicer recordings: 4 × 4,096 int16 samples (32,768 bytes).
- Scope snapshot and the 3,840-byte storage payload buffer.

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
- Design the wrapper and state ownership for two simultaneous Rings instances from the beginning; the product acceptance target is two independent instances, not one.
- Measure one and two rings::Part / rings::Strummer allocations separately, including all per-instance buffers and state.
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

- Two independent Rings instances can run simultaneously with separate parameters, triggers, presets and audio outputs.

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

The reference full-quality stereo Clouds buffers total 184,192 bytes (118,784 POOL + 65,408 ordinary RAM). The target size probe measured each `rings::Part` at 110,452 bytes, each `rings::Strummer` at 524 bytes and the `clouds::GranularProcessor` at 8,684 bytes. Two Parts, two Strummers, the Clouds processor and full Clouds buffers total 414,828 bytes. Replacing two 12,888-byte engine overlays gives a projected combined total of 590,808 bytes, 148,440 bytes over the 442,368-byte SRAM span, before resampler/FIFO/routing.

A hypothetical 16-bit Rings delay store saves 98,304 bytes across the two Parts, reducing the full-Clouds estimate to 492,504 bytes, still 50,136 bytes over. A 25% shorter recording store projects to 459,800 bytes, still 17,432 bytes over. A 0.5-second full-quality stereo Clouds profile with compact Rings projects to 427,224 bytes combined, leaving 15,144 bytes before resampling/routing. With both Clouds buffers in POOL and 13,596 bytes of object state placed in RAM, the current region estimate is 357,592 bytes POOL and 69,632 bytes RAM; only 2,856 bytes remain beyond the required reserves for resampling/routing.

These are planning calculations, not build-fit claims. The next measurement step is to record target `sizeof(rings::Part)`, `sizeof(rings::Strummer)` and `sizeof(clouds::GranularProcessor)`, then link the actual C++ objects and buffers with explicit region placement. Preserve at least 4 KiB ordinary-RAM and 8 KiB POOL headroom.

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

This removes the need to reserve 128 KiB for two Rings reverb histories. It does not remove the need to measure both independent `rings::Part` objects, both Strummers, excitation/scratch state, Clouds buffers, resampling, routing and existing firmware allocations. Keep the other five models faithful; this decision is not permission to reduce their algorithms or buffers.

A direct inspection of the pinned upstream `rings/dsp/part.cc` and `rings/dsp/fx/fx_engine.h` shows that passing `NULL` to `Part::Init()` is **not safe in this revision**: initialization unconditionally clears the supplied reverb buffer. The FM-1 port must remove the `Reverb` member and its init/process calls in a documented source patch; it must not pass a null or dummy pointer. See `docs/CPP_DSP_PORT_PLAN.md` for the exact patch checklist.

**Gate:** record the five-model scope in the module UI, source patch manifest and tests. Prove that both instances initialize without reverb storage, that all five retained model paths render, and that the excluded model cannot be selected.


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

Two Parts, two Strummers, the Clouds processor and the full Clouds buffers total 414,828 bytes. Added to the measured baseline after replacing two engine overlays, the combined estimate is 590,808 bytes, 148,440 bytes over the SRAM span. A hypothetical 16-bit Rings delay store saves 98,304 bytes but still leaves the full Clouds profile 50,136 bytes over. The 0.5-second full-quality Clouds profile with compact Rings estimates 427,224 bytes combined, leaving 15,144 bytes before resampler/routing. It has only 2,856 bytes beyond the required combined 4 KiB RAM and 8 KiB POOL reserves, so more resource/placement work is required before it can be accepted.

The size probe is compile-only; it does not instantiate, link into the firmware, or run these objects.
