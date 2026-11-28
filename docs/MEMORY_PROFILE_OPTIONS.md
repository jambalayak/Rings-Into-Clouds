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

## Measured current baseline

The earlier source-only POOL subtotal of 56,416 bytes omitted the UI canvas and other static allocations. It is not the current firmware's actual POOL use and must not be used for fit calculations.

The lean target linker measurement is the baseline:

| Region | Used | Capacity | Free |
|---|---:|---:|---:|
| Ordinary RAM (.data + .bss) | 56,036 B | 73,728 B | 17,692 B |
| POOL | 145,720 B | 368,640 B | 222,920 B |
| **Combined** | **201,756 B** | **442,368 B** | **240,612 B** |

The 145,720-byte POOL use includes the 59,520-byte RGB565 UI canvas, 51,552-byte four-part engine-memory array, 6,160-byte user preset bank, project/storage/editor buffers and smaller state. See the symbol-level inventory below for the exact breakdown.

The old 131,072-byte global tempo delay line, 4,096-byte chorus line, 11,868-byte global ROOM/SPRING/HALL buffers and 32,768-byte performance-loop recorder were removed before this measured lean baseline. They are not present as free allocations to remove a second time. The current `firmware/src/fx.c` retains only the small per-track insert path.

## Rings + Clouds memory floor

The pinned FM1_Locus reference allocates 184,192 bytes for full-quality stereo Clouds: 118,784 bytes in POOL and 65,408 bytes in ordinary RAM. One original Rings Part contains 98,304 bytes of float delay-line arrays. If one 12,888-byte engine overlay is replaced by Rings state, the measured combined baseline projects as follows:

| Profile | Projected combined use | Headroom against 442,368 B |
|---|---:|---:|
| One original float Rings Part + full 32 kHz / 16-bit Clouds | 492,720 B | 50,352 B over |
| One compact 16-bit Rings delay store + full Clouds | 443,568 B | 1,200 B over |
| One compact Rings + Clouds recording storage shortened 25% | 410,864 B | 31,504 B free |
| One compact Rings + approximately 0.5 s full-quality stereo Clouds | 378,288 B | 64,080 B free |

These totals include one measured Rings Part, one Strummer and one Clouds processor, the measured base image, replacement of one engine overlay and Clouds' external buffers. They still exclude resampler/FIFO/routing buffers, stack growth and any additional alignment.

The region split matters as much as the combined total. Keeping the FM1_Locus split for full Clouds adds 65,408 bytes to ordinary RAM, taking it from 56,036 to 121,444 bytes (47,716 bytes over). The previous dual-Rings POOL/RAM placement arithmetic is obsolete. With one Rings instance, the exact location of the Rings state, Clouds buffers, resampler and routing storage must be recalculated from a fresh target linker map; no region-fit claim is made here.

A roughly 0.5-second full-quality stereo profile reserves 32,768 recording bytes per channel plus the unchanged 53,376-byte workspace (118,912 bytes total). The 32 kHz processing rate and 16-bit sample format remain unchanged; only maximum capture duration is shortened. This is a candidate to test, not a selected product setting. The exact recording duration, allocator alignment, routing/resampler state and 8 KiB POOL / 4 KiB RAM reserves must be verified by the target linker.

### Dedicated Rings reverb allocation removed from the target budget


The pinned upstream `rings::Part` includes a separate `Reverb` object whose
`FxEngine<32768, FORMAT_16_BIT>` requires a caller-owned 32,768-sample
`uint16_t` buffer. That is 65,536 bytes for the single Rings instance. The approved five-model port removes the member,
its initialisation and its processing path, so these buffers are not part of
the RINGS INTO CLOUDS target allocation.

The current full-quality Rings + Clouds projection above already excludes the
reverb buffers; it is not an additional saving to subtract from that total.
This 128 KiB is a source-derived avoided allocation, not a measured linker
delta. The separate Clouds-native reverb remains part of the Clouds processor
and is not included in this Rings-specific calculation.

## Possible architecture work (not yet implemented)

1. **Prototype compact Rings delay-line storage.** Keep the original capacities, update order and Hermite interpolation, but test a fixed-point 16-bit backing store against upstream float reference renders. Do not accept it until all five retained models pass SNR, peak, decay and musical reference tests. Keep one Rings main state and delay storage isolated from the legacy engine overlays.
2. **Reuse one selected track's engine overlay.** Replace only that track's small engine union with the single Rings runtime after ownership/lifetime is proven. There is no second Rings Part or second Rings delay bank in the selected product direction.
3. **Place Clouds buffers deliberately.** Keep the exact reference buffer sizes and quality. Allocate large/small buffers to regions based on the final map, not assumptions.
4. **Measure all remaining state.** Target `sizeof` for Part, Strummer and Clouds processor, plus FIFO, resampler, stereo bus, stack and CPU2 handoff.
5. **Add reverb later as an optional graph node.** It must have an explicit instance count, buffer size, CPU ceiling, bypass/tail policy and patch-save format.

The experimental cache-way RAM in a newer BSP revision offers up to 28 KiB, but the project's pinned BSP does not include it; it reduces data-cache capacity and needs early-boot and hardware validation. It is supplementary only, not a solution.

## Validation gates

- Produce a successful baseline target build and linker map.
- Report exact `.bss`, `.data`, POOL and stack usage with headroom.
- Measure actual Rings/Strummer/Clouds object sizes using the target compiler.
- Prove one independent Rings instance feeding Clouds at the selected, documented recording duration.
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
- The single Rings track can replace one of the four 12,888-byte engine slots; do not reserve a second Rings Part or delay bank.
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

At 4 bytes per float, each String occupies 12,288 bytes of delay-line storage; eight Strings occupy 98,304 bytes per Rings Part. The single Part therefore reserves 98,304 bytes for these delay-line arrays alone. This is the source of the minimum in the projection above; it excludes the other Rings state, object alignment, Clouds object, resampler, FIFOs, routing and stacks.

This storage is embedded in the Part object even when its current model is Modal or FM Voice, because the same Part can switch models. Omitting the arrays would break the supported String and Sympathetic Strings models. The original String-and-Reverb model has been excluded as requested, but that does not remove the String delay lines used by the remaining models.

### Candidates to prototype, not decisions

1. **Compact delay-line storage.** A custom 16-bit representation could theoretically halve the two delay arrays to 49,152 bytes for the single Part, but upstream `DelayLine<float>` performs fractional and Hermite reads in floating point. A fixed-point adapter must define signal scaling/headroom, interpolation precision, saturation and round-trip error, and pass host reference renders for all five models before it can be accepted.
2. **Shorter maximum delay.** Halving both line lengths would also halve their memory, but the 2,048-sample line supports periods down to roughly 21.5 Hz at 44.1 kHz; a 1,024-sample line raises that floor to roughly 43 Hz and would compromise low bass notes. It is not a transparent optimisation.
3. **Reduce polyphony.** Reducing `kMaxPolyphony` changes `kNumStrings` and can reduce memory, but it also changes the voice capability of each independent Rings instance. Do not apply without an explicit product decision.

The most promising path to investigate first is a bounded 16-bit delay-line adapter with the upstream float implementation retained as a host reference. No compact representation is implemented or sound-validated yet.

## Reverb-model exclusion detail

The upstream Rings `Part` embeds a small `Reverb` object and calls `reverb_.Init(reverb_buffer)` unconditionally from `Part::Init()`. Its reverb delay storage is external: `FxEngine<32768, FORMAT_16_BIT>` requires 32,768 16-bit samples (65,536 bytes) supplied by the caller. The original upstream `FxEngine::Init()` immediately clears that buffer, so passing `NULL` to unmodified upstream code is unsafe.

FM1_Locus carries a local guard around `reverb_.Init()` when the pointer is null, and calls `Part::Init(NULL)` because it does not use the String-and-Reverb model. Our port must explicitly review and carry an equivalent safe patch, or remove the unused reverb member/model path entirely. Do not pass `NULL` to unmodified upstream `Part::Init()`. The 65,536-byte external reverb buffer is not included in the Rings + Clouds projection; it is omitted by design. This also means the current Rings Part object still contains a small Reverb state member unless our local patch removes it.

## Candidate combined memory profiles (planning arithmetic only)

| Profile | Projected combined use | Headroom against 442,368 B |
|---|---:|---:|
| One original float Rings Part + full 32 kHz / 16-bit Clouds | 492,720 B | 50,352 B over |
| One compact 16-bit Rings delay store + full Clouds | 443,568 B | 1,200 B over |
| One compact Rings + 25% shorter full-quality Clouds recording storage | 427,216 B | 15,152 B free |
| One compact Rings + approximately 0.5 s full-quality stereo Clouds | 378,288 B | 64,080 B free |

The combined figures are not proof of a region fit. In particular, putting the 65,408-byte Clouds small buffer in ordinary RAM exceeds the current RAM region; putting both full-length buffers in POOL exceeds POOL once Rings is included. The approximately 0.5-second profile is the most promising conservative experiment, but the target linker must include the actual DSP object sizes, routing, resampler/FIFO state and required headroom before it is accepted.


## Target C++ object sizes (pi32v2, 2026-11-24)

The compile-only target size probe measured these upstream class sizes:

| Object | Target size |
|---|---:|
| `rings::Part` | 110,452 B |
| `rings::String` | 12,428 B |
| `rings::Strummer` | 524 B |
| `clouds::GranularProcessor` | 8,684 B |

The upstream `Part` size includes its eight inline String delay stores (98,304 bytes per Part) and the small embedded Rings Reverb state member. The external 65,536-byte-per-Part Rings reverb buffer is not part of `sizeof(Part)` and is not allocated by this compile-only probe. The later five-model source patch will remove the unused embedded Reverb member and model branch; its exact size reduction must be measured again.

One Part, one Strummer and one Clouds processor occupy 119,660 bytes of object state before external buffers, resamplers, FIFOs or routing. With full Clouds external buffers (184,192 bytes), the total DSP state is 303,852 bytes. Adding that to the measured base image after replacing one 12,888-byte engine overlay (201,756 - 12,888 = 188,868 bytes) gives **492,720 bytes**, 50,352 bytes over the 442,368-byte combined SRAM budget.

If the single Rings delay store were converted to 16-bit, its inline delay arrays would shrink by 49,152 bytes. The full-Clouds estimate would be 443,568 bytes, still 1,200 bytes over before resampling/routing. This is a hypothetical storage adaptation, not implemented or audio-validated.

A 0.5-second full-quality stereo Clouds profile requires 118,912 external bytes (32,768 recording bytes per channel plus 53,376 bytes workspace). With one compact Rings instance, the measured-object combined estimate becomes 378,288 bytes, leaving 64,080 bytes before resampling/routing. This is a candidate profile, not a fit claim. The region placement of both Clouds buffers and all object state must still be measured.


## Target DSP object-size measurement (Run 68, 2026-11-24)

The compile-only target size probe emitted symbol extents from the `pi32v2` compiler. It did not construct or initialise any DSP object:

| Type | Target size |
|---|---:|
| `rings::Part` | 110,452 B |
| `rings::String` | 12,428 B |
| `rings::Strummer` | 524 B |
| `clouds::GranularProcessor` | 8,684 B |

The `Part` size includes its eight String objects and their two float delay lines each. The two delay arrays alone account for 98,304 B per Part; the measured object therefore adds 12,148 B of other Rings state. One Part occupies 110,452 B, one Strummer adds 524 B. The Clouds processor object adds 8,684 B, separate from its external buffers.

The revised table above now includes those measured object sizes, the measured base image, replacement of one 12,888-byte engine overlay, and the Clouds external-buffer estimates. It still excludes resampler histories, FIFOs, stereo routing/batch buffers, stack growth and any additional alignment. The 16-bit Rings row assumes the delay arrays halve in size while all other Part state remains unchanged; this is a prototype assumption, not an implementation result.

### Clouds external-buffer breakdown

In the FM1_Locus reference split, full stereo Clouds receives 118,784 B of POOL and 65,408 B of ordinary RAM. In stereo mode the processor uses 65,408 B per channel for recording (32,704 signed 16-bit samples, about 1.02 s at 32 kHz); the remaining 53,376 B in the large buffer is FX workspace. The workspace allocator requests 8,192 B for the diffuser, 32,768 B for the native Clouds reverb and 1,560 B for the correlator data. This workspace is independent of recording duration.

A roughly 0.5 s full-quality recording uses 32,768 B per channel plus the unchanged 53,376 B workspace: 86,144 B large buffer + 32,768 B small buffer = 118,912 B total. Both buffers can be placed in POOL in the candidate profile. This preserves the 32 kHz processing bandwidth but halves the maximum captured duration. By contrast, 24 kHz with the original 1.02 s duration uses the same sample-storage bytes as a 25% shorter 32 kHz buffer and requires a different codec-to-Clouds resampler ratio. Shortening duration at 32 kHz is therefore the better first experiment; no buffer-size or sample-rate change has been applied.


## Product direction decision — single Rings

The selected product architecture is **one complete Mutable Instruments Rings engine, one Clouds processor and one Marbles sequencer/modulation engine**, with the dedicated DRUM engine remaining on Track 4. The previous two-independent-Rings concept is no longer the target for the FM-1.

This is a scope decision, not a claim that the current target allocation already fits. The implementation must still pass a fresh target link with measured data, bss, POOL, RAMTEXT and stack headroom, including the actual Clouds buffers, Rings Part, Strummer, Marbles state, resampler/FIFO/routing buffers and UI allocations.

The one Rings instance must retain all five supported resonator models, the original eight-string storage capacity, normal pitch range, authentic excitation/strum behaviour, full natural decay and stereo OUT/AUX. Do not shrink the resonator bank, alter model coefficients, shorten decay or remove a model as a memory shortcut.

Clouds remains a processor for the Rings signal, not a second synth voice or a second Rings-like track. The original 32 kHz processing rate and 16-bit audio quality are the target. Full stock recording duration remains preferred; a shorter recording buffer is only an engineering candidate if a measured target link proves that it is necessary and the trade-off is reviewed before adoption. No buffer-duration reduction is approved by this decision.

Marbles continues to provide the X CV, Y CV and T trigger streams, with its timing, jitter, Deja Vu and random-gate behaviour preserved. With only one Rings pitch/strum destination, the former Rings 1 / Rings 2 destination selectors become a single-Rings routing design. The precise X1/X2 pitch-bus combination and attenuation defaults require a dedicated routing implementation and regression tests; do not silently sum two full-scale pitch streams without defining their scaling. T1/T2 may feed the single Rings strum input through an edge-preserving trigger combiner.

The Rings performance screen remains the approved five-knob layout: Frequency, Structure, Brightness, Damping and Position. Frequency offsets the incoming note pitch; it is not a fabricated Rings Patch field. Four physical rotary controls edit four assigned parameters, and SELECT cycles the assignment so the fifth can be edited. All displayed controls must change the actual DSP state.

The old dual-Rings experiments remain on rings-delay-packed24-exp as research history. Do not merge them into this branch. Future implementation and validation for the selected architecture proceeds on rings-single-rings-development.


## Measured one-Rings + full-Clouds target link (2026-11-28)

A target linker diagnostic was produced from the pinned FM-1 toolchain with one original-float Rings Part, one Strummer, one Clouds processor and the full stock stereo Clouds buffers. This is a diagnostic link only: the C ABI objects are retained for measurement and are not attached to the live audio path. The diagnostic does not include the final Marbles/routing/resampler integration.

Measured section sizes:

| Section | Measured | Region capacity | Result |
|---|---:|---:|---:|
| .data + .bss (ordinary RAM) | 123,476 B | 73,728 B | 49,748 B over |
| .pool | 384,112 B | 368,640 B | 15,472 B over |
| .ram_text | 3,124 B | 24,576 B | 21,452 B free |

The diagnostic includes the complete stock Clouds buffers: 65,408 B in ordinary .bss and 118,784 B in POOL. It also includes one Rings Part storage (110,384 B in this target build), one Strummer (524 B), one Clouds processor (8,684 B), and the existing firmware allocations. The measured base-only sections in the same artifact are .data 352 B, .bss 55,684 B and .pool 145,720 B.

The large Clouds small buffer is the dominant ordinary-RAM overflow. Moving all 65,408 B out of ordinary RAM is necessary, not optional. The POOL is also over capacity, so simply moving that buffer into POOL cannot work. RAMTEXT has 21,452 B unused in this diagnostic, but it is a code region and must not be treated as general-purpose audio storage until flash-update execution, DMA access, startup clearing and linker placement are reviewed.

The existing 59,520 B UI graph canvas (cv_px, 240 x 124 RGB565) and four 12,888 B per-track engine overlays (eng_mem) are the largest potentially relevant POOL allocations. They are not declared disposable. A smaller/tiled UI renderer and an explicit track-role memory plan are candidates for investigation, but both need feature and visual regression tests. The one Rings runtime must replace or deliberately reuse the selected track's engine overlay where safe; it must not allocate a second Rings Part.

The experimental packed-24 Rings delay representation measured a 24,576 B reduction in the host Part size for 75 comparison cases (MIDI notes 36, 60 and 84). It is not yet integrated into this target link, has not yet been expanded to all six tested pitches, and is not accepted as the production representation. Do not treat the hypothetical 16-bit delay store as implemented.

No memory profile is approved by this measurement. Do not shorten the Clouds recording buffer, reduce Rings' five models/eight-string capacity/natural decay, or change upstream DSP coefficients to force a fit. A viable profile must fit the full buffers and all actual routing/Marbles/resampling state while retaining at least 4 KiB ordinary-RAM and 8 KiB POOL headroom. It must also prove stack and CPU deadlines with CPU2 enabled and unavailable.
