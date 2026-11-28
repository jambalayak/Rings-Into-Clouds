# Rings source-fidelity audit

Date: 2026-11-28

## Decision

**Do not adopt packed signed-24 delay storage in the product firmware yet.** Keep it isolated to `rings-delay-packed24-exp`. The experiment is useful evidence that float DSP arithmetic can run over a smaller delay store, but it has not established transparent sound equivalence for all five retained models, and there is no hardware listening test.

The product reference remains the pinned upstream Mutable Instruments Rings implementation, revision `08460a69a7e1f7a81c5a2abcc7189c9a6b7208d`, with the approved removal of String-and-Reverb only. The five retained models remain Modal, Sympathetic Strings, String, FM Voice, and Quantized Sympathetic Strings.

## What the packed-24 experiment actually changes

The test overlay replaces both `StringDelayLine` and `StiffnessDelayLine` in `rings/dsp/string.h` with `Q24DelayLine`. The delay samples are stored as three-byte signed values in Q3.21 format (range [-4, 4)); each write quantizes the floating-point sample. Reads decode back to float, and the surrounding Rings DSP/interpolation arithmetic remains floating point.

This is not a fixed-point rewrite of the resonator algorithms. It is a lossy reduction in the precision of the feedback delay memories. The Q3.21 step size is 1/2,097,152. The tested signals did not hit the representable limit, so the measured differences are quantization/feedback effects rather than clipping.

The comparison uses the same five-model patched Part source for the float reference and packed-24 variant. It changes the Rings sample-rate constant from upstream's 48 kHz to the FM-1 target rate of 24 MHz / 544 = 44,117.6470588 Hz for both variants. Thus it isolates the delay-storage change at the target sample rate; it is not a direct comparison to a physical Eurorack module.

## Evidence from the 75-case host comparison

The test matrix covers five retained models, MIDI notes 36/60/84, and five profiles (neutral, dark, bright, long decay, loud external).

- Overall packed-24 SNR against the float reference: **94.3221 dB**.
- Overall RMS error: **3.5754e-6**.
- No delay saturation was observed.
- The weakest reported model-specific case is **Sympathetic Strings, note 84, dark profile: approximately 52.13 dB SNR**.
- Host Part storage falls from 110,624 bytes (float) to 86,048 bytes (packed-24), about 22.2%.

The overall score is encouraging but hides the weaker Sympathetic Strings case. That model's coupled resonant feedback can make small per-write errors accumulate differently from a simple one-shot sample comparison. A good aggregate score is not enough to establish that the decay, beating, tuning, and sympathetic response remain indistinguishable.

## Fidelity risks and required follow-up

1. Keep the packed-24 implementation experimental. Do not use it in a release build or claim it sounds identical to upstream.
2. Expand the comparison around Sympathetic Strings, especially high notes and dark/long-decay settings; include low-level tails, repeated excitation, polyphony changes, and long renders.
3. Add delay-line conformance tests against the pinned upstream `stmlib::DelayLine<float, N>` for reset, wraparound, integer/fractional reads, Hermite reads, allpass, and write-before-read ordering.
4. Compare per-model envelopes, decay slopes, spectral peaks, tuning drift, stereo OUT/AUX balance, and tail noise, not only aggregate SNR.
5. Audition level-matched float and packed-24 renders on headphones/speakers. No such listening evidence is currently recorded.
6. If any audible or material musical difference remains, reject packed-24 and preserve float delay storage. Do not reduce string count, model count, decay, or buffer lengths to make the memory map fit.
7. Keep both independent Rings instances and the normal Clouds buffer requirement intact. Memory feasibility must be solved by verified memory placement/hardware capability or a separately approved product-level decision, not by quietly changing the sound.

## Important implementation boundary

The current C ABI contains construction, initialization, and processing entry points, but the firmware boot path only calls the link-retention anchor. The audio engine does not yet construct, initialize, or process Rings. Consequently these host renders validate only the isolated DSP comparison; they do not prove live FM-1 integration, real-time deadline compliance, or hardware sound.

## Reproducibility

- Source pin: `pichenettes/eurorack@08460a69a7e1f7a81c5a2abcc7189c9a6b7208d`.
- Experiment script: `tools/rings_delay_packed24_test.py`.
- Delay store: `tools/rings_delay_test/q24_delay_line.h`.
- Workflow run: https://github.com/jambalayak/Rings-Into-Clouds/actions/runs/46087345419
- Experiment branch: `rings-delay-packed24-exp`.

This audit records a conservative engineering decision, not a claim that the port is complete or playable.
