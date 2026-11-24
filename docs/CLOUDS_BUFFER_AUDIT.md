# Clouds buffer and quality audit

Date: 2026-11-24

## Source baseline

Audited the pinned Mutable Instruments source:

- Repository: `pichenettes/eurorack`
- Revision: `08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4`
- Files: `clouds/dsp/granular_processor.h`, `clouds/dsp/granular_processor.cc`, `clouds/dsp/audio_buffer.h`
- FM-1 allocation reference: `stevexfer/FM1_Locus/firmware/apps/locus/locus_engine.cc`

This is a source audit only. Clouds has not yet been imported, compiled or measured in RINGS INTO CLOUDS.

## What the two external buffers actually contain

FM1_Locus declares:

- `clouds_large[118784]` in POOL;
- `clouds_small[65408]` in ordinary RAM.

The processor does not simply treat both allocations as one undifferentiated audio delay. In stereo mode, `GranularProcessor::Prepare()` partitions them as follows:

| Use | Bytes | Region |
|---|---:|---|
| Left channel recording buffer | 65,408 | first part of large POOL array |
| Right channel recording buffer | 65,408 | small ordinary-RAM array |
| DSP workspace | 53,376 | remainder of large POOL array |
| **Total** | **184,192** | **130,816 sample storage + 53,376 workspace** |

The 16-bit stereo mode uses 32,704 samples per channel after the interpolation-tail reservation. At 32 kHz this is approximately 1.022 seconds of recording per channel. This is a source-derived duration from the reference allocation, not a measured target result.

In mono mode, the large 118,784-byte array is used for the recording buffer and the 65,408-byte small array becomes DSP workspace. The exact partition is selected by `Prepare()`.

The processor object itself also contains fixed internal working arrays, including frame scratch, grain state, and two 256-sample tail buffers. Those are part of `sizeof(clouds::GranularProcessor)`, not part of the external 184,192-byte pair. The target compiler must measure the object size.

## Important quality-mode correction

Stock Clouds exposes two independent quality choices: channel count and low-fidelity mode.

- Full quality stereo: 32 kHz processing, 16-bit recording.
- Low-fidelity stereo: 16 kHz processing and 8-bit recording.
- Mono can be selected separately.

The source's `sample_rate()` returns 32,000 Hz normally and 16,000 Hz when low-fidelity is enabled. There is no stock 24 kHz quality setting.

**Changing the stock quality flag does not automatically reduce the externally reserved 118,784 + 65,408 bytes.** The memory arrays are still allocated at their caller-provided sizes. The 8-bit mode can store more samples in those same byte capacities (and therefore gives longer recording time), while also reducing resolution and processing bandwidth. It does not return RAM to the rest of the firmware.

A custom 24 kHz mode would require a deliberate resampler and rate-dependent DSP validation. It is not a one-line quality flag.

## Memory-saving options

1. **Keep stock 32 kHz / 16-bit stereo and full buffer capacities.** Best fidelity and reference behaviour, but requires solving the measured RAM/POOL fit without silently reducing buffers.
2. **Stock 16 kHz / 8-bit stereo quality.** Lower bandwidth and quantization quality; potentially lower DSP load and longer recording duration per fixed byte allocation. It does not reduce the external buffer reservation by itself.
3. **Custom shorter recording duration.** Reduce the two sample-storage partitions while preserving the 53,376-byte stereo workspace, processor algorithms, grain counts and sample rate. This is a real memory saving but intentionally shortens the maximum recording window. A 25% reduction of the 130,816-byte stereo sample storage would save 32,704 bytes and reduce the nominal per-channel window from about 1.022 s to about 0.766 s at 32 kHz. These are planning calculations; allocator alignment, tails and the actual implementation must be rechecked.
4. **Custom 24 kHz with proportionally shorter storage.** This could reduce sample-storage demand while preserving a chosen recording duration only if the exact number of samples is re-derived. It also requires new rate conversion and quality tests; it is not currently preferred over a clean 32 kHz baseline.

## Decision

Keep the 32 kHz / 16-bit stereo source behaviour as the fidelity reference. Do not switch to 16 kHz or 24 kHz just to make the first build fit. First obtain the lean linker map, measure the exact target object sizes and allocator workspace, and model a profile with explicit recording duration. If a reduced-duration profile is necessary, expose its recording time as a documented product trade-off rather than claiming full original buffer capacity.

## Validation still required

- Target compiler `sizeof(clouds::GranularProcessor)` and all Rings objects.
- Exact linker allocation in RAM and POOL for the chosen profile.
- Confirm that the target build retains at least 4 KiB RAM and 8 KiB POOL headroom.
- Verify all Clouds modes, freeze, stereo separation, recording duration, and reset/prepare transitions.
- Profile worst-case audio processing and sample-rate conversion.
- Test on Harbor only after a verified package exists; test physical codec timing on FM-1 hardware when available.
