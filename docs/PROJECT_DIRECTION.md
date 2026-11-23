# RINGS INTO CLOUDS — Project Direction

**Target:** M-VAVE FM-1  
**Base:** Felucca (GPL-3.0-only), with its existing hardware layer and build system  
**Development branch:** `development`

## Product identity

RINGS INTO CLOUDS is a standalone FM-1 instrument built around expressive physical modelling, resonant tones and granular sound transformation. Its visual language takes inspiration from Mutable Instruments' module artwork, colour palettes, typography, diagrams and panel layouts, reinterpreted as original artwork and a readable FM-1 screen interface. Do not copy Mutable Instruments logos, illustrations or panel artwork verbatim.

## Verified starting-point facts

- This repository is a fork of `hugelton/Felucca`; the initial code is the upstream Felucca code, not a completed RINGS INTO CLOUDS implementation.
- Felucca's `PHYS` engine currently offers MODAL, STRNG, MEMB and SYMP models. Its source documents fixed-point physical-modelling DSP ported from DaisySP and Rings sympathetic strings.
- Felucca has an existing GRAIN engine, FX layer, four parts, shared voice budget, modulation matrix, arpeggiator and 64-step sequencer. These are useful foundations to study and extend.
- The presence of Rings-derived physical-modelling code is not the same as a complete port of every Mutable Instruments Rings mode.
- A dedicated Clouds-style granular processor is not yet established by this fork. The GRAIN engine must be assessed before deciding whether to extend it or integrate a separate compatible Clouds DSP implementation.
- The hardware build depends on the Felucca submodules, JieLi toolchain and AC79 SDK described in `BUILDING.md`. A GitHub source ZIP alone is not a complete local build checkout.

## Design principles

1. Preserve a reliable FM-1 hardware foundation before large DSP changes.
2. Make real audio and playable controls the priority; visual mock-ups must not stand in for working synthesis.
3. Keep the core sound path flexible: excitation/source → resonator → granular processor → spatial effects, with user-selectable routing where CPU and memory allow.
4. Treat Rings resonator, Clouds granular processing, Marbles generative sequencing and Yarns-style arpeggiation as distinct systems with clearly documented behaviour.
5. Benchmark CPU, RAM, latency and voice count on the actual FM-1 target. Do not promise simultaneous full-quality processing until measured.
6. Preserve upstream history and keep development changes on this branch until tested.

## Planned milestones

### 0 — Baseline and build audit
- Record the upstream commit and submodule revisions.
- Inspect the FM-1 controls, display dimensions, audio path, memory layout, voice allocator and CPU budgets.
- Confirm the build and regression-test workflow, including required submodules and SDK/toolchain.
- Establish a reproducible baseline before changing DSP.

### 1 — Instrument identity and UI foundation
- Rename user-facing product identity to RINGS INTO CLOUDS without breaking package/update identity or project compatibility.
- Design an original Mutable Instruments-inspired palette, module cards, typography and graphic motifs for the FM-1 display.
- Keep labels, values and navigation legible at the device's actual resolution.

### 2 — Resonator and exciter
- Audit the existing PHYS models against the intended Rings behaviour.
- Identify missing Rings modes and hidden/easter-egg modes; implement only after DSP and licensing review.
- Add or refine excitation types (pluck, strike, bow and blow) where practical.

### 3 — Granular processor
- Audit the existing GRAIN engine, buffer sizes, memory use and routing.
- Compare it with the intended Clouds modes and controls.
- Choose a measured implementation path: extend existing code or integrate a compatible upstream DSP implementation with correct attribution and licence notices.

### 4 — Performance and modulation
- Integrate the resonator and granular processor into a usable performance workflow.
- Add assignable modulation and independently controllable spatial effects within measured hardware limits.
- Preserve direct keyboard playing and preset recall.

### 5 — Generative and conventional sequencing
- Develop Marbles-inspired random pitch, trigger, looping and probability behaviour as a dedicated system.
- Retain and improve conventional step sequencing separately.
- Keep the arpeggiator separate from both.

### 6 — Verification and release
- Run host regression tests and target builds after each meaningful change.
- Test sound, controls, storage, preset compatibility and update/recovery paths.
- Only label a build hardware-ready after installation and playback have been verified on a physical FM-1.

## Licensing and attribution

Felucca is GPL-3.0-only, while its hardware layer, engine submodule and several third-party DSP components retain their own licences. Every imported or adapted component must be checked at its exact upstream revision. Preserve copyright notices, licence texts and source attribution; update `LICENSING.md` before distributing a derived firmware build.
