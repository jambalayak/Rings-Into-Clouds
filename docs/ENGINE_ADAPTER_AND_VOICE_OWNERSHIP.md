# Rings engine adapter and voice ownership

## Status

This is a source-verified integration design for the current Felucca-derived engine architecture. It is not an implementation: no Rings source, wrapper, or target build has been added.

## Findings from the current source

### Track and voice model

- `core.h` defines four parts/tracks (`NPART == 4`).
- Each `track_t` contains its own `voice_t v[NVOICE]` array, with `NVOICE == 8`.
- The allocator in `voice.c` enforces a **shared eight-sounding-voice budget across all four parts**. The per-track arrays are capacity, not four independent eight-voice allowances.
- `voice_start()` calls the selected engine's `note_on(track_t *, voice_t *)`; the render path calls its `render(track_t *, voice_t *, int32_t *, uint32_t, const vmod_t *)`.
- The engine receives the owning track and voice, so the adapter can identify the Rings instance from the track index without a global “current Rings” pointer.
- Engine voice caps are expressed through `engine_t.poly`; `trk_nvoice()` honours a non-zero cap below eight.
- Voice allocation can steal or release voices belonging to other tracks. The Rings adapter must therefore treat the track/voice pair as the ownership key and must not assume that a voice index is globally unique.

### Existing large-state memory is an overlay

`engines.c` currently allocates one `ENG_MEM_PART` region per part (12,888 bytes in the default build). The active engine claims that region. When a different engine claims it, `eng_mem_claim()` clears the new engine's declared memory size and changes the owner marker.

This is deliberately efficient for current engines, but it is not a persistent state store. A Rings resonator has long-lived internal energy and must not be placed in this overlay if changing away from Rings is expected to preserve its tail and instance state. Two Rings instances also cannot share one mutable `Part` object.

### Engine switch lifecycle

`engine_block()` runs at block boundaries. It fades the old engine, clears track voices, changes the effective engine, claims its memory and then replays queued notes. This gives the Rings adapter a safe point for instance activation/configuration, but it is still part of the audio-side block lifecycle: expensive object construction, buffer clearing, sample-rate preparation or FFT work must not be added there.

## Required ownership model

1. Assign each part a stable Rings runtime slot, indexed by `track_t - trk`.
2. Give each slot its own independent Rings `Part`, `Strummer`, mutable parameters, excitation state, model configuration, and any wrapper-owned scratch/state buffers.
3. Never use a shared mutable Rings singleton. Static immutable tables/resources may be shared only where upstream code is read-only.
4. The initial product configuration must support at least two simultaneous Rings slots on separate parts. It may support more only if measured target resources and CPU deadlines allow it.
5. Keep Rings state in a dedicated, explicitly budgeted allocation rather than the current engine-memory overlay. If the instrument later chooses suspend/reconstruct-on-engine-switch, that must be a deliberate, tested policy and must define tail handling; it is not the default.
6. Keep each track's parameter and preset data in its existing track-owned state. The adapter translates those values into that track's Rings instance only.
7. Preserve the global voice allocator. The Rings port must not silently claim eight additional voices per instance or bypass stealing/release rules.

## Proposed C-facing adapter

Keep upstream C++ classes private to a C++ translation unit. The C firmware should see only an opaque slot identifier or an integer part index, scaled integer parameters, event flags, and audio-buffer pointers. Do not expose C++ class layout in a C header.

Conceptual API (names are proposals, not existing symbols):

- `rings_runtime_prepare(part_index, sample_rate)`: construct/prepare the selected slot outside the audio interrupt.
- `rings_runtime_reset(part_index)`: reset only that instance.
- `rings_runtime_set_params(part_index, params)`: update only that instance's configuration.
- `rings_runtime_note_on(part_index, voice_index, note, velocity, flags)`: excite the matching instance/voice.
- `rings_runtime_note_off(part_index, voice_index, note)`: release the matching instance/voice according to the adapter's verified Rings event semantics.
- `rings_runtime_render(part_index, voice_index, output, frames, modulation)`: bounded render for one voice/block, with no allocation or blocking.
- `rings_runtime_strum(part_index, strength, position)`: explicit strummer event where required by the chosen excitation design.

The actual API must be derived from the pinned upstream Rings interfaces and the base engine callback contract. In particular, verify whether one Rings `Part` naturally represents one polyphonic resonator engine and how its internal voice allocation relates to Felucca's per-track `voice_t` allocator. Do not assume a one-to-one mapping until tested.

C/C++ ABI boundary:
- Use integer and pointer arguments initially; avoid passing floats across the generic-C / FPU-C++ boundary until the target ABI has been demonstrated by a compile/link/runtime test.
- Keep constructors, placement-new, configuration, resource preparation and reset outside the audio interrupt.
- No heap allocation, locks, exception handling, RTTI, dynamic global constructors or unbounded work in render.
- Preserve the current C unity build path while introducing a separate explicit C++ object list and runtime only after a toolchain smoke test succeeds.

## Event and voice-lifecycle rules

The adapter must be validated against all of these cases:

- First note into an idle part.
- Retrigger of the same note/voice.
- Legato pitch change.
- Polyphonic note-on and note-off.
- Voice steal initiated by another part.
- Voice release and reuse.
- Track mute and all-notes-off.
- Engine switch during a ringing tail.
- Preset/model change while notes are held.
- Two Rings tracks receiving simultaneous and interleaved events.

The key invariant is isolation: an event or voice steal on RINGS A must never reset, retrigger, damp, retune or otherwise mutate RINGS B.

A design choice is still required for how the eight global voice slots map into Rings' own resonator/strummer model. Compare at least:
- one Rings `Part` per track, with Felucca voices represented as excitation events; and
- one Rings voice/processor state per allocated Felucca voice, if the upstream DSP semantics and resource cost support it.

Choose by source inspection and audio tests, not by naming similarity.

## Resource and scheduling gates

Measure target compiler sizes and linked allocations for:
- one Rings runtime slot;
- two independent slots;
- four slots (informational upper bound);
- two slots plus full Clouds;
- two slots plus Clouds, patch routing, current effects and MIDI sync.

Report POOL, ordinary RAM, stack, flash image and worst-case block CPU separately. Include Strummer state, wrapper scratch buffers, any resampling history and all Rings auxiliary state. The two-instance case is the acceptance baseline.

The current linker map reserves 72 KiB for ordinary RAM and 360 KiB for POOL, with build checks requiring at least 4 KiB RAM and 8 KiB POOL spare. These headroom checks are hard gates, not targets to consume. A linker success that leaves less headroom is a failed profile.

## Acceptance criteria

- Two different parts can play Rings at the same time.
- Their mutable DSP state and presets are independent.
- Changing model, structure, brightness, damping, position, tune, excitation or modulation on A has no effect on B, and vice versa.
- Note-off, steal, mute, retrigger and engine-switch events affect only their owning instance.
- Both instances remain stable during long sustained/ringing passages.
- The two-instance resource and worst-case CPU report passes the documented headroom and audio deadline requirements.
- Existing non-Rings engines, sequencer, MIDI input and current effects remain functional.
- Any omitted Rings model or altered behaviour is documented visibly and in the source patch manifest.

## Next implementation steps

- [ ] Locate and inspect the exact engine interface header from the checked-out Felucca-Engines submodule.
- [ ] Inspect every voice allocator/render callback path and confirm the exact global-budget behaviour with the existing tests.
- [ ] Inspect pinned Rings `Part` and `Strummer` semantics and select the voice/event mapping.
- [ ] Confirm the target C++ compiler and ABI with a standalone smoke build.
- [ ] Implement the isolated C ABI wrapper and host-side adapter tests.
- [ ] Measure dedicated per-part Rings state before adding it to the live engine table.
- [ ] Integrate only after two-instance isolation and resource tests pass.
