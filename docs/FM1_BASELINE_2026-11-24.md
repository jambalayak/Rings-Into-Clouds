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


## Lean profile measurement and linker artifact

A later diagnostic-only build excluded Slicer and linked successfully in GitHub Actions run [45335987649](https://github.com/jambalayak/Rings-Into-Clouds/actions/runs/45335987649), commit `5945595e727664e3b44a6f9b7b22c71c365be72f`.

| Metric | Full profile (Run 62) | Lean profile (Run 64) |
|---|---:|---:|
| App image | 508,180 B | 474,708 B |
| RAM (.data + .bss) | 61,012 B | 56,036 B |
| RAM free | 12,716 B | 17,692 B |
| POOL | 145,720 B | 145,720 B |
| POOL free | 222,920 B | 222,920 B |

The Run 64 host regression step was cancelled when a newer documentation commit entered the branch. However, the workflow's `if: always()` diagnostic build ran and passed, and its map and section table were uploaded as artifact [14894735101](https://github.com/jambalayak/Rings-Into-Clouds/actions/runs/45335987649/artifacts/14894735101). This is not a tested firmware release.

The map confirms that the 72 KiB ordinary-RAM region contains 352 bytes of `.data`, 55,684 bytes of `.bss`, and a 3,072-byte CPU1 stack allocation. The combined RAM figure is 56,036 bytes. The POOL input section is one large allocation from the unity-built firmware object, so the map alone does not attribute its bytes to individual C objects.

The build now writes `build/felucca.symbols.txt` from the target ELF symbol table. Run 68's diagnostic artifact includes it; the `.pool` symbol sizes and addresses account for 145,711 of the 145,720 bytes, with 9 bytes of alignment.

## Exact Clouds buffer partition

See [CLOUDS_BUFFER_AUDIT.md](CLOUDS_BUFFER_AUDIT.md) for the pinned upstream source audit. In stereo mode, the 184,192-byte FM1_Locus pair comprises 130,816 bytes of recording storage (65,408 bytes per channel) plus 53,376 bytes of workspace carved from the large POOL array. The processor's stock low-fidelity mode is 16 kHz / 8-bit, not 24 kHz, and changing that flag does not shrink the caller-reserved arrays. The initial 32 kHz / 16-bit stereo reference remains the fidelity target.


## Run 68 diagnostic result

Run [45337236367](https://github.com/jambalayak/Rings-Into-Clouds/actions/runs/45337236367), commit `d21f9a5af7588ec64b99dc9f69da67ad7bfd0abf`:

- Target firmware compilation/link: passed.
- Host regression suite: failed. It still reports 720 engine-switch golden-hash differences and legacy UI/song/FX/editor/librarian failures. It also caught the directly introduced PHYS test gap: 10 factory presets but only 9 demo phrases. The MINIMALIST preset itself passes the PHYS stability and torture renders; the missing tenth demo phrase is being added to the test fixture.
- Lean Slicer-excluded firmware build: passed.
- Diagnostic artifact: [14895241257](https://github.com/jambalayak/Rings-Into-Clouds/actions/runs/45337236367/artifacts/14895241257), containing `felucca.map`, `felucca.sections.txt` and `felucca.symbols.txt`.
- Tested firmware artifact: skipped because the host regression suite failed. This is not a Harbor-ready package.


## Other reserved memory

The lean linker map's `.ram_text` section is 3,124 bytes in a 24 KiB region, leaving 21,452 bytes of potential slack. This is not part of the ordinary RAM + POOL figures above and is currently reserved for flash-safe code. A separate, guarded `.ram_pool` section may be considered for small DSP state or resampler tables, but it cannot replace the contiguous Clouds recording buffers and does not resolve the overall Rings + Clouds fit. The 8 KiB RAM-run debug gap and 32 KiB user/supervisor stack region remain reserved.
