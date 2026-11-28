# Sample-rate characterization results (experimental)

Date: 2026-11-28. Initial 75-case run: [workflow 46104213643](https://github.com/jambalayak/Rings-Into-Clouds/actions/runs/46104213643). Extended-capture rerun: [workflow 46105243175, attempt 2](https://github.com/jambalayak/Rings-Into-Clouds/actions/runs/46105243175).

## Scope

The harness ran 75 cases: five resonator models, notes 36/60/84, and five excitation/parameter profiles. It compares original-float Rings rendered at 48 kHz with the same original-float DSP rendered at 44,117.647 Hz, after resampling the 48 kHz output to the target timebase. The target rate is calculated from 24 MHz / 544; it is not yet measured on physical FM-1 hardware.

The extended run increases only the `long_decay` capture from 6 to 12 seconds. It does not expand the pitch/profile matrix or change DSP coefficients.

## Updated 12-second results

10 ms RMS envelope correlation and target/reference RMS ratio, averaged across 15 cases per model:

| Model | OUT corr mean / min | OUT RMS ratio mean | T20 measured (both rates) |
|---|---:|---:|---:|
| Modal | 0.9993 / 0.9978 | 1.024 | 6 / 15 |
| Sympathetic Strings | 0.8858 / -0.0256 | 0.973 | 4 / 15 |
| String | 0.9738 / 0.7926 | 1.119 | 8 / 15 |
| FM Voice | 0.9758 / 0.7250 | 1.009 | 7 / 15 |
| Quantized Sympathetic Strings | 0.8645 / -0.2987 | 1.042 | 5 / 15 |

Only 30 of 75 cases produced a T20 crossing in both renders within the capture. A null T20 means the envelope did not cross -20 dB during the recorded segment; it is not a zero decay or a failure. Even 12 seconds is insufficient for many cases.

Important long-decay cases:
- Sympathetic Strings, note 84: OUT RMS ratio 1.416; envelope correlation 0.922; T20 5.268 s at 48 kHz versus 5.348 s at the calculated FM-1 rate. AUX T20 was 7.547 s versus 8.067 s.
- Quantized Sympathetic Strings, note 84: OUT RMS ratio 0.787; envelope correlation 0.911; T20 7.997 s versus 8.177 s. AUX T20 was 8.457 s versus 9.266 s.
- Modal long-decay cases retained high envelope correlations (0.998-0.999) and near-unity OUT RMS ratios, despite low phase-sensitive waveform SNR.
- String long-decay envelope correlations were high (0.968-0.998), while OUT RMS ratios ranged from 1.033 to 1.074.

The negative minimum correlations in the two sympathetic-string model groups are a warning that a single aggregate envelope-correlation score is not robust for every resonant/beating case. Inspect per-case envelopes and spectral evolution before drawing a listening-quality conclusion.

## Interpretation and limitations

This is a comparison of two sample rates using original floating-point Rings, not a packed-24 precision comparison and not a hardware listening test. The aggregate waveform SNR is phase-sensitive and is not a perceptual pass/fail metric for resonant feedback systems. The calculated target rate remains unverified on physical FM-1 hardware.

The extended workflow completed successfully and uploaded the audio/metrics artifact. Its full target-link diagnostic still reports POOL overflow: 389,920 B used against 368,640 B, exceeding the region by 21,280 B; ordinary RAM .data+.bss is 65,336 B of 73,728 B, leaving 8,392 B. Thus the diagnostic is not a successful firmware link or release build.

The Rings C ABI remains outside the live audio path. This experiment is not a playable firmware build.

## Follow-up

- Inspect per-case envelope traces and resonant spectral evolution, especially Sympathetic Strings and Quantized Sympathetic Strings.
- Improve the metric so beating/phase-sensitive envelopes cannot yield misleading aggregate correlations.
- Expand pitch coverage to 48/60/72/84/96 and the supported range, then broaden excitation and parameter profiles.
- Measure the physical FM-1 codec rate.
- Keep all work experimental. Do not reduce the five models, eight-string bank, independent Rings instances or authentic decay to solve memory constraints.
