# Sample-rate characterization results (experimental)

Date: 2026-11-28. Initial 75-case run: [workflow 46104213643](https://github.com/jambalayak/Rings-Into-Clouds/actions/runs/46104213643). Extended-capture rerun: [workflow 46105243175, attempt 2](https://github.com/jambalayak/Rings-Into-Clouds/actions/runs/46105243175). Added 100 ms envelope metrics: [workflow 46113594758](https://github.com/jambalayak/Rings-Into-Clouds/actions/runs/46113594758).

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
- Sympathetic Strings, note 84: OUT RMS ratio 1.416; 10 ms envelope correlation 0.922; T20 5.268 s at 48 kHz versus 5.348 s at the calculated FM-1 rate. AUX T20 was 7.547 s versus 8.067 s.
- Quantized Sympathetic Strings, note 84: OUT RMS ratio 0.787; 10 ms envelope correlation 0.911; T20 7.997 s versus 8.177 s. AUX T20 was 8.457 s versus 9.266 s.
- Modal long-decay cases retained high envelope correlations (0.998-0.999) and near-unity OUT RMS ratios, despite low phase-sensitive waveform SNR.
- String long-decay envelope correlations were high (0.968-0.998), while OUT RMS ratios ranged from 1.033 to 1.074.

## 100 ms envelope follow-up

Workflow 46113594758 added a coarser 100 ms RMS envelope correlation and a bounded best-lag search (up to five 100 ms windows, or approximately 500 ms). Per-model OUT 100 ms correlation mean/min and RMS ratio mean:

| Model | 100 ms corr mean / min | Best-lag corr mean / min | OUT RMS ratio mean |
|---|---:|---:|---:|
| Modal | 0.9997 / 0.9994 | 0.9997 / 0.9994 | 1.024 |
| Sympathetic Strings | 0.8752 / -0.1692 | 0.8875 / -0.0650 | 0.973 |
| String | 0.9909 / 0.9105 | 0.9958 / 0.9821 | 1.119 |
| FM Voice | 0.9707 / 0.5801 | 0.9846 / 0.7883 | 1.009 |
| Quantized Sympathetic Strings | 0.8274 / -0.3054 | 0.8619 / -0.2960 | 1.042 |

The coarser metric improves several beating-sensitive cases, but does not resolve the sympathetic-string outliers. Some best-lag searches hit the +/-500 ms boundary; those values are boundary-limited diagnostics, not measured onset offsets. The negative minimum correlations show that a single envelope-correlation score is not robust for all resonant/beating cases. Do not interpret the bounded best-lag metric as a pass/fail score. The next metric revision should explicitly flag boundary hits and compare per-case envelope trajectories and spectral evolution.

## Packed-24 precision experiment

The same workflow also completed the separate packed signed-24 Q3.21 versus float host audio comparison over 75 cases:
- Overall waveform SNR: 94.322 dB; RMS error: 3.5754e-6.
- No output samples exceeded full scale and no delay saturation was recorded.
- Maximum absolute delay value: 2.60025.
- Packed-24 host Rings Part size: 86,048 B versus 110,624 B for float (about 22.2% smaller).

This is encouraging host-side precision evidence only. It does not establish target firmware integration, real-time performance, or hardware sound quality. The earlier weak Sympathetic Strings case (note 84, dark profile, approximately 52.13 dB SNR) remains worth monitoring.

## Interpretation and limitations

This is a comparison of two sample rates using original floating-point Rings, not a hardware listening test. The aggregate waveform SNR is phase-sensitive and is not a perceptual pass/fail metric for resonant feedback systems. The calculated target rate remains unverified on physical FM-1 hardware.

The 46113594758 workflow completed successfully as a diagnostic workflow and uploaded its artifact. Its full target-link diagnostic is not a successful firmware link: POOL is 389,920 B against 368,640 B, exceeding the region by 21,280 B; ordinary RAM .data+.bss is 65,336 B of 73,728 B, leaving 8,392 B. The diagnostic log also reports unresolved `rings::q24_max_abs` and `rings::q24_saturation_count` references in the target String object. These need resolving before any packed-24 target link can be considered valid. The diagnostic step is deliberately non-fatal to the experiment workflow.

The Rings C ABI remains outside the live audio path. This experiment is not a playable firmware build.

## Follow-up

- Correct the coarse-envelope lag metric so boundary hits are explicitly marked as unresolved and cannot be mistaken for measured offsets.
- Inspect per-case envelope traces and resonant spectral evolution, especially Sympathetic Strings and Quantized Sympathetic Strings.
- Expand pitch coverage to 48/60/72/84/96 and the supported range, then broaden excitation and parameter profiles.
- Resolve the packed-24 target link symbols and POOL capacity without reducing the five models, eight-string bank, independent Rings instances or authentic decay.
- Measure the physical FM-1 codec rate.
- Keep all work experimental. Do not reduce the five models, eight-string bank, independent Rings instances or normal Clouds buffer to solve memory constraints.
