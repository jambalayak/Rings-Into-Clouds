# Sample-rate characterization results (experimental)

Date: 2026-11-28. Source: [workflow run 46104213643](https://github.com/jambalayak/Rings-Into-Clouds/actions/runs/46104213643), commit `4ace9d0224bc3f3191b10bad3efa14e224216495`.

## Scope

The initial corrected harness ran 75 cases: five resonator models, notes 36/60/84, and five excitation/parameter profiles. It compares original-float Rings rendered at 48 kHz with the same original-float DSP rendered at 44,117.647 Hz, after resampling the 48 kHz output to the target timebase. The target rate is calculated from 24 MHz / 544; it is not yet measured on physical FM-1 hardware.

## Per-model phase-independent averages

10 ms RMS envelope correlation and target/reference RMS ratio, averaged across 15 cases per model:

| Model | OUT corr mean / min | OUT RMS ratio mean | AUX corr mean | AUX RMS ratio mean |
|---|---:|---:|---:|---:|
| Modal | 0.9987 / 0.9948 | 1.022 | 0.9989 | 1.015 |
| Sympathetic Strings | 0.9121 / 0.2508 | 0.976 | 0.9125 | 0.978 |
| String | 0.9698 / 0.7924 | 1.118 | 0.9690 | 1.115 |
| FM Voice | 0.9658 / 0.5739 | 1.009 | 0.9988 | 0.999 |
| Quantized Sympathetic Strings | 0.9140 / 0.5195 | 1.041 | 0.8943 | 1.029 |

These averages hide important outliers. The worst Sympathetic Strings case is note 84 / long_decay: OUT target/reference RMS ratio 1.444 (44.4% higher), envelope correlation 0.901, and T20 5.268 s reference versus 5.348 s target. The worst Quantized Sympathetic Strings case is note 84 / long_decay: OUT RMS ratio 0.785 and envelope correlation 0.808. Modal's worst waveform-SNR case (note 84 / long_decay) still has OUT envelope correlation 0.998 and RMS ratio 0.988, illustrating why raw waveform SNR alone is not a perceptual verdict.

The aggregate waveform SNR is 1.076 dB. This is phase-sensitive and must not be used as a perceptual pass/fail metric for resonant feedback systems.

## Decay measurement limitation and follow-up

The original six-second long_decay segment is too short to produce a -20 dB envelope crossing for many cases; T20 is therefore null where no crossing was observed. That means "not measured within the capture", not zero decay or an immediate decay failure. The long_decay capture has now been extended to 12 seconds in commit `95edeaf68a5147918237a598f0f9aac8b12d30c4` to improve T20 coverage. The next workflow must be inspected before replacing these initial results.

## Important interpretation

This is a comparison of two sample rates using the original floating-point DSP, not a packed-24 precision comparison. It characterizes rate sensitivity, not hardware sound quality. The rate is calculated, not hardware measured. No live FM-1 integration or listening test has been recorded.

## Memory and architecture boundary

The full diagnostic link previously overflowed POOL by 21,280 bytes and retained only a reduced second-Rings probe, not a full independent eight-string second instance. The Rings C ABI remains outside the live audio path. This experiment is not a playable firmware build.

## Follow-up

- Review the 12-second long-decay run and T20 coverage.
- Investigate model-specific resonant frequency, damping, spectral peak and beating differences, especially Sympathetic Strings and Quantized Sympathetic Strings.
- Expand pitch coverage to 48/60/72/84/96 and the supported range.
- Measure the physical FM-1 codec rate.
- Keep all work experimental. Do not reduce the five models, eight-string bank, independent Rings instances or authentic decay to solve memory constraints.
