# Single Rings instance requirements

## Product decision (2026-11-24)

RINGS INTO CLOUDS uses **one original Mutable Instruments Rings instance** feeding the Clouds processor. The previous two-instance RINGS A / RINGS B requirement is superseded by this decision. Do not allocate, expose, serialize or test a second Rings instance.

The single instance must retain its own complete, independent DSP state and expose the five approved original resonator models:

- Modal
- Sympathetic Strings
- String
- FM Voice
- Quantized Sympathetic Strings

The original String-and-Reverb model is intentionally excluded. Its dedicated reverb delay memory is not allocated. This does not remove Clouds' own native reverb control/effect.

## Ownership and behaviour

- Use one stable module identity, `rings_main`, for the Rings DSP instance.
- Own one `rings::Part`, one `rings::Strummer`, its excitation/state buffers and one output stream.
- Do not duplicate mutable Rings state or reserve a second Rings engine slot.
- Route the single Rings output to the shared Clouds processor by default; retain a dry/mixer route if the graph supports it without duplicating DSP.
- Preserve the inherited FM-1 global voice budget and MIDI/sequencer behaviour.
- Presets save and restore the one Rings model and parameter set plus Clouds settings and their connection.
- UI labels should say **RINGS**; do not show RINGS A/B selectors or imply dual operation.

## Fidelity and resource rules

Use the pinned upstream Rings DSP revision and retain the five approved models faithfully. Any compact delay-line storage adaptation must be compared against the upstream floating-point reference for every retained model, including SNR, peak error, decay behaviour and musical renders. Do not claim stock fidelity if a quantized storage adaptation changes output; document and expose any meaningful quality trade-off.

Keep the Clouds processor and its own native effect path separate from Rings. The single-instance decision is intended to recover memory for a useful Clouds recording window, not to silently shrink Rings algorithms or remove Clouds features.

## Acceptance tests

- Instantiate and initialize exactly one Rings Part and Strummer.
- Verify all five retained models render and respond to excitation and parameter changes.
- Verify the excluded String-and-Reverb model cannot be selected or loaded from a new preset.
- Verify Rings output is routed into Clouds with deterministic timing and no channel errors.
- Verify preset save/recall, MIDI, sequencing and audio regression behaviour.
- Measure target linker RAM and POOL usage separately, retaining at least 4 KiB ordinary-RAM and 8 KiB POOL headroom.
- Measure worst-case CPU/audio deadline with Rings and Clouds active.
- Record Harbor/emulator and physical FM-1 validation separately.

This document supersedes the former dual-instance requirement.