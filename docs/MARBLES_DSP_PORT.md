# Marbles DSP port investigation

Status: isolated sizing experiment only. No Marbles behaviour is connected to the FM-1 audio or sequencing path, and this branch is not approved for merge.

## Product constraints

- Marbles has priority over a second Rings instance.
- Preserve the existing compact Clouds experiment buffers: 32,768-byte small buffer, 86,144-byte large buffer, and 53,376-byte workspace.
- Keep the primary Rings track's selectable 1/2/4 resonator polyphony.
- Do not change protected branches or promote this experiment.
- Do not claim a usable firmware package until DSP initialization, event scheduling, audio integration, and FM-1 testing exist.

## Port boundary

The upstream Mutable Instruments Marbles firmware is MIT-licensed. The port should retain attribution and the MIT notice with copied source.

The relevant DSP is separated from Eurorack hardware:
- `marbles/random/t_generator.*`: clock/rhythm generation, gate patterns, probability and jitter.
- `marbles/random/x_y_generator.*`: random voltage generation, channel correlation, Deja Vu and output timing.
- `marbles/random/random_sequence.h`: 16-step Deja Vu loop and 16-value history/replay.
- `marbles/random/output_channel.*`, `quantizer.*`, `discrete_distribution_quantizer.*`, `lag_processor.*`: random pitch shaping, scale quantization and glide.
- `marbles/ramp/*`: clock/ramp extraction and division used by the original external-clock-capable implementation.
- `marbles/resources.cc`: generated distribution and interpolation lookup tables.

Eurorack-only pieces to exclude from the FM-1 adaptation include ADC/DAC drivers, CV calibration, physical knob/button/LED scanning, hardware clock input self-patching, scale-recording CV acquisition, and module-specific persistence/calibration.

## FM-1 adaptation questions

1. The FM-1 already has a transport and sequencer clock. Determine whether Marbles should follow that clock directly, avoiding a second competing master clock and the external-clock ramp acquisition path.
2. Map Marbles' X output to melodic note generation and T outputs to gate/probability or ratchet decisions. Do not assume that the full Eurorack four-channel CV layout is needed.
3. Preserve Deja Vu repeat/mutate/lock behaviour, and make the number of generated melodic lanes configurable only after the resource budget is measured.
4. The current firmware's scale and note-on pipeline must be inspected before selecting the exact event insertion point. Avoid generating events from the audio ISR.
5. Measure target code/XIP, .data/.bss, POOL and CPU separately. Object `sizeof` is only a first diagnostic and is not a substitute for linked-image memory or runtime load.

## Current experiment

`tools/check_upstream_dsp_compile.py` now compiles the upstream Marbles random and ramp translation units with the pinned FM-1 target compiler and emits target `sizeof` symbols for TGenerator, XYGenerator, OutputChannel, RandomSequence, RandomStream and RandomGenerator.

These objects are compile-only at this stage. They are deliberately not added to the firmware link manifest and are not constructed or processed. The target workflow is enabled on this branch to collect the first compiler and object-size results.

The generated upstream `marbles/resources.cc` is compiled as part of the check, but its full lookup-table footprint is not assumed to be acceptable. The linked subset and any reduction/approximation strategy must be measured before a port is selected.
