# RINGS INTO CLOUDS — M1 Rings Engine Integration

Status: initial single-engine implementation committed; full host suite and target validation pending.
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

Implemented eight EDIT controls:
1. EXC — crossfades a one-shot pluck impulse toward continuous noisy excitation.
2. STR — shifts the second and third modal ratios from harmonic toward inharmonic relationships.
3. BRT — weights the upper resonant modes.
4. DMP — controls the decay radius of all three modes.
5. POS — changes the balance of the second and third modes.
6. BODY — shapes the third mode's ratio and level.
7. TONE — controls a fixed-point output low-pass stage.
8. AIR — adds noise to the exciter.

The engine ships with eight factory presets: PLUCK, BELL, BOW, WOOD, GLASS, STRING, DRONE and METAL. These are presets of the same engine, not separate Rings models.

## Integration constraints and unresolved engineering work

1. Inspect all engine dispatch sites, including `voice.c`, preset serialization, editor protocol, engine browsing, factory preset enumeration, and tests.
2. Stable engine numbering is now fixed: SLICE 13, ADPCM 14, RINGS 15. NENGINES is 16 in every build; absent optional engines keep reserved descriptor slots and eng_idx() maps those unavailable IDs safely. RINGS is placed before ADPCM in display order so it is available in the EDIT engine-key bank while ADPCM remains last. Compile/test all supported build-flag combinations.
3. The first implementation uses a deterministic per-voice three-mode resonator. It uses the host voice's eight signed state words and adds no per-part ENG_MEM allocation. This is a deliberate first milestone; shared sympathetic interaction is not implemented.
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

## Initial implementation snapshot (2026-11-25)

- Added `firmware/src/eng_rings.c`, included once by `engines.c`, as the single `ENG_RINGS` engine at stable ID 15.
- The resonator is three damped second-order modal recurrences per voice. Coefficients are calculated once per render block from the host pitch increment and the STR / DMP controls; the audio loop uses bounded fixed-point arithmetic, a bounded xorshift exciter, and saturating state updates.
- Voice state uses `voice_t.s[0..7]`: six modal delay states, one output low-pass state and one DC-blocker history value. `voice_t.ph[0..1]` hold the exciter PRNG and the one-shot impulse flag. No dynamic allocation, floating point, or extra part memory is used.
- The engine follows the host pitch increment and amp ramp and receives the host shape / cutoff modulation values. Its resonator state continues through the host release envelope rather than being abruptly cleared at note-off.
- The engine table now has 16 stable slots. IDs 13 and 14 remain reserved for optional SLICE and ADPCM builds; ID 15 is RINGS in every build. The engine browser's selectable order includes RINGS and keeps ADPCM last.
- Added Rings preset categories and a favorites mapping in previously unused settings byte `favorites.factory[15][14]`; the existing ADPCM favorite byte `[15][13]` remains unchanged.
- Added `tests/rings_engine_test.c` to the host runner for deterministic output, non-silence, bounded state at parameter extremes, and audible response changes from resonator controls.
- An isolated local C harness compiled the engine callback source against stub host types and confirmed a non-silent pluck response. This is only a syntax / callback smoke check, not a firmware build or a run of the repository's integrated tests.

### Still required before calling M1 validated

1. Run `tests/run_tests.sh`, including the new Rings test, the expanded engine/preset golden renders, editor/UI tests, and project/user-preset migration tests.
2. Regenerate and review `tests/golden.txt`, `tests/cpu_baseline.txt`, and target instruction budget entries from actual host/target runs; do not invent baseline values.
3. Build with the actual JieLi / AC79 toolchain and verify the FM-1 package, audio CPU headroom, polyphonic voice stealing, release tails, MIDI, project save/load and editor protocol.
4. Check all supported combinations of `FELUCCA_SLICE`, `FELUCCA_ADPCM` and `FELUCCA_FM4` so the fixed engine IDs and editor list remain stable.
