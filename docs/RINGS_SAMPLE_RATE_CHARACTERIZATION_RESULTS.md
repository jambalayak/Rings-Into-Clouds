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

The coarser metric improves several beating-sensitive cases, but does not resolve the sympathetic-string outliers. Some best-lag searches hit the +/-500 ms boundary; those values are boundary-limited diagnostics, not measured onset offsets. The negative minimum correlations show that a single envelope-correlation score is not robust for all resonant/beating cases. Do not interpret the bounded best-lag metric as a pass/fail score. The corrected five-second follow-up below supersedes the old boundary counts; the original 500 ms results are retained here as historical results.

## Packed-24 precision experiment

The same workflow also completed the separate packed signed-24 Q3.21 versus float host audio comparison over 75 cases:
- Overall waveform SNR: 94.322 dB; RMS error: 3.5754e-6.
- No output samples exceeded full scale and no delay saturation was recorded.
- Maximum absolute delay value: 2.60025.
- Packed-24 host Rings Part size: 86,048 B versus 110,624 B for float (about 22.2% smaller).

This is encouraging host-side precision evidence only. It does not establish target firmware integration, real-time performance, or hardware sound quality. The earlier weak Sympathetic Strings case (note 84, dark profile, approximately 52.13 dB SNR) remains worth monitoring.

## Interpretation and limitations

This is a comparison of two sample rates using original floating-point Rings, not a hardware listening test. The aggregate waveform SNR is phase-sensitive and is not a perceptual pass/fail metric for resonant feedback systems. The calculated target rate remains unverified on physical FM-1 hardware.

The 46113594758 run was an earlier diagnostic. The later corrected target link in workflow 46121592760 resolves the q24 counter symbols, but remains a failed firmware link diagnostic: POOL is 389,920 B against 368,640 B, exceeding the region by 21,280 B; ordinary RAM .data+.bss is 65,348 B of 73,728 B, leaving 8,380 B. The workflow is successful only because the diagnostic is intentionally non-fatal to the audio experiment.

The Rings C ABI remains outside the live audio path. This experiment is not a playable firmware build.

## Follow-up

- Correct the coarse-envelope lag metric so boundary hits are explicitly marked as unresolved and cannot be mistaken for measured offsets.
- Inspect per-case envelope traces and resonant spectral evolution, especially Sympathetic Strings and Quantized Sympathetic Strings.
- Expand pitch coverage to 48/60/72/84/96 and the supported range, then broaden excitation and parameter profiles.
- Resolve the packed-24 target link symbols and POOL capacity without reducing the five models, eight-string bank, independent Rings instances or authentic decay.
- Measure the physical FM-1 codec rate.
- Keep all work experimental. Do not reduce the five models, eight-string bank, independent Rings instances or normal Clouds buffer to solve memory constraints.


## Corrected five-second envelope-lag follow-up

Workflow [46121592760](https://github.com/jambalayak/Rings-Into-Clouds/actions/runs/46121592760), commit `ed64c8bb7840d1c046d5cb9e0b35809e3faa9816`, corrected the lag-window calculation. The previous nominal five-second setting was unintentionally capped at approximately 1.1 seconds by a one-tenth-capture limit. The corrected implementation permits up to five seconds, while limiting the search to half of each coarse envelope capture. Short captures therefore have a smaller actual search window.

Across 75 cases and two channels (150 channel comparisons), the 100 ms RMS-envelope correlation results are:

| Model | OUT raw mean | OUT best-lag mean | AUX raw mean | AUX best-lag mean |
|---|---:|---:|---:|---:|
| Modal | 0.9997 | 0.9997 | 0.9997 | 0.9998 |
| Sympathetic Strings | 0.8752 | 0.9223 | 0.8922 | 0.9208 |
| String | 0.9909 | 0.9966 | 0.9911 | 0.9967 |
| FM Voice | 0.9707 | 0.9957 | 0.9998 | 0.9998 |
| Quantized Sympathetic Strings | 0.8274 | 0.9509 | 0.8384 | 0.9431 |
| **All cases** | **0.9328** | **0.9730** | **0.9442** | **0.9721** |

Three of the 75 AUX comparisons hit their available search boundary; no OUT comparisons did. The maximum search is approximately five seconds only for sufficiently long captures. These are best-offset correlations, not proof that the resonators have identical onset timing or sound. Large best offsets remain visible: the Quantized Sympathetic Strings note-84 long-decay case selected -1.700 s on OUT and -4.299 s on AUX. Its raw correlations were 0.9121 and 0.9148, improving to 0.9796 and 0.9466 after offset selection. That large channel-dependent offset should be investigated rather than normalized away.

The corrected search improves the aggregate best-lag metric, but does not resolve the underlying model-specific rate sensitivity. Sympathetic Strings and Quantized Sympathetic Strings remain the weakest models in the unshifted envelope comparison. A per-case trajectory and spectral-evolution review is still required; a best-lag score must not be used as a pass/fail criterion.

The separate packed signed-24 Q3.21 versus float comparison remains unchanged: 75 cases, 94.322 dB overall waveform SNR, 3.5754e-6 RMS error, zero delay saturation, and maximum absolute delay 2.60025. This is host-side precision evidence at the calculated target rate only.

The target-link diagnostic in the same workflow reports image size 546,756 B, ordinary RAM .data+.bss 65,348 / 73,728 B (8,380 B free), and POOL 389,920 / 368,640 B (21,280 B overflow). Its Rings 2 sizing object remains a reduced two-string proxy, not the required full eight-string independent Rings instance. This is not a playable build and does not establish that the approved two-Rings-plus-Clouds configuration fits.
