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


## First measured target results (2026-11-27)

GitHub Actions run `45959937238` completed successfully on target compiler `pi32v2`. The existing SLICE and DRUM host regression suites also passed. This is a compile/size probe, not an audio integration or hardware test.

Target `sizeof` results:
- `TGenerator`: 1,944 bytes
- `XYGenerator`: 5,788 bytes (contains all four original X/Y channel objects)
- `RandomStream`: 524 bytes
- `RandomGenerator`: 4 bytes
- `OutputChannel`: 892 bytes (already included four times inside `XYGenerator`; do not add it again)
- `RandomSequence`: 180 bytes (already embedded inside TGenerator and XYGenerator; do not add it again)

The standalone object-storage subtotal for TGenerator + XYGenerator + RandomStream + RandomGenerator is 8,260 bytes. This excludes any future FM-1 event queue, track mapping, control structures, and stack usage.

The original `resources.cc` contains 45 inverse-CDF distribution tables with 387 float values each (69,660 bytes), plus three 257-entry float lookup tables (3,084 bytes), for 72,744 bytes of raw float table data. The 45 distribution tables cover the 5-by-9 bias/spread grid used by the full continuous Marbles random distribution; they are not dead data in the unmodified upstream implementation.

Baseline target diagnostic from the same run:
- XIP image: 496,204 / 581,564 bytes, 85,360 bytes free
- POOL: 335,088 / 368,640 bytes, 33,552 bytes free
- RAM .data + .bss: 62,788 / 73,728 bytes, 10,940 bytes free

A full-fidelity float-table port would leave only 12,616 bytes of XIP headroom before Marbles executable code and other support data are counted. The measured Marbles object-storage subtotal would leave 25,292 bytes of POOL headroom before integration overhead. Therefore the next experiment should test a Q15/int16 representation of the 45 inverse-CDF tables: all values are in [0, 1], and simple quantization to signed Q15 has a maximum pointwise table error of approximately 1.526e-5. This is a memory-saving hypothesis only; interpolation error, output distribution statistics, target code size and CPU cost must be tested before accepting it.

The target compiler now builds the Marbles translation units, but no Marbles object is initialized or processed. CPU cost is not yet measured. It must be measured on FM-1 hardware once a runtime integration exists; host timings are not a substitute.


## Q15 interpolation experiment

A deterministic 200,000-sample numerical comparison was run against the upstream float inverse-CDF tables. With the 45 tables quantized to signed Q15 and linearly interpolated after conversion back to float, the observed maximum output difference was 0.00001501 and the mean absolute difference was 0.00000391. This is a source-data simulation, not yet a compiled C++ host regression or a listening test.

The target overlay now generates Q15 versions of the 45 inverse-CDF tables and changes the Marbles interpolation helper to decode them. The three 257-entry float LUTs are left unchanged. A fresh target build is running to verify the patch and measure the actual image/resource reduction. No firmware behaviour is connected by this experiment.


## FM-1 Marbles routing and clock requirements (user-approved design direction)

The intended virtual Marbles-to-Rings signal routing is:
- X1 -> Rings instance 1 pitch.
- X2 -> Rings instance 2 pitch.
- T1 gate -> Rings instance 1 strum trigger.
- T2 gate -> Rings instance 2 strum trigger.
- X3 -> user-selectable modulation destination on either Rings 1 or Rings 2.
- Y output(s) -> user-selectable modulation destination(s) on either Rings 1 or Rings 2.
- T3 -> reserved for a selectable destination elsewhere in the instrument if the selected Marbles implementation exposes a distinct T3 gate/clock output. Confirm exact upstream output semantics before promising the routing; do not fabricate a third gate from the two-channel T generator.

Marbles must follow the FM-1 master tempo/transport, with selectable rhythmic subdivisions. It must not free-run independently when tempo sync is selected. The subdivision setting should drive the Marbles master clock/rate and T gate generation coherently, with reset/transport start behaviour aligned to the FM-1 sequencer. Preserve Marbles' own random timing, bias/spread, Deja Vu and gate behaviour within the selected tempo grid.

Important upstream implementation detail to resolve before integration: the pinned upstream XY generator declares three X channels and one Y channel; the T generator declares two T channels. Inspect the complete upstream output/ramp API and Marbles app wiring to establish whether the panel's third T output corresponds to a master clock, a derived output, or another path. Do not silently conflate the T generator's two slave gates with a third output.
