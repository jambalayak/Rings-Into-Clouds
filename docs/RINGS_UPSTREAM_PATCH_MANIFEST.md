# Rings upstream patch manifest

## Scope and source baseline

This manifest records the project-owned changes required to build the user-approved five-model Rings port from Mutable Instruments' original source. It is not a claim that the source has already been imported or patched.

- Upstream: `pichenettes/eurorack`
- Pinned revision: `08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4`
- Relevant source: `rings/dsp/part.h`, `rings/dsp/part.cc`, and their transitive dependencies.
- Upstream licence: MIT. Preserve original copyright and licence notices in every copied/modified source file and include the upstream licence in the release attribution.
- Product scope: adapted Rings port with five original models. The sixth String-and-Reverb model is intentionally omitted by explicit user decision. Do not expose it in UI, presets, documentation or compatibility labels.

## Required five-model enum

The supported model order and stable model identities are:

| Value | Upstream model | Project status |
|---:|---|---|
| 0 | `RESONATOR_MODEL_MODAL` | retained |
| 1 | `RESONATOR_MODEL_SYMPATHETIC_STRING` | retained |
| 2 | `RESONATOR_MODEL_STRING` | retained |
| 3 | `RESONATOR_MODEL_FM_VOICE` | retained |
| 4 | `RESONATOR_MODEL_SYMPATHETIC_STRING_QUANTIZED` | retained |

The project enum terminator must become `RESONATOR_MODEL_LAST = 5`. No placeholder sixth model is permitted.

## Exact source edits required

### `rings/dsp/part.h`

1. Remove the include of `rings/dsp/fx/reverb.h`.
2. Change `Part::Init(uint16_t* reverb_buffer)` to a no-argument `Part::Init()`.
3. Remove the `RESONATOR_MODEL_STRING_AND_REVERB` enumerator. Keep the preceding five enumerators in their original order.
4. Remove the `Reverb reverb_;` member.
5. Retain all other DSP members and both stereo output buffers unchanged.

### `rings/dsp/part.cc`

1. Change the definition to `void Part::Init()`.
2. Remove the `reverb_.Init(reverb_buffer)` call. Keep limiter and note-filter initialization.
3. In `ConfigureResonators()`, remove the String-and-Reverb case label. Keep the other three string-family cases (Sympathetic String, String, Quantized Sympathetic String).
4. Change `has_dispersion` to test only `model_ == RESONATOR_MODEL_STRING`.
5. Remove the String-and-Reverb-only damping remapping in `RenderStringVoice()`.
6. Remove the complete final String-and-Reverb post-processing block in `Part::Process()`: stereo cross-mix, all `reverb_` parameter calls, `reverb_.Process()`, and its aux polarity conversion. Do not replace this with another reverb or a global effect.
7. Remove the final model-gain table entry and its comment. The table must have exactly `RESONATOR_MODEL_LAST` entries for the five retained models.

### Dependency and resource pruning

- Do not compile String-and-Reverb-only string-synth/Easter-egg translation units.
- Do not allocate, initialise, or process the per-instance Rings reverb buffer.
- Do not remove or alter the retained model's normal String dispersion, sympathetic-string LFOs, excitation, limiter, note filter, or stereo OUT/AUX behaviour.
- Do not substitute the FM-1 shared reverb bus for the omitted model. The omission is a removed model, not a hidden routing change.

## Runtime and adapter invariants

- Each active RINGS A/B instance owns its own `rings::Part`, `rings::Strummer`, performance state, patch state, event history and scratch buffers.
- The two instances must not share resonator state, strummer onset history, model state or output scratch.
- Preserve the original `out` and `aux` stereo outputs as separately addressable signals.
- Preserve the upstream maximum internal polyphony of four per Part, while respecting the FM-1's global eight sounding-voice budget.
- Keep expensive model/polyphony configuration outside the audio interrupt.
- Split the host's 32-sample control block into bounded Rings chunks no larger than upstream `kMaxBlockSize` (24) unless a separately tested source-level block-size adaptation is made.

## Validation checklist

- [ ] The five enum values match the table above and the sixth value is absent.
- [ ] No remaining `STRING_AND_REVERB`, `reverb_`, or Rings reverb-buffer reference exists in the imported Part source.
- [ ] The retained String model still enables dispersion.
- [ ] All five retained model paths compile and have reference-output tests.
- [ ] Two separately allocated Parts can be initialised and processed concurrently without state aliasing.
- [ ] Both OUT and AUX are preserved through the FM-1 stereo routing path.
- [ ] The compiler/linker map confirms the removed per-instance reverb allocation and reports both instance sizes.
- [ ] The build, DSP tests, audio deadline tests and FM-1/Harbor tests are run before claiming completion.

## Current implementation status

This manifest is a source-review specification only. No upstream Rings source has yet been copied into this repository, no patch has yet been applied to compiled code, and none of the validation items is claimed complete.
