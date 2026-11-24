# C++ DSP port plan: Rings + Clouds

## Purpose and status

This document records the next implementation boundary for bringing the pinned Mutable Instruments Rings and Clouds DSP into RINGS INTO CLOUDS. The pinned source submodules are now present, and a compile-only target check has successfully compiled 15 Rings/Clouds/stmlib C++ translation units for pi32v2. No DSP object is linked into the production firmware, instantiated, or run yet.

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

The target C++ smoke and 15-translation-unit compile-only checks now pass using the pinned JieLi compiler, target sysroot and a minimal freestanding header/runtime layer. The final production link, unresolved runtime symbols, constructor sections and FPU ABI boundary still require validation.

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

After the user's approved legacy-feature cuts, the known POOL subtotal is now 56,416 bytes before omitted allocations. The LOCUS Clouds buffer pair still totals 184,192 bytes across POOL and ordinary RAM, and two original Rings Parts have a source-declared 196,608-byte delay-line floor. The revised combined arithmetic is documented in `docs/MEMORY_PROFILE_OPTIONS.md`; it remains a tight, unmeasured fit gate.

Before importing DSP state, obtain a real baseline linker map and inventory every `.pool`, `.bss` and stack allocation. The global tempo delay, global chorus/reverb buses and performance-loop recorder have now been removed by user approval; do not reintroduce them as hidden memory consumers. Preserve full Clouds buffers and algorithms. Account for the large buffer in POOL and the small buffer in ordinary RAM separately. A future reverb must be an optional modular processor with an explicit budget.

## Next implementation sequence

- [x] Confirm target toolchain `clang++` availability and compile/link C/C++ ABI smoke test.
- [ ] Inspect the current linker script, map generation and every static pool allocation.
- [x] Compile the 15 selected pinned Rings/Clouds/stmlib C++ translation units; [ ] generate the final dependency-derived source manifest and complete link.
- [ ] Create an independent upstream patch manifest with licences and rationale.
- [ ] Build the source-only import and measure image, RAM and pool growth.
- [ ] Add a standalone Rings harness and compare output to upstream at matched sample rate.
- [ ] Add a standalone full-buffer Clouds harness and validate all stock playback modes.
- [ ] Implement and verify the target-specific sample-rate conversion.
- [ ] Connect Rings to Clouds with bounded buffers and measure worst-case processing deadlines.
- [ ] Only then expose real module ports to the modular patch graph.

## Freestanding runtime audit

The reference LOCUS runtime and minimal headers have now been inspected separately. See [`docs/CPP_FREESTANDING_RUNTIME_AUDIT.md`](CPP_FREESTANDING_RUNTIME_AUDIT.md) for the exact findings and the target checks required before adopting any runtime hooks or replacement headers. In particular, do not copy LOCUS's infinite-loop pure-virtual handler, single global errno slot, or insertion-sort `std::sort` implementation without proving the pinned DSP actually needs them and that their use is safe.

## Current truth

The pinned Rings/Clouds/stmlib submodules are present and 15 upstream C++ translation units compile for the FM-1 target. A compile-time `sizeof` probe now measures `rings::Part`, `rings::String`, `rings::Strummer` and `clouds::GranularProcessor`. The C production build still does not link these objects; no DSP object is instantiated or run, and no Rings/Clouds audio, Harbor or physical FM-1 test is claimed.


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
- [x] Establish target C++ compiler, minimal header layer and compile-only runtime prerequisites; [ ] verify all final-link runtime symbols.
- [ ] Measure actual baseline map and all statically allocated memory.
- [x] User decision: omit Rings String-and-Reverb and its dedicated reverb buffer; support the other five original models.
- [ ] Only then import and compile the DSP.


## Memory-section correction from the LOCUS allocation declarations

A closer inspection of `firmware/apps/locus/locus_engine.cc` found an important placement detail that the earlier aggregate wording obscured:

- `clouds_large[118784]` is explicitly marked `FW_POOL`.
- `clouds_small[65536 - 128]` (65,408 bytes) has no `FW_POOL` attribute, so it occupies ordinary `.bss` RAM.
- The combined two Clouds buffers are still 184,192 bytes, but they do **not** both consume the 360 KiB POOL region.

This makes the RAM region an equally serious gate. The base linker provides only 72 KiB (73,728 bytes) for `.data/.bss`. A 65,408-byte Clouds array would leave just 8,320 bytes for all existing static RAM data and the required 4 KiB headroom. This is before any other ordinary-RAM buffers or runtime state.

With the approved cuts, adding the 118,784-byte Clouds large buffer to the 56,416-byte remaining known POOL subtotal gives 175,200 bytes, leaving 193,440 bytes before Rings/Strummer state, Clouds object state, resampler histories, FIFOs, batch buffers and the required 8 KiB headroom. Two Rings Parts' 196,608-byte inline delay-line floor alone exceeds that remaining space by 3,168 bytes. Replacing the two selected track engine overlays could reduce the base subtotal by 25,776 bytes, but this still leaves only 22,608 bytes in POOL after those two Rings delay arrays and Clouds large buffer, before all other DSP state.

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

Do not substitute a null buffer, a dummy buffer, or a shared reverb buffer. Clouds remains a separate processor; any future reverb must be an explicit optional modular node. This is a documented source-level adaptation; it is not yet implemented or tested.


## Stereo engine-output integration gate (source audit, 2026-11-23)

The Felucca engine ABI and mixer were inspected directly in `firmware/engines/src/felucca_engine.h`, `firmware/src/voice.c`, and `firmware/src/fx.c`. This reveals a second integration blocker beyond C++ compilation:

- `track_render()` clears one mono `out[n]` buffer, invokes the engine's per-voice `render` callback, then invokes optional `post(track, out, n)`. The post callback runs once per track block, including the no-active-voice tail path, but receives only that mono buffer.
- `mix_part()` subsequently applies mono DIST/INSERT processing and folds that mono signal into the stereo dry mix using the track PAN law. The legacy global chorus, tempo-delay and reverb sends have been removed; future modules must use explicit graph connections.
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

The current app linker places `.bss` in a 72 KiB RAM region and large buffers in a separate 360 KiB POOL region. The current `tools/build.py` app link command already passes `-Map build/felucca.map`; the post-link checker reports aggregate `.bss` and `.pool` use from linker symbols. Preserve that map output when adding C++ objects, then add a parsed largest-symbol/allocation report so the owner of each imported DSP allocation is visible. A linker map is useful diagnostics, but it does not replace the existing 4 KiB RAM and 8 KiB POOL headroom checks.

No compiler invocation has been run here, so availability of `clang++`, C++ runtime compatibility, object sizes and memory headroom remain unverified. Do not treat the source-level design as a successful build.


## C++ smoke-probe scope clarified (2026-11-23)

The repository's current `tools/check_cpp_toolchain.py` has been inspected. It is a useful first gate, but its exact coverage is narrower than a complete C++ firmware link:

- It checks that `clang++`, `clang` and `ld` executables exist in the configured JieLi toolchain.
- It compiles one C caller and one C++11 object with `-target pi32v2 -mcpu=r3 -mfprev1`, `-fno-exceptions`, `-fno-rtti`, `-fno-threadsafe-statics`, `-fno-use-cxa-atexit` and `-nostdinc++`.
- The C++ object exercises placement construction, `std::fill`, `std::max_element`, and probe-only `<cmath>` / `<cstring>` header bridges. These are a narrow smoke subset based on direct includes found in candidate Rings/Clouds translation units; the transitive dependency audit remains incomplete.
- It combines the two objects using `ld -r`. It does not perform a final firmware link, resolve all C++ ABI/runtime or math-library symbols, exercise static initialization, or validate upstream DSP dependencies.
- It now uses `-Os`, matching the firmware's normal C unity build optimisation level. This does not prove final DSP code size or CPU cost.
- `BUILDING.md` documents how to run it, but the probe has not been executed in this work session. No PASS is claimed.

The next build-system milestone is therefore not just “clang++ exists”: it is a staged proof. First run the existing object/ABI probe on the actual JieLi toolchain; then add a minimal freestanding C++ runtime only for symbols proven necessary; then perform a full final-link smoke image using the real linker script and existing `build.py` safety checks. Keep `.init_array`, exception/unwind support, RTTI, unexpected soft-float helpers and unbounded constructors out unless a deliberate, measured design proves they are needed.

## Linker accounting: current evidence and missing artefacts

The actual `firmware/app.ld` defines a 72 KiB ordinary RAM region and 360 KiB POOL region, with `.bss` and `.pool` linker symbols. `tools/build.py` currently reports aggregate RAM and POOL consumption from `_bss_end`, `_pool_start` and `_pool_end`, enforces 4 KiB RAM / 8 KiB POOL spare, and already emits `build/felucca.map` through the app linker's `-Map` option. It does not yet parse that map into a per-symbol allocation report. The link is still C-only: there is no C++ object list or C++ runtime integration.

Before importing DSP buffers, add a parsed largest-symbol/allocation report using the existing map output, without changing memory regions. Preserve the current hard headroom checks and include `.data`, `.bss`, `.pool`, stack reservations, CPU2 buffers, and any C++ runtime objects in the accounting.

## Clouds memory placement: explicit region split

The LOCUS reference places its 118,784-byte large Clouds buffer in POOL but its 65,408-byte small buffer in ordinary `.bss`. On this project's current 72 KiB RAM region, that single small buffer would leave only 8,320 bytes for every other `.data/.bss` allocation, before the required 4 KiB headroom. In POOL, the approved-cut baseline plus the large Clouds buffer is 175,200 bytes, leaving 193,440 bytes before Rings and other DSP state. The two Rings delay-line arrays alone need 196,608 bytes, so the placement remains blocked without a deliberate layout redesign. Do not treat the two Clouds buffers as one POOL allocation.

## Project-owned Rings source patch manifest

The exact no-reverb five-model source changes are now recorded in [RINGS_UPSTREAM_PATCH_MANIFEST.md](RINGS_UPSTREAM_PATCH_MANIFEST.md). It specifies the enum, `Part::Init` signature, reverb member/init/process removal, retained String dispersion, source pruning, dual-instance invariants and validation gates. This is a reviewable patch specification; the upstream code has not yet been imported or compiled.


## Dual Rings object-layout finding (2026-11-23)

The pinned source headers reveal a hard mutable-state floor that must be included before the first C++ object is linked. Each `rings::Part` contains eight `String` objects (`kMaxPolyphony = 4`, `kNumStrings = 8`). Each `String` embeds a 2,048-float delay line and a 1,024-float stiffness delay line; the pinned stmlib `DelayLine` template stores its array inline. At 32-bit float storage this is 12,288 bytes per String, 98,304 bytes per Part, and **196,608 bytes (192 KiB) for two independent Parts**. This excludes all other Part members and wrapper/runtime buffers.

This is a source-derived array-storage lower bound, not a measured `sizeof(Part)` or linker placement. The five-model no-reverb decision removes the two dedicated 64 KiB reverb histories, but does not remove these String arrays: they are members of every Part regardless of selected model. Do not shrink or share them as a resource shortcut. The target compiler's actual class sizes and section placement remain a mandatory gate.

## Approved legacy-feature removal (2026-11-23)

The user approved a focused base firmware rather than carrying Felucca's general-purpose effects and live-loop recorder. The development branch now removes the 131,072-byte global tempo-delay line, 4,096-byte global chorus line, 11,868 bytes of global ROOM/SPRING/HALL reverb comb/allpass buffers, and the 32,768-byte performance-loop recorder store. The global FX DSP and their pages/sends are removed. The compact performance layer retains LPF, HPF, CRUSH, FLANGER, PHASER and track mutes; recording-based loop effects and throw-to-global-bus controls are removed. Per-track CHORUS insert is retired too, with its stored ID preserved as an OFF alias. Legacy project parameter IDs remain reserved and are ignored by the mixer.

A dedicated reverb remains a future product goal, but must be an optional modular graph node with measured instance memory, CPU, tail/bypass behaviour and preset persistence. It must not return as a permanent global bus. The revised source-declared memory arithmetic is in `docs/MEMORY_PROFILE_OPTIONS.md`.


## Measured-memory correction (2026-11-24)

The measured Slicer-excluded baseline is 56,036 bytes ordinary RAM plus 145,720 bytes POOL (201,756 bytes combined). Replacing two engine overlays with the two Rings Parts' 196,608-byte inline string-delay-line floor and adding the full 184,192-byte Clouds buffer pair projects to 556,780 bytes before the remaining Rings/Clouds runtime state. This exceeds the 442,368-byte RAM + POOL budget by 114,412 bytes. The earlier 411,440-byte source-only estimate omitted 145,340 bytes of measured ordinary-RAM and other POOL allocation; it is not a fit claim. See `MEMORY_PROFILE_OPTIONS.md` for the full arithmetic and diagnostic links. Phase 1 source import is therefore still blocked on a concrete, measured memory architecture.


## Math compatibility gate

The pinned Rings sources use `fabs` and `powf`; the current JieLi C++ toolchain does not find a system `math.h` in its default include path. The smoke probe now uses a freestanding `fabs` bridge and declares `powf`, but it does not prove the final link can resolve `powf`. Prefer the source-local RT60 coefficient approximation documented in `CPP_FREESTANDING_RUNTIME_AUDIT.md`, then compare host renders before adopting it. Keep the smoke probe advisory until the actual upstream C++ files compile and the final firmware link resolves every undefined symbol.


### Rings reverb exclusion patch

The pinned upstream `Part::Init()` unconditionally calls `reverb_.Init(reverb_buffer)`; the upstream `FxEngine::Init()` immediately clears the caller's 32,768-sample `uint16_t` buffer. Therefore `Part::Init(NULL)` is unsafe in unmodified upstream code. FM1_Locus adds an explicit null guard because it does not offer `RESONATOR_MODEL_STRING_AND_REVERB`. Our patch must do the same or remove the unused reverb member and model path. The external 65,536-byte reverb buffer is not part of the proposed memory profile. The small embedded Reverb object remains part of `sizeof(Part)` unless removed locally.


## Verified FM-1 C++ integration precedent

The sibling FM-1 project `stevexfer/FM1_Locus` already builds the same pinned Rings and Clouds C++ DSP for the JieLi AC79 target. Its `tools/build.py` compiles every `.cc` under the app and the `third_party.txt` directories with `clang++`, `-mcpu=r3`, `-mfprev1`, `-std=gnu++11`, `-nostdinc++`, no exceptions/RTTI/static constructors, and the AC79 `pi32v2/include` C header sysroot; it links `libm.a` and `libcompiler_rt.a`. It supplies a small freestanding C++ header set under `firmware/cxx/` (`algorithm`, `cmath`, `cstring`, `cstdlib`, `new`) and a minimal runtime. This is direct evidence that a full C++ port is feasible on this hardware/toolchain, not merely the small ABI probe.

Our smoke probe is being aligned with that proven header arrangement: use the target toolchain's actual C header sysroot and the same thin `cmath`/`cstring` wrappers, rather than pretending compiler builtins are a substitute for the target math headers. Next build milestone should be a compile-only pass over the pinned upstream Rings/Clouds translation units with the minimal required header/runtime files, followed by a real link and measured object size. Do not yet import the whole Locus engine or its two-core scheduler.


## Target size-probe result (2026-11-24)

The target compile-only check measured `rings::Part` at 110,452 B, `rings::String` at 12,428 B, `rings::Strummer` at 524 B and `clouds::GranularProcessor` at 8,684 B. See `docs/MEMORY_PROFILE_OPTIONS.md` for the combined budget calculation. These sizes are for the pinned upstream class layout before the approved five-model patch removes the embedded Rings Reverb member; they do not include the external Rings reverb buffer or Clouds external buffers. The compile-only check does not link or instantiate DSP objects.


## Compile-only five-model source overlay

The target compile check now applies a local source overlay (without modifying the pinned upstream submodule) that removes `RESONATOR_MODEL_STRING_AND_REVERB`, the embedded Rings `Reverb` member, its initialisation and its processing path. The Part initialiser becomes parameterless; it no longer accepts a null or dummy reverb-buffer pointer. The five retained model implementations are otherwise left unchanged. This overlay is a compile/memory-validation patch only; it is not yet part of the linked firmware audio path.
