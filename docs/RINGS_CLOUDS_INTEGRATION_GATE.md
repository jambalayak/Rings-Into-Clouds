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

FM1_Locus reports 184 KiB of Clouds buffers, in addition to the Rings object/state, resampler histories, FIFOs, batch buffers and other working state. This is not a small incremental allocation. The current pool cannot be assumed to have room for it.

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
- Use the measured current codec rate.
- Test all supported resonator models, excitation, tune, structure, brightness, damping and position.
- Keep the original Rings model/polyphony semantics; any omitted model must be an explicit resource decision.
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
