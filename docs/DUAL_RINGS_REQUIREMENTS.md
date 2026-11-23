# Dual Rings instance requirements

## Product requirement

RINGS INTO CLOUDS must support **two simultaneous, independent instances of the original Mutable Instruments Rings engine**. This is a core instrument capability, not a doubled-voice mode, a second preset slot for one shared engine, or a simulated second resonator.

The two instances may use the same DSP implementation and model set, but each owns separate runtime state and can be configured and played independently.

## User-facing behaviour

Expose the two instances as **RINGS A** and **RINGS B** in the FM-1 part/engine selection system.

- Each instance is independently selectable and editable, using the same familiar per-part workflow used by FM-1 firmware to combine different synth engines.
- Both parts may select the same Rings engine simultaneously.
- Editing A must never alter B, and vice versa.
- Each instance has its own resonator model, excitation settings, structure, brightness, damping, position, tune, FM/strum settings where supported, modulation assignments, enable/bypass state and performance configuration.
- Each instance has independent preset/state storage. A complete instrument preset also saves and restores both instances and their routing.
- Both can sound at the same time, including layered notes, different note ranges or separately sequenced parts where the existing keyboard/part system supports them.
- Each instance has an independent audio output port so the modular graph can route A and B differently, in parallel or in series where supported.
- The interface must make the selected instance unmistakable. Show RINGS A or RINGS B in the module title and parameter context; never show ambiguous shared controls.

## Approved five-model scope (2026-11-23)

The product uses an adapted five-model Rings port in **both** instances. The supported models are Modal, Sympathetic Strings, String, FM Voice and Quantized Sympathetic Strings. The original String-and-Reverb model and its dedicated 64 KiB reverb delay memory are intentionally excluded from both instances by user decision. Do not expose that model in either selector or preset format, and do not substitute a shared effect and label it as the omitted model. This omission does not reduce the fidelity requirements for the five retained models and does not remove the firmware's shared effects or the separate Clouds processor.

The upstream `rings::Part::Init(uint16_t*)` cannot safely be called with a null reverb buffer: `Reverb::Init()` calls `FxEngine::Init()`, which clears the supplied buffer. The port must therefore make a source-level no-reverb adaptation (remove the per-Part `Reverb` member and its initialization/processing path, or provide an equivalently safe compile-time exclusion) rather than merely passing null. This is a required integration patch and must be covered by compile and runtime tests.

## Part and voice behaviour

Use two separate FM-1 parts/tracks as the initial ownership model. Source inspection confirms the inherited firmware already has four independent synth parts: each track stores its own selected engine, parameter array, preset and voice state, while all four parts share one global budget of eight sounding voices. The engine table is shared, but each part has its own engine-memory region. This is a strong fit for selecting the same Rings engine on two tracks, provided the Rings integration gives each part a distinct DSP state object and does not put mutable state in shared globals.

- Allocate a distinct Rings DSP object/state block per instance.
- Keep each instance's parameter state, note/trigger state, exciter state, resonator delay/state, strummer state and modulation state independent.
- Both instances participate in the FM-1's shared global voice/CPU budget. The inherited voice allocator explicitly enforces eight sounding voices across all four parts, even though each part has storage for eight voice records; Rings must use this global budget rather than assuming eight additional voices per instance. Do not promise two full independent eight-voice allocations if the platform only has eight sounding voices globally.
- Establish and document how the global voice allocator accounts for Rings voices and how voice stealing works across A, B and other engines.
- A note or trigger sent to A must not excite B unless an explicit patch connection routes an event to B.
- Shared immutable tables/constants may be shared only where safe; mutable DSP state and buffers must never alias.

## Fidelity

Both instances must run the same pinned Rings DSP revision and expose the same verified supported model set and parameter behaviour. Any model omitted for resource reasons must be omitted consistently and explicitly documented for both instances. Do not make B a reduced-quality or alternate approximation to save resources without an explicit, visible profile choice.

## Resource and scheduling requirements

Two simultaneous Rings instances increase state memory and worst-case processing cost. The integration plan must therefore:

1. Measure the exact object and auxiliary-state size for two rings::Part instances and two rings::Strummer instances using the target compiler.
2. Include per-instance exciter, resonator, strummer, modulation, input/output and resampler state in the memory inventory.
3. Measure worst-case CPU time with both instances active in the most expensive supported model/configuration, then with Clouds and the rest of the planned graph active.
4. Keep both instances within the same hard audio deadline and memory headroom requirements; never allocate, construct, prepare or free DSP state in the audio interrupt.
5. Make resource validation aware of instance count. If a patch cannot fit, report the specific resource conflict before activation rather than silently disabling one Rings.
6. Keep an independently testable one-Rings fallback during development, but the product acceptance target remains two simultaneous instances.

Do not assume the second Rings instance costs exactly twice the first: immutable tables, shared code and compiler/linker placement may be shared, while mutable state and audio buffers are duplicated. Measure it.

## Patch graph and presets

Use stable module instance IDs, for example rings_a and rings_b, not array position or UI page number. Each instance exposes its own typed audio, modulation and event ports. Preset serialization must store both module identities and independent parameter values, and graph validation must reject duplicate IDs or references to a missing instance.

A useful default patch is:

- Part 1 / RINGS A -> mixer input 1
- Part 2 / RINGS B -> mixer input 2
- Both parts can feed a shared Clouds processor, or separate processor instances only if the measured resource profile permits them.
- Each Rings output may also be routed independently to Clouds, effects or the mixer.

The default must remain immediately playable and must not require patch programming.

## Acceptance tests

- Instantiate two Rings objects and prove their mutable state is disjoint.
- Set visibly and audibly different parameters on A and B; verify edits do not cross-contaminate.
- Trigger both instances concurrently and confirm both produce audio.
- Verify separate model selection, parameter editing, preset save/recall and modulation.
- Verify each audio output can be routed independently.
- Test layered and split/sequenced use cases supported by the FM-1 control system.
- Measure CPU, ordinary RAM and POOL use with both active.
- Stress both instances with Clouds and MIDI clock/transport active; record audio deadline and stability results.
- Run long-duration simultaneous playback and rapid A/B parameter changes without crashes, stuck notes or buffer errors.

## Status

This document records the required behaviour. It does not claim that dual Rings DSP instances have been imported, compiled, scheduled or tested on an FM-1. The implementation remains subject to target memory and CPU measurements, but the product requirement is two simultaneous independent Rings instances.


## Confirmed base-firmware fit (2026-11-23)

Source inspection of firmware/src/core.h, firmware/src/engines.c and firmware/src/voice.c confirms:
- Four independent synth parts/tracks exist.
- Each part selects its own engine and stores its own parameter and preset state.
- Each part has a dedicated engine-memory region; large engine state is overlaid per part because only one engine is selected on that part at a time.
- All four parts share a global maximum of eight sounding voices, enforced by the common voice allocator.
- Therefore, assigning the Rings engine to two different parts is consistent with the existing FM-1 engine-selection model. The Rings implementation still needs per-part mutable DSP state and a correct wrapper/voice adapter.

This is source-level architecture evidence, not a completed dual-Rings implementation or target test.
