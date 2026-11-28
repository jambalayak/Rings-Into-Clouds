# Sample-rate characterization results (experimental)

Date: 2026-11-28. Workflow run [46104213643](https://github.com/jambalayak/Rings-Into-Clouds/actions/runs/46104213643), commit `4ace9d0224bc3f3191b10bad3efa14e224216495`.

## Scope
The corrected harness ran 75 cases: five resonator models, three pitches (48, 60, 84) and five profiles. Original-float DSP was rendered at 48 kHz and 44,117.647 Hz; the 48 kHz render was resampled to the target-rate timebase. Characterization only—not hardware testing or acceptance.

## 10 ms RMS envelope metrics

| Model | OUT corr mean / min | OUT RMS ratio mean | AUX corr mean / min | AUX RMS ratio mean |
|---|---:|---:|---:|---:|
| Modal | 0.9987 / 0.9948 | 1.022 | 0.9989 / 0.9955 | 1.015 |
| Sympathetic Strings | 0.9121 / 0.2508 | 0.976 | 0.9125 / 0.5177 | 0.978 |
| String | 0.9698 / 0.7924 | 1.118 | 0.9690 / 0.7747 | 1.115 |
| FM Voice | 0.9658 / 0.5739 | 1.009 | 0.9988 / 0.9917 | 0.999 |
| Quantized Sympathetic Strings | 0.9140 / 0.5195 | 1.041 | 0.8943 / 0.5077 | 1.029 |

Modal and FM Voice AUX envelopes are generally highly correlated. Sympathetic Strings and Quantized Sympathetic Strings vary more, including low correlations and notable level differences. String levels also vary (mean ratios around 1.115). These measurements warrant targeted investigation and listening; metrics alone are not perceptual acceptance.

T20 currently returns null for many cases where the post-peak envelope never crosses -20 dB during the segment. Window length and threshold logic need revision before T20 is relied upon.

## Waveform SNR
Aggregate waveform SNR is 1.076 dB. It is phase-sensitive and not a perceptual pass/fail measure for resonant feedback systems.

## Memory
The full diagnostic link remains 21,280 bytes over POOL capacity. It retained a reduced second-Rings probe, not a full independent eight-string instance; this is not a product-ready layout and the diagnostic does not run DSP.

## Next
- Expand pitch points and excitation/decay profiles.
- Improve T20 window and threshold-crossing logic.
- Investigate weak Sympathetic Strings and Quantized Sympathetic Strings cases.
- Measure actual FM-1 codec rate on hardware.
- Keep this experiment separate from product firmware; do not compromise models or decay to fit memory.
