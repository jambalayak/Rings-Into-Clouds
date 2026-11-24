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

## Memory-layout adaptation without DSP reduction

The original `String` class embeds two delay arrays in every object:

- `StringDelayLine`: 2,048 floats per String.
- `StiffnessDelayLine`: 1,024 floats per String.
- Eight Strings per Part, two independent Parts: 49,152 floats total, or 196,608 bytes at 32 bits per float.

This storage is a major SRAM constraint. The first memory adaptation must preserve both array lengths and the original delay-line read/write/interpolation algorithms while moving the arrays out of each `String` object:

1. Add a pointer-backed delay-line storage variant (or equivalent source-compatible wrapper) whose only per-object state is its buffer pointer, write pointer and delay value.
2. Initialise each `String` with its own external 2,048-float string buffer and 1,024-float stiffness buffer. `String::Init` must clear both buffers exactly as upstream `DelayLine::Init` does.
3. Give each `rings::Part` a distinct storage descriptor. The descriptor must map every one of its eight Strings to unique arrays; RINGS A and RINGS B must never alias.
4. Place the external arrays deliberately across ordinary RAM and POOL using named linker sections. This is a placement change only; it does not reduce the 196,608-byte storage requirement.
5. Keep the arrays static and aligned. No allocation, clearing, locking or page placement may occur in the audio interrupt.
6. Compare the adapted delay-line class against upstream for wraparound, integer and fractional reads, Hermite reads, allpass operation and reset. Then compare retained Rings model audio against upstream reference renders.

The combined memory lower bound remains tight even after the approved base-firmware removals. External storage is necessary to control placement, but is not by itself proof that two full Rings instances plus Clouds fit. The final target map must account for all other DSP state and required headroom before the integration is accepted.

### Exact upstream delay-line API findings

The pinned `stmlib/dsp/delay_line.h` implementation was inspected at stmlib revision
`d18def816c51d1da0c108236928b2bbd25c17481`. Its storage adaptation must preserve these
observable operations, not just the nominal buffer sizes:

- `Init()` delegates to `Reset()`; reset clears every sample, sets delay to 1 and
  write pointer to 0.
- `Write()` writes at the current pointer then decrements with wraparound.
- `Allpass()` reads at `(write_ptr + delay) % max_delay`, writes the allpass
  recurrence, and returns the original output recurrence.
- `Read()` supports configured delay, integer delay, linear fractional interpolation,
  and Hermite interpolation with the original four neighboring samples.
- `WriteRead()` writes before reading.

A pointer-backed replacement must retain these exact indexing and update semantics, including
the order of write and read. Do not replace modulo arithmetic with a mask unless equivalence
is proven for the exact power-of-two capacities and target integer widths. Keep the upstream
implementation available in the host reference test so the adapted implementation can be
compared sample-for-sample over wraparound and reset cases.

### Build-system gate discovered during source review

`tools/build.py` currently compiles `firmware/src/felucca.c` as one C translation
unit and links a single firmware object. It has no source list or C++ object integration for
the upstream Rings/Clouds translation units. `tools/check_cpp_toolchain.py` is only a
smoke probe for compiling one C++ object and combining it with a C object; it explicitly
does not verify the C++ runtime or upstream dependencies.

Before importing DSP code, the build work must therefore establish:

1. An explicit, pinned list of required `.cc` translation units and include roots.
2. The target C++ ABI and compiler flags, including a deliberate no-exceptions/no-RTTI policy
   if compatible with every dependency.
3. A C-compatible adapter boundary between the existing C firmware and the C++ DSP objects.
4. A complete link with the actual target linker, with no accidental host standard-library,
   exception, RTTI, static-initialisation or heap dependencies.
5. Map-file accounting for every object and section, and a repeatable build command that keeps
   the existing app-slot, RAM and POOL headroom checks.

No C++ source or DSP code has been added to the firmware build at this stage.
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

This manifest remains a source-review specification. The upstream source is consumed through pinned submodules and the 15 translation units compile-only for the target. The only current local source patch in that check removes an unused STM32 debug-pin include from a build copy of Clouds; no Rings algorithm or model patch has been applied, and none of the five-model runtime validation items is complete.

### C++ header/runtime compatibility detail

The pinned stmlib delay-line header is physically `dsp/delay_line.h` in the
`pichenettes/stmlib` repository and is included by Rings as
`stmlib/dsp/delay_line.h`. It uses `<algorithm>` and `std::fill` in `Reset()`.
The current compile-only check now compiles this header through the project-owned
freestanding `firmware/cxx/algorithm` wrapper and the target C-header sysroot;
all 15 selected Rings/Clouds/stmlib translation units compile successfully.

This is stronger than the initial one-object ABI probe, but it is still not a
complete final link. Keep `-nostdinc++`, do not add a host C++ library, and
continue auditing every transitive dependency. The next gate is to link the
actual DSP objects with the target linker and account for every unresolved
runtime/math symbol. A relocatable `ld -r` combination is not a complete
firmware link.

The source-compatible external-storage adaptation must preserve the pinned
header's public operations: `Init`, `Reset`, `set_delay`, `Write`,
`Allpass`, `WriteRead`, `Read()`, `Read(size_t)`, `Read(float)`,
and `ReadHermite(float)`. Its current object layout is exactly a write
pointer, delay value and inline sample array (plus the non-copyable
declaration); a replacement may substitute a buffer pointer for the inline
array, but must not change the update order or interpolation arithmetic.


### Explicit removal of the Rings reverb implementation

A direct inspection of the pinned upstream `rings/dsp/part.h` and `rings/dsp/part.cc`
reveals that removing only the `RESONATOR_MODEL_STRING_AND_REVERB` enum entry is
not sufficient. The upstream `Part` still includes `rings/dsp/fx/reverb.h`,
owns a `Reverb reverb_` member, accepts a reverb buffer in `Part::Init()`,
initialises that member, and executes its processing branch for the omitted model.

The user's approved scope is five Rings resonator models with **no additional Rings
reverb**. The eventual local patch must therefore, together:

1. Remove `RESONATOR_MODEL_STRING_AND_REVERB` from the exposed model enum and all
   model-selection/configuration logic.
2. Remove the `rings/dsp/fx/reverb.h` include and `Reverb reverb_` member from
   `rings::Part`.
3. Change `Part::Init(uint16_t* reverb_buffer)` to an initialization signature
   that requires no reverb buffer, and remove `reverb_.Init(reverb_buffer)`.
4. Remove the omitted model's processing branch and all reverb parameter calls.
5. Exclude the Rings reverb implementation from the imported source/dependency set
   unless another retained upstream component demonstrably requires it.
6. Keep the retained five model values and behaviour stable; update every caller,
   adapter and test for the revised Init signature.
7. Add a source audit that fails if `STRING_AND_REVERB`, `reverb_`,
   `reverb_buffer` or Rings-specific reverb includes remain in the imported Part
   implementation.

This is a deliberate product-scope reduction, not an approximation of the sixth
model. It does not prevent a separate optional modular reverb processor being
designed later, under its own memory and CPU budget. No such processor is added
by this patch.



### Reverb allocation and upstream null-buffer hazard

The pinned `rings/dsp/fx/reverb.h` defines its engine as
`FxEngine<32768, FORMAT_16_BIT>`. Its `Init(uint16_t* buffer)` calls
`engine_.Init(buffer)`; the pinned `rings/dsp/fx/fx_engine.h` stores that
pointer and clears the full configured buffer with `std::fill`. Therefore
each Rings `Part` requires a separate **32,768 × uint16_t = 65,536-byte
(64 KiB)** external reverb buffer while this member exists. Two Parts would
consume 131,072 bytes (128 KiB) for a feature the user explicitly declined.

The FM1_Locus reference calls `part->Init(NULL)`. That call is not safe with
this pinned upstream implementation: `FxEngine::Init` clears the supplied
buffer, so a null pointer is invalid. Do not copy that call or assume the
reverb is inert merely because the sixth model is not selected.

Removing the `Reverb` member and its Init call as specified above eliminates
the need for this buffer entirely. The source-based saving is 64 KiB per
independent Rings Part, 128 KiB for RINGS A and B, before any other object-size
or alignment effects. This is an upstream allocation calculation, not a
measured linker delta.
