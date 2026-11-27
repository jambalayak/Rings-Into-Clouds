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
- T3 -> user-selectable modulation/trigger destination elsewhere in the instrument. Upstream T1 and T3 are the two derived gate streams; T2 is the jittered master-clock output (the master ramp/gate), so the three physical outputs are all accounted for by the two slave ramps plus the master ramp.

Marbles must follow the FM-1 master tempo/transport, with selectable rhythmic subdivisions. It must not free-run independently when tempo sync is selected. The subdivision setting should drive the Marbles master clock/rate and T gate generation coherently, with reset/transport start behaviour aligned to the FM-1 sequencer. Preserve Marbles' own random timing, bias/spread, Deja Vu and gate behaviour within the selected tempo grid.

Confirmed upstream output semantics: the pinned XY generator declares three X channels and one Y channel. The T generator declares two slave gate channels (T1 and T3); T2 is the master clock ramp/output. Preserve this distinction when adapting its buffers to FM-1 event triggers. T2 is a valid strum trigger destination for Rings 2, as requested, even though it is the master clock rather than a second random gate.


### Confirmed Marbles output semantics

The upstream implementation's `Ramps` structure has a master ramp and two slave ramps. The physical outputs correspond to:
- T1: first derived random gate stream (`slave[0]`)
- T2: jittered master clock (`master`)
- T3: second derived random gate stream (`slave[1]`)

The X generator has three X channels and one Y channel. In its default internal T-clock mode, the three X outputs are associated with the three T timing streams; Y is a slower random modulation output (default rate 1/16 of X2, with its own division control in the original UI). FM-1 routing should preserve this timing relationship unless the user deliberately selects another clocking mode.

The requested T1 -> Rings 1 strum and T2 -> Rings 2 strum mapping is intentional and valid: Rings 2 is clocked from the Marbles master pulse, while Rings 1 receives the T1 random gate stream. T3 remains available as a selectable auxiliary gate destination.


## Q15 target-link result (run 45961122280)

The corrected Q15 overlay compiled and linked successfully for the FM-1 `pi32v2` target. The same run passed the existing SLICE and DRUM host regression suites. This remains a diagnostic link, not an installable firmware integration.

Target-linked results with Marbles DSP objects and Q15 resources retained:
- Application image: 541,900 bytes / 581,564-byte capacity; 39,664 bytes free.
- RAM `.data + .bss`: 63,908 / 73,728 bytes; 9,820 bytes free.
- POOL: 343,376 / 368,640 bytes; 25,264 bytes free.
- Each of the 45 Q15 inverse-CDF tables is 774 bytes (387 signed 16-bit entries); the complete 45-table data set is 34,830 bytes.
- Three other 257-entry float lookup tables remain float.
- Marbles object sizes: TGenerator 1,944 B; XYGenerator 5,788 B; RandomStream 524 B; RandomGenerator 4 B. The measured `OutputChannel` and `RandomSequence` sizes are already embedded in XYGenerator/TGenerator and must not be double-counted.
- The linker retained Marbles resources and eight Marbles DSP translation units. No Marbles objects are constructed or processed yet.

The Marbles-enabled target diagnostic increases XIP by 45,696 bytes and POOL by 8,288 bytes relative to the prior no-Marble target diagnostic. This includes linked code/resources and sizing-anchor storage, not a final runtime allocation plan. Compared with retaining the original float distribution tables, Q15 saves 34,830 bytes of XIP table data.

With only 39,664 bytes of XIP and 25,264 bytes of POOL remaining, keep the next work focused on a minimal Marbles runtime/event integration and precise allocation audit. Do not start a second Rings instance or allocate duplicate Clouds processors. The user's required X1/X2 and T1/T2 routing must be preserved; T2 is the master-clock output, not the second derived random gate.


## Tempo-sync implementation direction

The FM-1 already has a single transport clock and a shared beat-duration helper in `fx.c` (`beat_samples()`), which resolves to the project BPM for internal tempo or the measured MIDI clock tempo when external sync is selected. The sequencer's `events_block(n)` runs once before the track render in each audio half.

The Marbles T generator can run from its internal oscillator at a host-controlled frequency. Its base rate is 2 Hz at 120 BPM; therefore the synced master-clock frequency can be derived from the FM-1 beat duration and a selected subdivision multiplier. Keep its 1x range and calculate the semitone-rate control from the host tempo/subdivision, while leaving the original jitter and random T1/T3 gate generation active. Transport start/restart should reset Marbles' phase and Deja Vu position; stop should stop or freeze its clock according to the selected sync mode. External MIDI clock tempo changes must update the same clock source without creating a second independent transport.

For every audio block:
1. Set TGenerator's rate from the current FM-1 beat length and selected subdivision.
2. Process TGenerator to produce the T1/T3 slave ramps/gate flags and T2 master ramp.
3. Derive the T2 50%-duty gate's rising edge from the master ramp wrap/phase, not by treating T2 as a second slave gate.
4. Pass the three T timing ramps into XYGenerator in its internal T1/T2/T3 clock mode, yielding X1, X2, X3 and the slower Y output.
5. Convert X1/X2 to Rings pitch values; T1/T2 edges to the two Rings strum triggers; route X3, Y and T3 through a selectable modulation/destination matrix.

Use sample-offset trigger events (or split the Rings processing block at event offsets) so the two strum inputs retain their actual timing inside the 128-frame audio half. Avoid calling ordinary `trk_note_on` as a substitute for Rings' strum API. The Marbles DSP must not generate MIDI note events on the sequencer tracks unless a separate user-facing routing option explicitly requests that behaviour.

The existing Rings C ABI currently exposes one Rings Part, one Strummer and one Clouds processor; its setters for Marbles routing, per-Rings parameters, pitch/strum state and modulation destinations still need to be designed. The present `events_block`/mix ordering also has a performance-FX early return, so decide deliberately whether the Rings/Clouds instrument is inserted before the performance layer or only on the normal master path. Do not leave one path silently bypassing the instrument.

CPU has not been measured. Run the Marbles T/XY processing in a target audio-budget experiment before turning it on in the real-time mix path.
