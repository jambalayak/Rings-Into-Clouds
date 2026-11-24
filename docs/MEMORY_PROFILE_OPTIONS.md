# RINGS INTO CLOUDS memory profile

## Purpose and status

This is a source-based planning estimate after the user's approved removal of legacy Felucca features. It is not a target linker map, a successful build, or proof that the full instrument fits. The next gate is a measured target build with a linker map and per-section allocation report.

## FM-1 memory regions

The current application linker script divides the internal SRAM span into:

- ordinary RAM: 72 KiB (73,728 bytes), for `.data/.bss`;
- POOL: 360 KiB (368,640 bytes), for large static buffers;
- combined: 432 KiB (442,368 bytes).

The build requires at least 4 KiB ordinary-RAM headroom and 8 KiB POOL headroom. No external PSRAM region is currently exposed by the pinned board support package.

## User-approved base-firmware simplification

The instrument is not intended to retain Felucca's general-purpose groovebox effects and live-loop performance layer. The following features have been removed from the development branch:

| Removed feature | Known static POOL storage recovered |
|---|---:|
| Global tempo delay line (65,536 × int16) | 131,072 bytes |
| Global chorus line (2,048 × int16) | 4,096 bytes |
| Global ROOM / SPRING / HALL reverb buffers (comb + allpass union) | 11,868 bytes |
| Performance-loop recorder buffer (4 × 4,096 × int16) | 32,768 bytes |
| **Known total** | **179,804 bytes (~175.6 KiB)** |

The global reverb's HALL work/state block and small runtime state are also removed; their exact linker delta is not included in the total above. Performance-layer LPF, HPF, CRUSH, FLANGER, PHASER and track mutes remain; the recording-based REPEAT/REVERSE, TAPE STOP, FREEZE and octave-shifter effects have been removed. The legacy global-send parameter IDs and insert CHORUS ID remain reserved for project compatibility but no longer run DSP or appear as active controls. New presets initialise retired sends to zero.

A future reverb is still part of the product vision, but it will be designed as an optional modular processor with an explicit, measured memory/CPU budget. It will not be reintroduced as a permanent global bus, and it must not consume Rings/Clouds state by surprise.

## Remaining known POOL subtotal

The earlier known POOL subtotal was 236,220 bytes. Subtracting the approved allocations above leaves **56,416 bytes** of known existing allocations:

| Remaining known allocation | Bytes |
|---|---:|
| Four Felucca per-track engine-memory overlays (4 × 12,888) | 51,552 |
| Scope snapshot | 1,024 |
| Flash storage payload buffer | 3,840 |
| **Known remaining subtotal** | **56,416** |

This is still a lower bound. Other code/data, CPU2 state, insert state, stacks and ordinary `.bss/.data` allocations must be measured.

## Rings + Clouds memory floor

The reference FM1_Locus Clouds allocation uses:

- `clouds_large[118784]` in POOL;
- `clouds_small[65408]` in ordinary RAM.

The Clouds buffer pair is 184,192 bytes total.

The pinned original Rings source declares eight `String` objects per `rings::Part`. Each String embeds a 2,048-float delay line and a 1,024-float stiffness delay line. At 32-bit float storage this is at least 98,304 bytes per Part, or **196,608 bytes for two independent Rings Parts**, before the rest of either Part, Strummers, excitation state, audio scratch, stereo routing, resampling or stacks.

If RINGS A and B replace two Felucca engine overlays, the optimistic lower-bound arithmetic is:

| Allocation | Bytes |
|---|---:|
| Remaining known base allocations after subtracting two replaced 12,888-byte overlays | 30,640 |
| Clouds buffer pair | 184,192 |
| Two Rings Parts' inline delay-line arrays | 196,608 |
| **Combined lower bound** | **411,440** |

That leaves only 30,928 bytes inside the full 432 KiB SRAM span for all other Rings/Clouds state, Strummers, FIFO/resampler/stereo buffers, other firmware data and required headroom. This is a warning, not a fit claim.

The region split is also a separate constraint. With the current 72 KiB RAM region, Clouds' 65,408-byte small buffer leaves only 8,320 bytes for every other `.bss/.data` allocation before the required 4 KiB reserve. A 128 KiB RAM / 304 KiB POOL split is one possible experiment, but the Rings delay-line arrays would then need deliberate placement across both regions to avoid overfilling POOL. The current inline Rings object layout does not provide that split automatically.

### Dedicated Rings reverb allocation removed from the target budget

The pinned upstream `rings::Part` includes a separate `Reverb` object whose
`FxEngine<32768, FORMAT_16_BIT>` requires a caller-owned 32,768-sample
`uint16_t` buffer. That is 65,536 bytes per Part, or 131,072 bytes for the two
independent Rings instances. The approved five-model port removes the member,
its initialisation and its processing path, so these buffers are not part of
the RINGS INTO CLOUDS target allocation.

The 411,440-byte combined lower-bound table above already excludes these two
reverb buffers; it is not an additional saving to subtract from that total.
This 128 KiB is a source-derived avoided allocation, not a measured linker
delta. The separate Clouds-native reverb remains part of the Clouds processor
and is not included in this Rings-specific calculation.

## Possible architecture work (not yet implemented)

1. **Externalise Rings delay-line storage without changing its algorithm.** Adapt the pinned DelayLine/String storage interface so each Rings instance owns independent arrays, but those arrays can be placed in separate linker regions. Do not shorten delay lengths or share mutable buffers between A and B.
2. **Reuse the two selected tracks' engine overlays.** Replace their small engine unions with the Rings runtime only where ownership/lifetime is proven; keep A and B completely independent.
3. **Place Clouds buffers deliberately.** Keep the exact reference buffer sizes and quality. Allocate large/small buffers to regions based on the final map, not assumptions.
4. **Measure all remaining state.** Target `sizeof` for Part, Strummer and Clouds processor, plus FIFO, resampler, stereo bus, stack and CPU2 handoff.
5. **Add reverb later as an optional graph node.** It must have an explicit instance count, buffer size, CPU ceiling, bypass/tail policy and patch-save format.

The experimental cache-way RAM in a newer BSP revision offers up to 28 KiB, but the project's pinned BSP does not include it; it reduces data-cache capacity and needs early-boot and hardware validation. It is supplementary only, not a solution.

## Validation gates

- Produce a successful baseline target build and linker map.
- Report exact `.bss`, `.data`, POOL and stack usage with headroom.
- Measure actual Rings/Strummer/Clouds object sizes using the target compiler.
- Prove two simultaneous independent Rings instances and full Clouds quality.
- Profile worst-case CPU, audio deadlines, MIDI clock and stereo routing.
- Verify old project files load safely with retired effect parameters ignored.
- Only then decide whether a future modular reverb instance fits.

No target build, audio test or physical FM-1 test has yet verified these changes.

## Symbol-level inventory from the lean linker artifact

The latest lean artifact (Run 68, commit `d21f9a5`) contains `felucca.symbols.txt`. The target symbol table attributes the 145,711 bytes of named POOL objects as follows (9 bytes remain as linker alignment):

| POOL object | Bytes | Notes |
|---|---:|---|
| `cv_px` | 59,520 | UI RGB565 canvas, 240 × 124 pixels |
| `eng_mem` | 51,552 | Four per-track engine-memory slots, 12,888 bytes each |
| `up_bank` | 6,160 | User preset bank |
| `proj_scratch` | 4,808 | Project scratch |
| `st_buf` | 3,840 | Storage transfer buffer |
| `proj_wire_u` | 3,840 | Project wire/transfer buffer |
| `upf` | 3,728 | User-preset transfer state |
| Other named POOL objects | 12,263 | FX/editor/persistence/favorites/scope and small state |
| **Named symbols** | **145,711** | plus 9 bytes alignment = 145,720 |

The largest non-engine allocation is the UI canvas. `firmware/src/gfx.c` sets `CV_MAX = 240 × 124`; the full graph panel is 240 × 122 pixels (`H_GRAPH = 122`). Merely trimming the two spare rows would save only 960 bytes. A material saving would require a real renderer change, such as tiled/row-based drawing or a reduced pixel representation, and would need visual regression coverage. The graph area is a core UI element, so do not shrink it or reduce color depth without comparing screenshots and antialiasing.

The ordinary `.bss` section is 55,684 bytes (plus 352 bytes `.data`). Its largest named objects include `chain` 13,096 B, `trk` 7,360 B, `drw_v` 2,944 B, `abuf` 2,048 B, `ua_ring` 2,048 B, `midi_sel_on` 2,048 B and `cdc_out` 2,048 B. The 3,072-byte CPU1 stack is also in ordinary RAM. The rest is distributed across USB/MIDI, motion, editor, audio and UI state.

This inventory explains the earlier 89,304-byte POOL discrepancy: `cv_px` is 59,520 bytes; the remaining 29,784 bytes are other named allocations not included in the earlier 56,416-byte subtotal. That subtotal consists of `eng_mem` 51,552 B, the 1,024-byte scope snapshot, and the 3,840-byte storage buffer.

### What this means for the next memory pass

- Keep the four engine slots for now: the fourth part is the GM drum part and the DRUM engine has per-part lane state. Do not remove its slot without auditing the drum engine and track-switch tests.
- The two Rings tracks can replace two of the four 12,888-byte engine slots, as already counted in the projection.
- The full-height UI canvas is not a quick 59 KiB win; a tiled renderer is a separate UI project.
- The remaining 34.6 KiB of POOL outside `eng_mem` and `cv_px` supports user presets, project I/O, storage, editor, undo, scope and small state. Only reclaim it after an explicit feature/lifetime audit.
- A custom Rings delay-line representation and a shorter Clouds recording buffer remain the DSP-side options to prototype and measure. No such reduction has been implemented or sound-validated yet.


## Additional RAMTEXT headroom (not yet allocated)

The linker map shows a separate 24 KiB `RAMTEXT` region at `0x01C00000`. The lean build uses 3,124 bytes (`.ram_text` including the second-core waiting loop), leaving 21,452 bytes in that region. It is currently reserved for code that must execute while flash is busy; the ordinary RAM/POOL build checks do not count this unused space.

A future, explicit `.ram_pool` NOLOAD section placed after `_rt_end` could potentially use some of this free region for small mutable DSP state or resampler tables. It must not overlap the copied `.ram_text`, must be accounted for in new linker/build headroom checks, and must be tested during flash operations. It is not a contiguous 65,408-byte substitute for the Clouds small buffer, and it does not close the roughly 114 KiB Rings + Clouds deficit. The 8 KiB gap before ordinary RAM is reserved for RAM-run debug and is not counted as free. The 32 KiB user/supervisor stack region must not be reclaimed without stack-watermark evidence.


## Rings delay-line floor: source-level breakdown

The pinned upstream `rings/dsp/part.h` allocates `String string_[kNumStrings]` in every `Part`. With `kMaxPolyphony = 4`, `kNumStrings = 8`. Each `String` in `rings/dsp/string.h` contains:

- `StringDelayLine`: 2,048 `float` samples;
- `StiffnessDelayLine`: 1,024 `float` samples.

At 4 bytes per float, each String occupies 12,288 bytes of delay-line storage; eight Strings occupy 98,304 bytes per Rings Part. Two fully independent Parts therefore reserve 196,608 bytes for these two delay-line arrays alone. This is the source of the minimum in the projection above; it excludes the other Rings state, object alignment, Clouds object, resampler, FIFOs, routing and stacks.

This storage is embedded in the Part object even when its current model is Modal or FM Voice, because the same Part can switch models. Omitting the arrays would break the supported String and Sympathetic Strings models. The original String-and-Reverb model has been excluded as requested, but that does not remove the String delay lines used by the remaining models.

### Candidates to prototype, not decisions

1. **Compact delay-line storage.** A custom 16-bit representation could theoretically halve the two delay arrays to 98,304 bytes for both Parts, but upstream `DelayLine<float>` performs fractional and Hermite reads in floating point. A fixed-point adapter must define signal scaling/headroom, interpolation precision, saturation and round-trip error, and pass host reference renders for all five models before it can be accepted.
2. **Shorter maximum delay.** Halving both line lengths would also halve their memory, but the 2,048-sample line supports periods down to roughly 21.5 Hz at 44.1 kHz; a 1,024-sample line raises that floor to roughly 43 Hz and would compromise low bass notes. It is not a transparent optimisation.
3. **Reduce polyphony.** Reducing `kMaxPolyphony` changes `kNumStrings` and can reduce memory, but it also changes the voice capability of each independent Rings instance. Do not apply without an explicit product decision.

The most promising path to investigate first is a bounded 16-bit delay-line adapter with the upstream float implementation retained as a host reference. No compact representation is implemented or sound-validated yet.

## Reverb-model exclusion detail

The upstream Rings `Part` embeds a small `Reverb` object and calls `reverb_.Init(reverb_buffer)` unconditionally from `Part::Init()`. Its reverb delay storage is external: `FxEngine<32768, FORMAT_16_BIT>` requires 32,768 16-bit samples (65,536 bytes) supplied by the caller. The original upstream `FxEngine::Init()` immediately clears that buffer, so passing `NULL` to unmodified upstream code is unsafe.

FM1_Locus carries a local guard around `reverb_.Init()` when the pointer is null, and calls `Part::Init(NULL)` because it does not use the String-and-Reverb model. Our port must explicitly review and carry an equivalent safe patch, or remove the unused reverb member/model path entirely. Do not pass `NULL` to unmodified upstream `Part::Init()`. The 65,536-byte external reverb buffer is not included in the Rings + Clouds projection; it is omitted by design. This also means the current Rings Part object still contains a small Reverb state member unless our local patch removes it.

## Candidate combined memory profiles (planning arithmetic only)

| Profile | Projected combined use | Headroom against 442,368 B |
|---|---:|---:|
| Two original float Rings Parts + full 32 kHz / 16-bit Clouds | 556,780 B | 114,412 B over budget |
| Two compact 16-bit Rings delay stores + full Clouds | 458,476 B | 16,108 B over budget |
| Compact Rings + Clouds recording storage shortened 25% | 425,772 B | 16,596 B free |
| Compact Rings + 16 kHz / 8-bit Clouds with about 1 s stereo recording | 359,660 B | 82,708 B free |

The last row assumes 16,000 bytes per channel for 8-bit recording, plus the unchanged 53,376-byte stereo workspace, and the compact Rings delay stores. It is a potentially comfortable memory profile, but it changes Clouds to its original low-fidelity mode and still needs an explicit custom short-buffer allocation, target linker measurement and listening tests. Full float Rings with this one-second low-fidelity Clouds buffer would still project to 457,964 bytes, above the combined memory budget.

The 25%-shortened full-quality Clouds row fits the combined total on paper but does not fit the present linker-region split if both stereo recording buffers are simply moved into POOL; more detailed placement and additional DSP object sizes still need to be measured. None of these rows includes the complete Rings/Clouds object, resampler/FIFO/routing state or worst-case stack growth. These are not build-fit claims or selected product settings.
