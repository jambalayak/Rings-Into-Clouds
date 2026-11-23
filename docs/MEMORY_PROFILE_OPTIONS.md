# Rings + Clouds memory profile options

## Purpose and status

This is a planning calculation based on source-declared static buffers and the current linker regions. It is not a measured linker map and does not authorize removing existing features. The full Rings + Clouds port needs an explicit memory profile before DSP state is imported.

## Current memory layout

`firmware/app.ld` divides the main SRAM budget into:

- ordinary RAM: 72 KiB (73,728 bytes), for `.data/.bss`;
- POOL: 360 KiB (368,640 bytes), for large static buffers.

The build requires at least 4 KiB ordinary-RAM headroom and 8 KiB POOL headroom.

The current source-declared POOL subtotal previously inventoried is 236,220 bytes. It includes the 131,072-byte master tempo delay and 32,768 bytes of SLICER recording buffers. It is a lower bound: HALL state, insert state and any allocations not yet enumerated must be measured.

## What the LOCUS source actually allocates

In `FM1_Locus/firmware/apps/locus/locus_engine.cc`:

- `clouds_large[118784]` is marked `FW_POOL`;
- `clouds_small[65408]` has no `FW_POOL` marker and therefore occupies ordinary `.bss`;
- Rings `Part`, Rings `Strummer`, Clouds processor object, batches, resampler histories and FIFOs have additional allocations.

The 184,192-byte Clouds buffer pair therefore crosses two memory regions. Placing the 65,408-byte small buffer in this project's current 72 KiB RAM region would leave only 8,320 bytes for all other .bss before the 4 KiB safety margin. That is unlikely to fit without changing the region split.

## Candidate resource profile (not approved)

A plausible experiment is to reclaim memory from legacy features that overlap with Clouds' purpose:

| Change | POOL bytes reclaimed |
|---|---:|
| Disable/remove Felucca master tempo delay | 131,072 |
| Disable/remove SLICER recording buffers | 32,768 |
| **Total reclaimed** | **163,840** |

If both features were removed, the known existing POOL subtotal would fall from 236,220 to 72,380 bytes.

Then place both Clouds buffers in POOL:

| Allocation | POOL bytes |
|---|---:|
| Existing known allocations after the two removals | 72,380 |
| Clouds large buffer | 118,784 |
| Clouds small buffer (relocated from .bss) | 65,408 |
| **Subtotal before Rings and working buffers** | **256,572** |

This leaves 54,724 bytes in a 304 KiB POOL region, or 46,532 bytes after the required 8 KiB headroom. That remaining space must still cover Rings/Strummer/Clouds object state, resampler histories, FIFOs, batch buffers, and every currently omitted allocation. It may not be sufficient.

A possible linker split to investigate is 128 KiB ordinary RAM and 304 KiB POOL, preserving the combined 432 KiB budget. At 128 KiB RAM, the 65,408-byte Clouds small buffer would leave 61,568 bytes for existing .bss after the 4 KiB headroom. The actual current .bss size must be measured before this split is considered viable. The linker origins and stack/NOINIT boundaries must be checked for overlap.

## Required evidence before choosing

1. Produce a baseline linker map and exact `.bss` and `.pool` usage from a successful base build.
2. Enumerate all POOL and ordinary-RAM allocations, including conditional build options, HALL, per-track inserts, CPU2 state and stack reservations.
3. Measure actual `sizeof(rings::Part)`, `sizeof(rings::Strummer)` and `sizeof(clouds::GranularProcessor)` using the pinned source/toolchain.
4. Calculate all batch, FIFO, resampler and audio staging buffers from the actual scheduler design.
5. Test at least one profile with linker-enforced 8 KiB POOL and 4 KiB RAM headroom.
6. Confirm CPU, latency and functionality after each resource change.

## User-visible consequences if the candidate is adopted

- Removing the master tempo delay removes Felucca's shared tempo-synchronised delay effect. Clouds' internal granular delay/feedback is not a drop-in replacement for that effect.
- Removing SLICER removes its per-track gate/stutter insert and its four recording buffers.
- Changing the linker split is internal only, but it must preserve stack guards, CPU2 operation and all reserved NOINIT regions.

No feature has been removed and no linker layout has been changed. The candidate must not be silently adopted; its audible trade-offs need an explicit product decision after the measured budget is available.


## Dual Rings requirement (added 2026-11-23)

The instrument must run two independent Rings DSP instances at the same time, exposed as RINGS A and RINGS B on separate FM-1 parts. This changes the resource target: the memory and CPU budget must include two mutable Rings object/state sets, two strummer states, per-instance input/output and modulation state, and any per-instance resampling or staging buffers. Do not estimate this as simply doubling the whole first instance: code and immutable lookup tables may be shared, while mutable state must be separate.

The earlier single-Rings-plus-Clouds estimates are therefore not sufficient to approve a final profile. Recalculate with the target compiler and linker after the C++ source import and wrapper exist. Profile at least:
- one Rings instance alone;
- two Rings instances simultaneously;
- two Rings plus one full-quality Clouds processor;
- two Rings plus Clouds, MIDI clock, modulation and the intended mixer/effects path.

The two-instance requirement is not permission to reduce either Rings engine's fidelity or to silently disable other modules. If the full configuration does not fit, present measured options and user-visible consequences before making a product trade-off.


## Original Rings String-and-Reverb model memory requirement (2026-11-23)

A further pinned-source inspection found a material memory cost that must be included in the dual-instance profile:

- Original `rings/dsp/fx/reverb.h` defines its Rings reverb engine as `FxEngine<32768, FORMAT_16_BIT>`.
- Its backing store is therefore 32,768 × 2 bytes = **65,536 bytes (64 KiB) per independent Rings Part**.
- `rings::Part::Init(uint16_t* reverb_buffer)` initializes this engine from the supplied buffer. The upstream implementation expects valid backing storage when the reverb mode is supported.
- FM1_Locus adds a guard around `reverb_.Init(reverb_buffer)` and calls `Part::Init(NULL)`; its own source comment explicitly ties this to omitting `RESONATOR_MODEL_STRING_AND_REVERB`. That is why its one-Part memory profile cannot be copied as a complete Rings implementation.

For two fully faithful independent Parts, reserve **at least 128 KiB** for two independent Rings reverb histories, in addition to both `rings::Part` objects, both Strummers, excitation/scratch buffers, Clouds storage, resampling/FIFOs, and the existing firmware allocations. Do not share one reverb history between A and B: it would couple their tail state and violate instance independence.

This 128 KiB figure is the exact raw delay-memory capacity required by the upstream type, not a measured total allocation or proof that the FM-1 pool can fit it. The target linker map and actual runtime object sizes still need measurement. If the complete feature set does not fit, present measured alternatives; do not silently remove the sixth Rings mode or shorten its delay memory.
