# FM-1 baseline build measurements — 2026-11-24

## Build identity

- Repository: `jambalayak/Rings-Into-Clouds`
- Branch: `rings-into-clouds-development`
- Source commit: `9b3569507dd5595a4da4656b3bb5c37f5e494036`
- GitHub Actions run: [45333118401](https://github.com/jambalayak/Rings-Into-Clouds/actions/runs/45333118401)
- Build step: `./build.sh` (default full development configuration, including Slicer)
- Target toolchain and pinned AC79 SDK installation: passed
- FM-1 target compilation/link: passed
- Host regression suite: failed; see the CI log. Therefore the later lean build and artifact upload did not run. This is a measurement build, not a releasable/tested firmware package.

## Measured linker totals

The successful target build reported:

| Metric | Used | Region | Free |
|---|---:|---:|---:|
| App image | 508,180 B | — | — |
| RAM (.data + .bss) | 61,012 B | 73,728 B | 12,716 B |
| POOL | 145,720 B | 368,640 B | 222,920 B |

The build gate requires at least 4 KiB free in ordinary RAM and 8 KiB free in POOL. The measured baseline passes those two static headroom checks. The linker map and section table were generated in CI, but the workflow did not upload them because the host regression step failed.

These values are from the default full build at the commit above. They are not yet measurements of the lean Slicer-excluded profile or of a Rings/Clouds build.

## Audio-rate derivation

`firmware/src/audio.c` defines `DAC_TICKS = 544` timer ticks per I2S frame and documents the timer clock as 24 MHz. The derived frame rate is:

`24,000,000 / 544 = 44,117.6470588 frames/second`

This is the base pipeline rate used for the integration design. Before DSP integration, verify the codec clock configuration against the board-level BSP source and confirm the measured physical rate on hardware. Do not use FM1_Locus's 48,076.9 Hz clock or copy its 3:2 resampler unchanged.

## Clouds memory implications

The FM1_Locus reference allocation recorded in the integration gate is 118,784 bytes in POOL plus 65,408 bytes in ordinary .bss (184,192 bytes total). Compared with this measured baseline:

- Adding the 65,408-byte ordinary-RAM allocation unchanged would exceed the current 12,716-byte free RAM by 52,692 bytes.
- Adding the 118,784-byte POOL allocation would leave 104,136 bytes of POOL before Rings state, object state, resampler histories, FIFOs and routing buffers.
- Moving the 65,408-byte allocation out of ordinary RAM and into POOL is a candidate to investigate, not an approved implementation. If both reference arrays were placed in POOL, they would consume 184,192 bytes and leave 38,728 bytes before Rings and all new support state; the required 8 KiB POOL reserve must still be preserved.

A lower Clouds processing rate does not automatically shrink either array. Only reducing the number of stored samples (and therefore recording duration or another buffer property) changes storage. A 32-to-24 kHz change would represent a 25% sample-count reduction only for buffers deliberately scaled to preserve the same time duration. Do not change the rate or buffer sizes until the exact upstream array roles, duration, sound-quality consequences and measured combined memory profile are documented.

## Regression status and next gate

The target compilation succeeded, but host regression tests failed, so the workflow correctly skipped the lean build and artifact upload. Failures include engine-switch audio golden hashes and existing UI, song, FX, preset and editor/librarian checks. The current evidence does not identify a Clouds/Rings DSP defect; neither original DSP has been integrated.

Next:
1. Preserve this measured default-build baseline.
2. Inspect the generated linker map/section contributions and build the Slicer-excluded profile once the regression gate is understood.
3. Confirm the codec clock from BSP source and hardware.
4. Inspect the exact upstream Clouds buffer declarations and determine whether a safe pool placement or explicit quality profile is possible.
5. Keep 32 kHz as the reference until a controlled lower-rate comparison is available.
