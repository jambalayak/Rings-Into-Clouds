# RINGS INTO CLOUDS — M1 Rings Engine Integration

Status: architecture decision; implementation not yet started.
Branch: `rings-into-clouds-dev`

## Product decision

RINGS INTO CLOUDS will contain **one Rings-inspired resonator engine**. It will not expose separate Modal, String, Sympathetic, FM, or other Rings models as independent engine entries. Those are not separate engines in the product.

The engine should feel like one coherent instrument: a playable exciter feeding a resonant body, with a small set of expressive macro controls. The existing sequencer, MIDI, keyboard, modulation matrix, envelopes, and track effects remain available.

## What the source audit established

- The host engine interface is declared in the pinned Felucca-Engines submodule at `firmware/engines/src/felucca_engine.h`.
- An engine provides `note_on` and `render` callbacks, up to eight EDIT parameters, preset data, a polyphony cap, and optional hooks.
- Importantly, `engine_t` also provides an optional `post` callback. It processes the complete part after its voices and can keep a resonant tail alive after the notes stop. This is a suitable integration point for a shared resonator stage if the chosen design requires it.
- Engine state can live in the per-part `ENG_MEM` region, with a compile-time `ENG_MEM_FITS` assertion. The current region is 12,888 bytes when ADPCM is disabled and 13,344 bytes when enabled.
- The firmware is a single C translation unit assembled in `firmware/src/felucca.c`; include order matters.
- Engine IDs are persisted in projects, presets, and the editor protocol. Existing IDs must never be reordered or reused.
- PHYS already contains a sympathetic-string DSP model, but it is a four-model physical-modelling engine and is not the single, unified Rings instrument requested here.

## Source and licensing decision

The upstream Mutable Instruments Rings DSP source inspected at `pichenettes/eurorack/rings/dsp/part.h` and `part.cc` carries MIT license notices. The upstream implementation is C++ and depends on stmlib and other Rings modules; it is not a drop-in C engine for this firmware's current C single-translation-unit build.

Do not paste the upstream C++ `Part` implementation into the firmware or silently omit its dependencies. The preferred path is a focused, original fixed-point C implementation informed by the documented DSP architecture, or a carefully scoped MIT port of the required DSP pieces with all upstream copyright/license notices and dependencies preserved. The exact source revision and every imported file's license must be recorded before importing code.

## Proposed single-engine design

Working engine name: `RINGS`.

- One engine entry and one preset family.
- One resonator identity and one continuous control set; no user-facing model selector that turns it into a collection of separate instruments.
- Excitation: velocity-sensitive transient/noise/pluck excitation, with optional continuous excitation controlled by a macro.
- Resonator: tuned modal/resonant structure with controllable brightness, damping, inharmonicity, and body character.
- Pitch follows the host's note, glide, tuning, and modulation data.
- Resonant state must ring naturally through note release; the host's envelope should shape excitation/voice level without abruptly truncating the resonator tail.
- Start with conservative polyphony and fixed-point arithmetic. Measure worst-case CPU before increasing it.
- Keep the design independent of a Clouds/granular engine. The later granular processor should be a separate post-voice/part effect stage, not another Rings engine.

Suggested eight EDIT macros (labels are provisional and must be checked against the display constraints):
1. EXCITE — strike/pluck intensity and character.
2. STRUCT — harmonic-to-inharmonic partial distribution.
3. BRIGHT — excitation and resonator brightness.
4. DAMP — decay time.
5. POS — excitation position / spectral nulls.
6. SPACE — resonator/body spread.
7. MOTION — subtle modulation of resonant partials.
8. LEVEL — resonator output balance.

## Integration constraints and unresolved engineering work

1. Inspect all engine dispatch sites, including `voice.c`, preset serialization, editor protocol, engine browsing, factory preset enumeration, and tests.
2. Resolve stable engine numbering. Current optional engines occupy IDs 13 (SLICE) and 14 (ADPCM); a new append-only ID must not collide when either optional build flag is off. Do not simply append an array item and assume the ID is stable. Use explicit reserved slots or a documented fixed-ID mapping, and test all supported build-flag combinations.
3. Confirm whether the resonator is per voice, shared per part, or a hybrid. A shared part resonator may better reflect Rings' resonant-body interaction, but note allocation and multi-note behavior must be deterministic.
4. Calculate actual state size with target compiler types and add `ENG_MEM_FITS`. Do not increase the global per-part memory pool without a measured RAM budget.
5. Avoid floating point in the target audio loop unless the toolchain and benchmark demonstrate it is safe.
6. Add deterministic host tests for impulse response, pitch tracking, decay, clipping bounds, note retrigger, voice stealing, and silence/tail behavior.
7. Build with the actual JieLi/AC79 toolchain and run the existing regression suite. A browser/emulator build alone is not target validation.

## M1 acceptance criteria

- Exactly one selectable RINGS engine.
- Existing engine IDs, presets, projects, and editor protocol remain compatible.
- One coherent resonator voice with expressive macros and playable MIDI/keyboard input.
- No unbounded audio-loop work, dynamic allocation, or unmeasured state growth.
- Tests and target build results are recorded honestly; no claim of hardware validation until an FM-1 is available.
