# Freestanding C++ runtime audit

## Scope

This is a source audit of the reference FM1_Locus C++ support files, not a claim that they are compatible with the pinned RINGS INTO CLOUDS toolchain. The reference files were inspected on 2026-11-23:

- `firmware/cxx/runtime.cc`
- `firmware/cxx/algorithm`
- `firmware/cxx/new`
- `firmware/apps/locus/locus_engine.cc`

The reference repository is `stevexfer/FM1_Locus`. Its implementation is useful evidence, but it is not a drop-in runtime for this firmware.

## Findings

### Runtime hooks

The reference `runtime.cc` defines:

- `__cxa_pure_virtual()`, implemented as an infinite loop;
- `__errno()`, backed by one function-static integer.

Neither should be copied automatically. First inspect the undefined symbols emitted by the actual Rings/Clouds object set. If no object references a hook, do not add it. If `__cxa_pure_virtual` is required, decide deliberately how a pure-virtual call should fail on the FM-1; an unreported infinite loop is not an acceptable default for an audio instrument. A single global errno slot is not thread-local and must not be assumed safe across CPU0/CPU1. Prefer eliminating the dependency if upstream DSP does not need it.

### Placement construction

The reference `new` header supplies only placement new:

```cpp
inline void* operator new(size_t, void* p) { return p; }
```

This supports constructing DSP objects in statically reserved storage without a heap. It does not provide ordinary allocation. RINGS INTO CLOUDS should use explicit aligned storage and placement construction, and should not introduce `new`, `delete`, malloc-backed containers, or dynamic allocation in the audio path.

The placement-new declaration itself must be tested with the exact target compiler and required headers. Do not assume that the reference header is a complete C++ `<new>` implementation.

### Minimal algorithm header

The reference `algorithm` header implements a small subset of `std::algorithm`, including `min`, `max`, `swap`, `fill`, `copy`, `max_element`, `rotate` and `sort`. Its `sort` is insertion sort, not the standard library's introsort implementation. Although it may be adequate for a small bounded collection, it must not be substituted without checking every call site's maximum range and execution context.

In particular, Rings' delay-line reset uses `std::fill`; this is a concrete dependency that must be satisfied by either a target-compatible standard header or a reviewed local implementation. The earlier C++ probe uses `-nostdinc++` and does not include real upstream headers, so its success would not prove this dependency works.

## Required target checks before adopting any runtime code

1. Compile the actual pinned Rings and Clouds translation units with generated dependency files and the proposed freestanding include path.
2. Inspect undefined symbols from every object; add only the exact required runtime hooks.
3. Confirm no unexpected heap, exception, RTTI, thread-safe static initialisation, global constructor, destructor registration, or soft-float helper dependency.
4. Check section tables and the final target link for `.init_array`, `.fini_array`, `.eh_frame`, unexpected TLS, and unresolved C++ ABI symbols.
5. Compile at the firmware's actual optimisation level and FPU ABI. The existing probe uses `-O2`; the firmware C unity unit uses `-Os`.
6. Keep all DSP class types behind a narrow `extern "C"` interface using fixed-width integers, pointers and bounded buffers. Do not pass floating-point values across the C/C++ boundary until the target ABI is explicitly proven.
7. Run the final link with the actual FM-1 linker script and the same startup, math and compiler-runtime libraries as the production image. A relocatable `ld -r` combination is not sufficient.

## Decision

Do not copy the LOCUS `firmware/cxx/` directory wholesale. Build the smallest freestanding support layer justified by the pinned upstream source's actual compiler output. Keep this work separate from the production C unity build until the full target link and memory report are available.

No C++ runtime files have been added to the firmware, and no target compiler or link test is claimed by this audit.
