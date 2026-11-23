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

Before importing DSP state, obtain a real baseline linker map and inventory every `.pool`, `.bss` and stack allocation. Evaluate candidate trade-offs with linked measurements, including the existing 128 KiB master tempo delay and slicer recording memory. Preserve full Clouds buffers and algorithms unless a clearly labelled lower-quality profile is deliberately designed and tested. Account for the large buffer in POOL and the small buffer in ordinary RAM separately. A feature must not silently disappear to make the linker pass.

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


## Follow-up source inventory (2026-11-23)

The pinned upstream trees were queried recursively, and the LOCUS source manifest and engine translation unit were inspected. This narrows the initial DSP candidate set, but it is not yet a compiler-generated transitive dependency list.

### Candidate translation units

For the Rings `Part` / `Strummer` path:

- `rings/dsp/part.cc`
- `rings/dsp/resonator.cc`
- `rings/dsp/fm_voice.cc`
- `rings/dsp/string.cc`
- `rings/resources.cc`
- `rings/dsp/strummer.h` is header-only in this revision.
- `rings/dsp/string_synth_*.cc` is not part of the Part path unless the excluded String-and-Reverb model is retained. LOCUS removes that model and its Easter-egg synth files; this is a documented fidelity trade-off, not a full stock Rings port.

For Clouds `GranularProcessor`:

- `clouds/dsp/granular_processor.cc`
- `clouds/dsp/correlator.cc`
- `clouds/dsp/mu_law.cc`
- `clouds/dsp/pvoc/frame_transformation.cc`
- `clouds/dsp/pvoc/phase_vocoder.cc`
- `clouds/dsp/pvoc/stft.cc`
- `clouds/resources.cc`

For stmlib, the directly referenced implementation candidates include:

- `stmlib/utils/random.cc`
- `stmlib/dsp/atan.cc`
- `stmlib/dsp/units.cc`

The include scan also confirms substantial header-only dependencies in `stmlib/dsp`, `stmlib/utils`, Rings DSP, and Clouds DSP. This list must be confirmed with generated compiler dependency files and a link before it is treated as final. Do not recursively compile every `.cc` under the upstream trees: that would include module drivers, tests, bootloaders, UI and unrelated modules.

### Exact LOCUS build-system behaviour

Further inspection of LOCUS `tools/build.py` establishes a more precise reference than a generic C++-support recipe:

- `clang++` is invoked as `pi32v2/bin/clang++ -target pi32v2`, with the target sysroot include path.
- C++ uses `-mcpu=r3 -mfprev1 -O2 -std=gnu++11`, no exceptions/RTTI/thread-safe statics/CXA atexit, `-nostdinc++`, section splitting, dependency generation and a 1024-byte frame warning.
- The AC79 FPU ABI is single-precision. LOCUS deliberately uses integer and pointer arguments across the generic-C / FPU-C++ boundary; C must not casually pass floats to C++.
- LOCUS discovers C++ sources from the app directory and the three explicit directories in `third_party.txt`, and compiles a dedicated `firmware/cxx/runtime.cc`.
- The linker receives all C++ objects plus `libm.a` and `libcompiler_rt.a` inside a linker group.
- Its link checker rejects unexpected sections such as `.init_array`, `.eh_frame`, and soft-float helper symbols; its C++ build does not permit dynamic global constructors.
- Minimal replacement headers are local to the C++ path. They are not a complete standard library and must be added only when the exact dependency scan requires them.

The current RINGS INTO CLOUDS build is structurally different: one C unity translation unit, a direct app link, and a size-optimization pass over the C unity unit. The safe adaptation is therefore a separate object list and explicit C++ compile helper, preserving the current C pipeline and its post-link checks. The LOCUS build script itself should not be copied wholesale.

### Important source-fidelity decision

The LOCUS integration is not a byte-for-byte stock Rings implementation. It removes the String-and-Reverb resonator model (and the associated 64 KiB reverb buffer) to fit the FM-1. **RINGS INTO CLOUDS has explicitly adopted this omission by user decision (2026-11-23).** The module must be labelled an adapted Rings port with five original models; the UI must not advertise String and Reverb. The remaining five models retain their fidelity requirements. No Rings source has been imported yet.

### Current status

- [x] Enumerated upstream Rings/Clouds C++ translation units at the pinned commit.
- [x] Identified the LOCUS candidate source files and the non-portable parts of its scheduler/build.
- [ ] Confirm the candidate list using compiler-generated dependency files.
- [ ] Establish exact target toolchain and C++ runtime availability.
- [ ] Measure actual baseline map and all statically allocated memory.
- [x] User decision: omit Rings String-and-Reverb and its dedicated reverb buffer; support the other five original models.
- [ ] Only then import and compile the DSP.


## Memory-section correction from the LOCUS allocation declarations

A closer inspection of `firmware/apps/locus/locus_engine.cc` found an important placement detail that the earlier aggregate wording obscured:

- `clouds_large[118784]` is explicitly marked `FW_POOL`.
- `clouds_small[65536 - 128]` (65,408 bytes) has no `FW_POOL` attribute, so it occupies ordinary `.bss` RAM.
- The combined two Clouds buffers are still 184,192 bytes, but they do **not** both consume the 360 KiB POOL region.

This makes the RAM region an equally serious gate. The base linker provides only 72 KiB (73,728 bytes) for `.data/.bss`. A 65,408-byte Clouds array would leave just 8,320 bytes for all existing static RAM data and the required 4 KiB headroom. This is before any other ordinary-RAM buffers or runtime state.

For POOL, adding only the 118,784-byte large buffer to the earlier 236,220-byte known subtotal gives 355,004 bytes of 368,640, leaving 13,636 bytes before Rings/Strummer state, Clouds object state, resampler histories, FIFOs, batch buffers, omitted current allocations and the required 8 KiB headroom. That is also not a viable complete integration without a deliberate memory-layout/resource redesign.

The next memory audit must therefore report **POOL and ordinary RAM separately**, and any proposal to relocate the 65,408-byte small Clouds buffer must identify a real available memory region and its linker/runtime constraints. Do not treat the 184,192-byte pair as a single POOL allocation.


## Dual-instance Rings integration implications (2026-11-23)

The product requirement is two simultaneous independent Rings instances (RINGS A and RINGS B), not one shared Rings object. The inherited Felucca engine architecture confirms four tracks and one shared eight-sounding-voice budget, but its current large-engine memory design is a per-track overlay: `eng_mem[NPART]` allocates one `ENG_MEM_PART` region per part and reuses that region when the part changes engine. The current default region is 12,888 bytes. It is sized for the existing PHYS/SYMP state, not assumed sufficient for the upstream Rings `Part` plus Strummer and associated buffers.

Consequently:

- Do not place the full Rings object in a shared global singleton or in a single shared engine-memory region.
- Do not assume the existing 12,888-byte `ENG_MEM_PART` fits Rings. Obtain target-compiler `sizeof` measurements for the exact pinned source revision, including every wrapper-owned buffer and strummer.
- The likely ownership model is one dedicated Rings runtime state per FM-1 track that selects Rings, with a stable mapping from track index to Rings instance. For the two-instance target, RINGS A and RINGS B occupy separate parts and separate state blocks.
- The current per-track overlay cannot by itself preserve large Rings state while a track switches to another engine. Decide whether Rings state is a dedicated always-resident per-track allocation or whether switching away intentionally serializes and reconstructs it. Do not silently lose resonator tails or preset state on engine changes.
- Account for the aggregate memory cost across all four possible tracks, not just the desired two-instance patch, and explicitly cap the supported simultaneous Rings count if the measured resource profile requires it. The product minimum is two.
- Both instances use the existing shared eight-voice allocator. Verify the Rings voice/event adapter against the allocator's note-on, note-off, steal and retrigger lifecycle. A stolen voice must release the correct instance's excitation/voice state without touching the other instance.
- All expensive Rings setup/configuration must occur outside the audio interrupt. The audio callback receives only bounded block processing calls over already-constructed state.

Before writing the live adapter, produce a target-side memory report for: one Rings instance; two Rings instances; two Rings plus full Clouds; and two Rings plus Clouds with the intended routing, effects and MIDI sync. The two-instance requirement must be treated as a first-class resource test, not postponed until after the single-instance implementation.


## Build-pipeline blocker confirmed in current build script (2026-11-23)

A direct source inspection of `tools/build.py` confirms that the current application build is a single C translation unit:
- It compiles only `firmware/src/felucca.c` to one LLVM IR/object file.
- The application link step passes the startup/interrupt assembly objects and `felucca.o`; there is no source/object list for separate C++ translation units.
- The compiler helper currently invokes the JieLi `pi32v2/bin/clang` with `-target pi32v2`, and the linker is invoked directly as `pi32v2/bin/ld`.
- No C++ standard library, exception runtime, RTTI or global-constructor startup support is configured by this build script.

### Required minimal C++ integration, before importing DSP

1. Add a separate, explicit C++ source manifest for the pinned Rings/stmlib translation units; do not recursively compile upstream directories.
2. Compile with the same `pi32v2` target, ABI, optimisation and section flags as the C firmware, initially using `-fno-exceptions -fno-rtti -fno-threadsafe-statics` and no standard library unless a verified source dependency requires a runtime feature.
3. Ensure C++ objects export only narrow `extern "C"` wrapper functions to the C engine table; never expose C++ class layouts or STL containers across the ABI.
4. Add linker inputs for the C++ objects and prove symbol resolution, global/static initialisation behaviour, and final image sections. Prefer constant/static initialization and explicit prepare functions over global constructors.
5. Add dependency-file generation for the selected upstream files, so missing transitive translation units are detected deterministically.
6. Add a minimal compile/link smoke target that builds one trivial C++ wrapper and calls it from C before adding Rings.
7. Only then add the pinned Rings translation units, compile, inspect unresolved symbols and linker map, and measure target `sizeof` for all runtime objects.

This is a confirmed integration blocker, not proof that the JieLi compiler cannot compile C++. The compiler executable is Clang, but its target-specific C++ ABI/runtime support must be demonstrated by the smoke test before the Rings port is treated as buildable.


## Required no-reverb source adaptation (2026-11-23)

The pinned upstream source was inspected directly after the approved five-model decision. There is an important safety detail: simply passing `nullptr` to `rings::Part::Init(uint16_t*)` is **not safe**. `Part::Init()` unconditionally calls `reverb_.Init(reverb_buffer)`; `Reverb::Init()` calls `FxEngine::Init()`; and `FxEngine::Init()` immediately calls `Clear()`, which writes across the supplied buffer. A null pointer would therefore be dereferenced during initialization even if the String-and-Reverb model is never selected.

The port must make an explicit source patch before either instance is initialized:

- Remove the `Reverb reverb_` member from `rings::Part` so its 65,536-byte backing buffer is not embedded in each object.
- Remove the unconditional `reverb_.Init()` call from `Part::Init()`.
- Remove the String-and-Reverb-only reverb processing block at the end of `Part::Process()`.
- Remove the String-and-Reverb-only damping special case in `RenderStringVoice()`.
- Exclude the String-and-Reverb enum value from the public FM-1 model mapping and clamp/validate all model values to the five supported entries.
- Keep all five retained model render paths and their original per-model gains unchanged.
- Add tests proving both Rings instances initialize without reverb storage, all five retained models render, invalid/omitted model values cannot reach the excluded branch, and A/B state remains independent.

Do not substitute a null buffer, a dummy buffer, or a shared reverb buffer. The firmware's shared effects and Clouds remain separate signal-chain modules. This is a documented source-level adaptation; it is not yet implemented or tested.


## Stereo engine-output integration gate (source audit, 2026-11-23)

The Felucca engine ABI and mixer were inspected directly in `firmware/engines/src/felucca_engine.h`, `firmware/src/voice.c`, and `firmware/src/fx.c`. This reveals a second integration blocker beyond C++ compilation:

- `track_render()` clears one mono `out[n]` buffer, invokes the engine's per-voice `render` callback, then invokes optional `post(track, out, n)`. The post callback runs once per track block, including the no-active-voice tail path, but receives only that mono buffer.
- `mix_part()` subsequently applies mono DIST/INSERT/SLICER processing and folds that mono signal into the stereo dry mix using the track PAN law. Chorus, delay and reverb sends are also derived from that mono signal.
- The Rings `Part` API produces distinct `out` and `aux` signals. Mapping those to the single Felucca `post` buffer would discard the independent output; summing them immediately would also prevent real modular routing of the two outputs.

### Required adapter shape

Do not force Rings through the existing mono post callback. Add a narrowly scoped, optional per-track stereo engine-output path (or equivalent sidecar bus) with these properties:

1. A Rings track owns dedicated, statically allocated left/right output scratch for the current bounded block. Its persistent `Part`, `Strummer`, event mailbox and scratch are separate for RINGS A and RINGS B.
2. The Rings post-processing call writes the original Rings `out` and `aux` channels into separate buffers. The two channels remain separately addressable by the patch graph.
3. The mixer consumes the stereo pair at a defined point in the per-track path, applies track level/pan and master summing without silently collapsing the pair. Any mono-only insert or send path must have an explicit documented policy (for example, a deliberate fold-down for a shared mono send while preserving the dry stereo pair).
4. The stereo callback must run once per track block, not once per host voice, and must remain callable while resonator tails continue after host note release.
5. Any new bus storage must be included in the POOL/RAM report and in CPU2 ownership analysis. If CPU2 renders a track, the sidecar buffers must follow the same ownership and handoff rules as the existing `mixsum_t` buffers; no concurrent writes or stale reads.
6. The patch graph may expose Rings `OUT` and `AUX` only after each is connected to a real mixer/bus input. The UI must not show an independent port that is merely decorative.

The first implementation should preserve Rings OUT and AUX as two distinct dry signals and document how they enter shared mono effects. A later graph revision can route either output to Clouds or another processor independently. Do not change the original Rings DSP to make its output fit the host's mono ABI.

### Build and memory implications

The current app linker places `.bss` in a 72 KiB RAM region and large buffers in a separate 360 KiB POOL region. The linker script does not currently emit a map file in the normal build command; the build checker reports aggregate `.bss` and `.pool` use from linker symbols. Add a map/report artefact before the first imported DSP objects so the exact owner of each allocation is visible. A linker map is useful diagnostics, but it does not replace the existing 4 KiB RAM and 8 KiB POOL headroom checks.

No compiler invocation has been run here, so availability of `clang++`, C++ runtime compatibility, object sizes and memory headroom remain unverified. Do not treat the source-level design as a successful build.


## C++ smoke-probe scope clarified (2026-11-23)

The repository's current `tools/check_cpp_toolchain.py` has been inspected. It is a useful first gate, but its exact coverage is narrower than a complete C++ firmware link:

- It checks that `clang++`, `clang` and `ld` executables exist in the configured JieLi toolchain.
- It compiles one C caller and one C++11 object with `-target pi32v2 -mcpu=r3 -mfprev1`, `-fno-exceptions`, `-fno-rtti`, `-fno-threadsafe-statics`, `-fno-use-cxa-atexit` and `-nostdinc++`.
- It combines the two objects using `ld -r`. It does not perform a final firmware link, link a C++ runtime, resolve `new`/placement-new or pure-virtual support, exercise static initialization, or validate upstream DSP dependencies.
- It uses `-O2`, while the current C unity build's normal C flags use `-Os`. This is acceptable for the minimal ABI probe, but not evidence of final DSP code size or CPU cost.
- `BUILDING.md` documents how to run it, but the probe has not been executed in this work session. No PASS is claimed.

The next build-system milestone is therefore not just “clang++ exists”: it is a staged proof. First run the existing object/ABI probe on the actual JieLi toolchain; then add a minimal freestanding C++ runtime only for symbols proven necessary; then perform a full final-link smoke image using the real linker script and existing `build.py` safety checks. Keep `.init_array`, exception/unwind support, RTTI, unexpected soft-float helpers and unbounded constructors out unless a deliberate, measured design proves they are needed.

## Linker accounting: current evidence and missing artefacts

The actual `firmware/app.ld` defines a 72 KiB ordinary RAM region and 360 KiB POOL region, with `.bss` and `.pool` linker symbols. `tools/build.py` currently reports aggregate RAM and POOL consumption from `_bss_end`, `_pool_start` and `_pool_end`, and enforces 4 KiB RAM / 8 KiB POOL spare. It does not currently emit a linker map file or a per-symbol allocation report. The `ld` invocation is direct, with no C++ object list or map-output option.

Before importing DSP buffers, add an optional diagnostic linker map (and a parsed largest-symbol/allocation report) without changing memory regions. Verify the JieLi linker's supported map-file syntax before wiring it into the production build. Preserve the current hard headroom checks and include `.data`, `.bss`, `.pool`, stack reservations, CPU2 buffers, and any C++ runtime objects in the accounting.

## Clouds memory placement: explicit region split

The LOCUS reference places its 118,784-byte large Clouds buffer in POOL but its 65,408-byte small buffer in ordinary `.bss`. On this project's current 72 KiB RAM region, that single small buffer would leave only 8,320 bytes for every other `.data/.bss` allocation, before the required 4 KiB headroom. In POOL, adding the large buffer to the previously inventoried 236,220-byte known subtotal yields 355,004 bytes of 368,640, leaving 13,636 bytes before all Rings state, Clouds object state, conversion/FIFO buffers and the required 8 KiB headroom. Both regions are therefore independently blocked pending a measured layout redesign; do not treat the two Clouds buffers as one POOL allocation or claim that removing Rings reverb solves the Clouds placement problem.

## Project-owned Rings source patch manifest

The exact no-reverb five-model source changes are now recorded in [RINGS_UPSTREAM_PATCH_MANIFEST.md](RINGS_UPSTREAM_PATCH_MANIFEST.md). It specifies the enum, `Part::Init` signature, reverb member/init/process removal, retained String dispersion, source pruning, dual-instance invariants and validation gates. This is a reviewable patch specification; the upstream code has not yet been imported or compiled.


## Dual Rings object-layout finding (2026-11-23)

The pinned source headers reveal a hard mutable-state floor that must be included before the first C++ object is linked. Each `rings::Part` contains eight `String` objects (`kMaxPolyphony = 4`, `kNumStrings = 8`). Each `String` embeds a 2,048-float delay line and a 1,024-float stiffness delay line; the pinned stmlib `DelayLine` template stores its array inline. At 32-bit float storage this is 12,288 bytes per String, 98,304 bytes per Part, and **196,608 bytes (192 KiB) for two independent Parts**. This excludes all other Part members and wrapper/runtime buffers.

This is a source-derived array-storage lower bound, not a measured `sizeof(Part)` or linker placement. The five-model no-reverb decision removes the two dedicated 64 KiB reverb histories, but does not remove these String arrays: they are members of every Part regardless of selected model. Do not shrink or share them as a resource shortcut. The target compiler's actual class sizes and section placement remain a mandatory gate.