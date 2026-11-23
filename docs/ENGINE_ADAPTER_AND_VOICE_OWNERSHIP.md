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

## Exact engine callback contract (pinned Felucca-Engines)

The repository's `firmware/engines` submodule is pinned to Felucca-Engines commit `1fa016b9702a76e2767b2bd9f108333f7c46e592`. Its `src/felucca_engine.h` defines the callback contract:

- `note_on(struct track *, voice_t *)` is called whenever a host voice starts or is retriggered.
- `render(struct track *, voice_t *, int32_t *out, uint32_t n, const vmod_t *)` adds samples to the output; it must not overwrite existing mix content.
- `block(struct track *)` is an optional once-per-block, per-track hook before voices.
- `post(struct track *, int32_t *out, uint32_t n)` is an optional once-per-block, per-track processor after voices; it can continue rendering a tail with no active notes.
- `engine_t.poly` caps the number of voices for that engine; zero means the full host voice count.
- `engine_t.mem` is a byte count in the one active engine-memory overlay for that track, not a persistent multi-engine allocation.

The header explicitly documents that voice-local `ph[]` and `s[]` are initialized/reset by the host and that selected state slots are restored after retrigger according to `engine_t.keep`. A Rings adapter must honour that contract or deliberately keep its own state outside the host voice slots.

This means a direct mapping of Rings' C++ `Part` to the Felucca `render` callback is not yet proven. Rings is a resonator processor with its own excitation/strummer and internal state; Felucca invokes a render callback per allocated note voice. The adapter must decide how the per-track Rings processor receives note events and excitation, then how its mono/stereo/block output is mixed without duplicating the same resonator for every host voice. Do not implement a naïve one-C++-`Part`-per-Felucca-voice wrapper.

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
- [ ] Inspect pinned Rings `Part` and `Strummer` semantics and select the voice/event mapping; prove the per-track processor/per-voice callback bridge before implementation.
- [ ] Confirm the target C++ compiler and ABI with a standalone smoke build.
- [ ] Implement the isolated C ABI wrapper and host-side adapter tests.
- [ ] Measure dedicated per-part Rings state before adding it to the live engine table.
- [ ] Integrate only after two-instance isolation and resource tests pass.


## Pinned Rings DSP semantics: decisive adapter constraints

Inspected upstream `pichenettes/eurorack` at pinned commit `08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4`:

- `rings::Part` is a **per-instrument resonator processor**, not a per-note oscillator. One Part owns up to four internal resonator voices, excitation filters, pluckers, DC blockers, note filtering and limiter. The upstream reverb member is removed by this project's approved five-model adaptation.
- Its `Process(performance_state, patch, in, out, aux, size)` accepts an excitation input block and emits two output channels. It internally selects/rotates its active resonator voice when `performance_state.strum` is asserted.
- `PerformanceState` is block-level: `strum`, `internal_exciter`, `internal_strum`, `internal_note`, `tonic`, `note`, `fm`, and `chord`. `Patch` carries `structure`, `brightness`, `damping`, and `position`.
- `Strummer::Process` consumes an optional excitation signal and updates the block-level strum event. It can derive strums from note changes or input onsets depending on internal/external settings.
- The pinned source sets Rings `kMaxPolyphony = 4` and `kMaxBlockSize = 24`; the FM-1 host's control blocks are 32 samples. The adapter must split host blocks into bounded Rings chunks (e.g. 24 + 8), or deliberately establish a different supported block/rate contract. It must not pass 32 samples into fixed 24-sample Rings scratch arrays.
- The upstream Rings DSP is designed around 48 kHz in this revision, while the current Felucca-derived FM-1 audio clock is approximately 44.1 kHz. Rate adaptation or a verified rate-specific build is required; simply changing a constant without validating filters, delay lengths, pitch and timing is not acceptable.

### Consequence for two independent Rings instances

The correct first architecture is **one Rings `Part` + one `Strummer` + one performance/patch state + one set of scratch storage per FM-1 track assigned RINGS A or RINGS B**. These are independent processors with their own internal four-resonator polyphony. The host's eight-note allocator remains the global input/event/voice budget; do not allocate a separate full host voice pool for each Rings instance.

The host note lifecycle should be adapted into block-level Rings performance events:
1. On host note-on/retrigger, update that track's note, velocity/excitation level and pending strum event.
2. On note-off, update the track's gate/strum policy without destroying resonator tails.
3. At the track's audio block, prepare the excitation buffer and performance state, run Strummer once for that instance, then process its Rings Part in chunks no larger than 24 samples.
4. Mix its stereo `out/aux` result into the track bus, preserving both outputs for independent routing.
5. Keep the Rings Part alive while resonator tails continue, including when no host note voice is currently active.

This avoids the incorrect design of creating a separate Rings Part per Felucca `voice_t`. It also means the engine adapter needs a persistent per-track runtime and a reliable way to receive note events and render a per-track tail. The current `engine_t.post` hook is a plausible tail/render point, but its exact call conditions and output ownership must be verified in `voice.c` before implementation.

### Still to prove before coding

- [ ] Exact ordering and call conditions of `block`, per-voice `render`, and `post` in host `voice.c`.
- [ ] How note-on/off/retrigger events are exposed to a per-track runtime without relying on a voice slot that can be stolen or reused.
- [ ] Whether per-track Rings state can be reserved outside the transient `ENG_MEM_PART` overlay without exhausting linker pool/RAM.
- [ ] Correct 44.1-to-48 kHz treatment and 32-to-24 chunk scheduling, including excitation alignment and stereo latency.
- [ ] Per-instance resource measurement for two Rings Parts, with all auxiliary state and no dedicated Rings reverb buffers.
- [ ] Regression tests for two simultaneous notes/instances, voice stealing, note-off tails, and independent parameter/model changes.


## Host render lifecycle verified in `firmware/src/voice.c`

The track render path confirms the following order for each control block:

1. It calls `engine_t.block(track)` once before iterating active host voices.
2. It calls `engine_t.render(track, voice, ...)` once for each active host voice that reaches the render stage.
3. It calls `engine_t.post(track, out, n)` once after the voice loop, regardless of whether any host voice rendered; the return value contributes to the track's active/tail count.

This is an important enabling detail: `post` can keep a persistent per-track Rings Part processing resonator tails when all host note voices have been released. However, it does **not** solve event delivery by itself.

### Adapter event bridge candidate

- Use `note_on` as the host note-on/retrigger event to update a fixed-size per-track event mailbox (note, velocity, gate/trigger, pitch bend/modulation snapshot as appropriate).
- Use `block` to consume the mailbox once per block and prepare the Rings performance state, excitation and strum decision.
- Use `post` to process the persistent Rings Part and add its stereo output to the track's output bus, including tails.
- Do not render the same Rings Part from every host voice's `render` callback; that would multiply processing and potentially trigger it several times per block.
- Note-off must be observed separately. The host voice's gate transition and release lifecycle must be traced to determine a safe bounded event hook; a one-shot note-on mailbox is not sufficient for correct internal/external strummer behaviour.
- The `post` callback receives the track's mono `out` buffer, not a dedicated stereo pair. The second Rings output therefore needs a separately allocated track stereo/aux bus or a documented routing extension. Do not silently collapse the aux pickup if independent stereo/dual-output routing is a product requirement.

The `post` callback is called after voice rendering and receives the same block length `n`; Rings processing must still obey its 24-sample maximum chunk size and the verified FM-1 sample-rate strategy above.


## Note-off and voice-steal lifecycle verified

The host's `trk_note_off(track, note)` releases matching voices by setting `gate = 0` and `stage = 3` (release). `trk_all_off` does the same for every active voice. The global allocator can also call `voice_kill`, setting `gate = 0` and `stage = 4` for a one-block fade before the voice becomes inactive.

There is no engine-level `note_off` callback in the pinned Felucca engine ABI. Therefore, a Rings adapter must not pretend the engine interface provides one.

A viable source-level approach is:
- `note_on` captures each new note/retrigger into a bounded per-track event queue or latest-event mailbox.
- At the next `block`/post stage, the adapter scans the track's fixed `v[NVOICE]` array for current `active`, `gate`, `note`, and velocity state to determine held-note and release transitions.
- A fixed per-track snapshot of the previous block's voice gates/notes detects note-off, all-off, voice steal and retrigger transitions without heap allocation.
- When no host key remains held, Rings' internal resonator state is allowed to ring out naturally; note-off must not hard-reset the Part; resonator tails must ring out naturally.

The snapshot must distinguish a released voice from a voice that has been stolen/reused for a new note in the same block. Tests must include same-note retrigger, rapid legato transitions, mono fallback, poly release, all-notes-off and global voice-budget stealing.

This approach is still a design proposal until the adapter code and tests exist, but the host data required to implement it is available through the `track_t` passed to the engine callbacks.



## Stereo output integration: current mix-path audit (2026-11-23)

A source inspection of `firmware/src/fx.c` establishes the current output topology:

- `track_render()` produces one mono block per track.
- `mix_part()` applies the track's DIST/INSERT/mute path, then level, pan and mono chorus/delay/reverb sends.
- The dry mix accumulators are stereo (`mix_l`, `mix_r`), but the three shared send buses are mono.
- With CPU2 enabled, each core owns a `mixsum_t` containing stereo dry sums and mono send sums. The two sums are merged before the shared FX/master path.
- The current engine `post(track, out, n)` callback receives only the mono track buffer. It cannot directly return Rings' native `out` and `aux` stereo pair.

Therefore, the Rings adapter must not simply add both Rings channels together in `post()` and claim stereo output or independent module ports. That would discard the original two-output behaviour and make later patch routing impossible.

### Required extension before live Rings audio integration

Introduce a bounded stereo processor-output path at the per-track mix stage:

1. Keep the existing mono engine callback path unchanged for existing engines.
2. Add an explicit optional stereo post-processor callback or equivalent per-track stereo result contract. It must run once per track/block, not once per host voice.
3. Give the stereo processor separate left/right scratch or bus buffers whose lifetime and ownership are explicit. Do not alias the mono `out` buffer or another track's scratch.
4. Preserve Rings' native two outputs as distinct left/right signals through level, pan and master mixing. Define how pan is applied without destroying the module's stereo width.
5. Keep the normal track mute/level behaviour predictable. Decide explicitly whether existing mono DIST/INSERT processing is bypassed, adapted to stereo, or applied before/after the Rings processor; do not silently collapse the pair.
6. If the patch graph exposes the two outputs as separate ports, connect those exact buffers to the graph. A visible cable must select a real signal, not a UI-only route.
7. Extend the CPU2 `mixsum_t` ownership/merge path so stereo module output is accumulated safely whichever core renders that part. Do not let both cores write the same scratch or accumulator.
8. Add regression tests for mono-engine bit-for-bit compatibility, Rings stereo separation, pan/level/mute, simultaneous RINGS A/B isolation, CPU2 on/off equivalence, and output clipping/headroom.

A practical first implementation may keep Rings' stereo pair as a dedicated post-track bus and mix it into the existing stereo dry sums. That is preferable to forcing it through the mono track buffer. The exact callback signature and effects order must be settled against the engine ABI before coding.

### Verified current limitation

The existing Felucca engine ABI has only the mono `post(track, out, n)` hook. A separate stereo hook is a host ABI extension, not an existing capability. This is an implementation requirement for faithful Rings output, not a claim that the stereo path already exists.


## Approved five-model Rings scope (user decision, 2026-11-23)

Both independent instances expose exactly these five original Rings resonator models:

1. Modal
2. Sympathetic Strings
3. String
4. FM Voice
5. Quantized Sympathetic Strings

The original String-and-Reverb model is deliberately excluded. Its dedicated Rings reverb object, processing path and 64 KiB backing buffer per instance are not part of this product. Do not allocate a Rings reverb buffer, expose a String-and-Reverb model selector, or describe this as a complete six-model Rings port. This is an adapted five-model Rings port; the retained five model algorithms remain subject to their fidelity requirements. The firmware's shared effects and the separate Clouds processor remain available elsewhere in the signal chain.

The no-reverb source adaptation must remove the Reverb member and its initialization/processing safely; passing a null buffer to the original unconditional initialization is not safe. The source patch must also remove the excluded model's special-case render behaviour and clamp model selection to the five retained enum values.
