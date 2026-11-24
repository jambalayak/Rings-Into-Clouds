# Pinned Mutable Instruments DSP source plan

This is a source-only pin. No Rings or Clouds objects are instantiated by the firmware yet.

| Component | Repository | Pinned revision | License |
|---|---|---|---|
| Rings DSP and resources | https://github.com/pichenettes/eurorack | 08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4 | MIT, Emilie Gillet |
| Clouds DSP and resources | https://github.com/pichenettes/eurorack | 08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4 | MIT, Emilie Gillet |
| stmlib dependency | https://github.com/pichenettes/stmlib | d18def816c51d1da0c108236928b2bbd25c17481 | MIT, Emilie Gillet |

The upstream eurorack repository contains its own stmlib gitlink. The explicit top-level stmlib pin is the revision selected for this FM-1 port; compile include paths must resolve `stmlib/...` from `third_party/stmlib`, not the nested upstream gitlink.

## FM-1 integration facts

- Base codec/timer rate: 24 MHz / 544 DAC ticks = 44,117.647 Hz. Rings must be compiled with this rate, not 48 kHz or the 48,076.9 Hz rate used by FM1_Locus.
- Clouds' nominal processing rate remains 32 kHz. Its 3:2 resampler must be redesigned for this codec ratio; do not copy the Locus ratio without validation.
- Rings' five exposed models are Modal, Sympathetic Strings, String, FM Voice, and Quantized Sympathetic Strings. Do not expose String-and-Reverb.
- The String-and-Reverb model's external 65,536-byte delay buffer is excluded. Upstream `Part::Init()` still initializes a Reverb member, so a reviewed null-buffer guard or removal of that unused path is required before instantiation. Never pass NULL to unmodified upstream `Part::Init()`.
- The current memory estimate for two full Rings Parts plus Clouds is over budget. Source import does not imply this configuration fits; the compact delay-line and reduced Clouds-buffer options remain prototypes only.
- Clouds `Prepare()` must run in the main loop, not in the audio interrupt. Its `Process()` call must be scheduled with bounded work and measured worst-case CPU time.
- No audio routing, DSP state, or memory allocations are changed by this source pin.

## Next source-only compile phase

Compile the upstream `.cc` translation units with the target AC79 compiler and the minimal freestanding C++ headers/runtime, without constructing any DSP object or touching the audio path. Record compiler flags, undefined symbols, section sizes and the exact source revision. Only after that succeeds should a standalone Rings harness and standalone Clouds harness be considered.

## Local patches to review before use

1. Replace Rings' nominal 48 kHz constant with 24 MHz / 544.
2. Guard the optional Rings reverb initialization if the external reverb buffer is absent, or remove the unused reverb member/model path.
3. Remove or adapt the Clouds STM32 debug-pin include for this target.
4. Apply the reviewed Clouds window-boundary correction and stmlib FFT pointer arithmetic correction if the sanitizer evidence still applies to this pinned revision.
5. Add any view accessors only when the FM-1 UI actually needs them; keep them out of the audio core otherwise.

Each local source patch must be listed here with a reason and test evidence. Do not import the Locus engine scheduler, its two-core timing, or its resampler wholesale.
