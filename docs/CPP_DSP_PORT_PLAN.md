# C++ DSP port plan: Rings + Clouds

## Purpose and status

This document records the next implementation boundary for bringing the pinned Mutable Instruments Rings and Clouds DSP into RINGS INTO CLOUDS. It is an engineering plan, not an implementation claim: no C++ source has been imported, compiled or run in this repository.

The reference is the FM1_Locus integration by Steve Xfer, but only its build/runtime and DSP dependency findings are reused. Its application, audio scheduler, sample-rate converter and memory layout are not portable unchanged.

## Reference implementation findings

Inspected files in `stevexfer/FM1_Locus`:

- `tools/build.py`: separate C++ compilation path, source discovery, dependency files, target-specific flags and final object linking.
- `firmware/apps/locus/third_party.txt`: explicitly lists the Rings, Clouds and stmlib source roots.
- `firmware/apps/locus/build.txt`: adds the eurorack include root.
- `firmware/cxx/runtime.cc`: supplies `__cxa_pure_virtual` and `__errno`.
- `firmware/cxx/algorithm`, `cmath`, `new`, plus `cstdio`, `cstdlib`, and `cstring`: minimal replacement headers for a freestanding C++ build.
- `firmware/apps/locus/locus_engine.cc`: placement-news the DSP objects, keeps C++ types internal, and exports a narrow `extern "C"` API.
- `firmware/apps/locus/locus.h`: demonstrates the intended C/C++ boundary: integer parameters, event flags, and pointers only.

The reference C++ flags include `-target pi32v2`, `-mcpu=r3`, `-mfprev1`, `-std=gnu++11`, `-fno-exceptions`, `-fno-rtti`, `-fno-threadsafe-statics`, `-fno-use-cxa-atexit`, `-nostdinc++`, function/data sections, and the local C++ header directory. The reference also links its runtime object and the normal math/compiler runtime libraries.

These flags are a reference, not approved settings for this repository. Confirm the exact compiler binaries, target ABI, FPU calling convention and linker behaviour against the installed JieLi toolchain and this project's startup/linker setup before adopting them.

## Source and dependency boundary

The upstream DSP revisions already recorded in `RINGS_CLOUDS_INTEGRATION_GATE.md` remain the only approved fidelity baseline:

- Rings and Clouds: `pichenettes/eurorack`, commit `08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4`.
- stmlib: `pichenettes/stmlib`, commit `d18def816c51d1da0c108236928b2bbd25c17481`.

The FM1_Locus patch manifest identifies the local changes that must be independently reviewed before porting: Rings sample-rate constant; removal of its 64 KiB string/reverb model and unused Disastrous Peace code; a public pre-audio `Configure()` operation; Clouds debug-pin include removal; one grain-window boundary correction; optional read-only view accessors; and a signed-index correction in stmlib FFT code.

Do not copy these changes as an opaque patch. Each must be checked against the exact upstream source, and any change affecting models, sound, quality, or observable behaviour must be listed in our own patch manifest. In particular, omitting Rings' string/reverb model is a fidelity reduction and must be clearly exposed as such if chosen.

The reference app's DSP include roots are `rings/`, `clouds/`, and `stmlib/`. Its integration uses Rings `Part` and `Strummer`, and Clouds `GranularProcessor`. The source import should include only the transitive DSP source/header dependencies required by these classes, their resources and stmlib—not module drivers, panel UI, calibration, settings or unrelated application code. Generate the final exact source list from compiler dependency output rather than guessing it.

## Proposed build-system adaptation

1. Keep the current Felucca C unity translation unit and its existing compile path unchanged initially.
2. Add a dedicated, explicit C++ source manifest under a project-owned directory (for example `firmware/dsp/third_party_sources.txt`). Do not recursively compile every upstream C++ file.
3. Add a C++ compile helper to `tools/build.py` that invokes the toolchain's `clang++` for each listed source and emits a distinct object and dependency file. Confirm that the toolchain actually contains a working `clang++` executable before making it a hard requirement.
4. Use project-owned, minimal C++ compatibility headers only for headers proven necessary by the compiler. Do not shadow C headers or add an incomplete general-purpose C++ standard library.
5. Add the minimal runtime only when link diagnostics prove its symbols are needed. Placement-new support, pure-virtual handling, errno, global constructors and static destruction must each be considered explicitly.
6. Link C and C++ objects with the same target ABI and compatible floating-point conventions. Inspect the final ELF for unexpected runtime/library pulls, constructor sections and unresolved symbols.
7. Expose DSP through a small C ABI header and wrapper. C code must not include C++ class headers or depend on class layout. Avoid passing floating-point values across a generic/FPU ABI boundary until verified; scaled integer parameters and audio-buffer pointers are safer.
8. Add a build-only smoke target that compiles and links a tiny C++ object using the same flags and runtime without instantiating Rings or Clouds. This isolates toolchain/ABI/runtime problems from DSP dependency problems.
9. Add Rings and Clouds objects only after the smoke target is reproducible. Keep the DSP disabled from the live audio callback until standalone tests and memory accounting are complete.

## Audio-rate and scheduling implications

The reference LOCUS scheduler is designed around a 48-frame codec tick and a 32-frame Clouds tick (3:2), with 24-frame Rings blocks. This base firmware's documented timer rate is approximately 44,117.65 Hz, so that scheduler and its polyphase coefficients cannot be copied.

For a 32,000 Hz Clouds processing clock, the nominal ratio is approximately 1.3787 input frames per Clouds frame. The actual codec clock must be measured/confirmed from the target clock configuration. Select a rational conversion ratio from the measured clock and the Clouds processing rate, then design and test a corresponding stereo polyphase converter. Test passband, alias rejection, phase/group delay, channel matching, startup and long-run FIFO drift. Do not use a crude sample skip/duplicate converter.

The existing firmware's 128-frame audio half-buffer and 32-sample control block are the scheduling starting point. Do not transplant LOCUS's 48-frame batches, 256-frame interrupt, or CPU2 ownership scheme. Build a deterministic one-core schedule first; then evaluate optional CPU2 use and a deadline-safe fallback.

Clouds `Prepare` work (buffer initialization, time-stretcher search and spectral FFT preparation) must run outside the audio interrupt. The interrupt may only call bounded processing functions on already-prepared state.

## Memory decision gate

The previous integration-gate arithmetic remains a lower bound: the 360 KiB pool has a known 236,220-byte subtotal before omitted allocations, while the LOCUS Clouds buffer pair alone totals 184,192 bytes. This leaves no credible space for full Clouds plus Rings, conversion histories, FIFOs, routing buffers and mandatory headroom without a deliberate resource-profile change.

Before importing DSP state, obtain a real baseline linker map and inventory every `.pool`, `.bss` and stack allocation. Evaluate candidate trade-offs with linked measurements, including the existing 128 KiB master tempo delay and slicer recording memory. Preserve full Clouds buffers and algorithms unless a clearly labelled lower-quality profile is deliberately designed and tested. A feature must not silently disappear to make the linker pass.

## Next implementation sequence

- [ ] Confirm target toolchain `clang++` availability/version and compile/link ABI smoke test.
- [ ] Inspect the current linker script, map generation and every static pool allocation.
- [ ] Generate an exact transitive C++ source/header list for Rings `Part`, `Strummer`, Clouds `GranularProcessor` and stmlib.
- [ ] Create an independent upstream patch manifest with licences and rationale.
- [ ] Build the source-only import and measure image, RAM and pool growth.
- [ ] Add a standalone Rings harness and compare output to upstream at matched sample rate.
- [ ] Add a standalone full-buffer Clouds harness and validate all stock playback modes.
- [ ] Implement and verify the target-specific sample-rate conversion.
- [ ] Connect Rings to Clouds with bounded buffers and measure worst-case processing deadlines.
- [ ] Only then expose real module ports to the modular patch graph.

## Current truth

The repository currently contains planning documents only for this integration. No Rings/Clouds source has been imported or built; no firmware build, emulator test, Harbor test or physical FM-1 test is claimed.
