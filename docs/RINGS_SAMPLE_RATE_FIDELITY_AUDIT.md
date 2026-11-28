# Rings sample-rate fidelity audit

Date: 2026-11-28

## Decision

The FM-1 port must run at the measured codec rate, 24 MHz / 544 = 44,117.6470588 Hz, unless the actual hardware audio clock is independently verified otherwise. Do not hard-code 48 kHz into the FM-1 audio path merely to match the original Eurorack firmware.

The pinned upstream source defines `rings::kSampleRate = 48000.0f` and derives `a3 = 440.0f / kSampleRate`. The FM-1 overlay currently substitutes 44,117.6470588 Hz. The packed-24 versus float comparison applies that same FM-1 rate to both variants. It therefore isolates delay-memory quantization at the target rate; it does **not** compare the FM-1 port against the original module's 48 kHz behaviour.

## Rate-sensitive source paths confirmed

- `rings/dsp/dsp.h`: defines `kSampleRate`, derives `a3`, and sets `kMaxBlockSize = 24`.
- `rings/dsp/part.cc`: uses `kSampleRate` in per-voice DC-blocker initialization, note-filter timing, and the sympathetic-string LFO phase increment (`kMaxBlockSize / kSampleRate`).
- The resonator/string DSP receives frequencies and processes discrete-time feedback delays. Changing the processing rate changes the relationship between delay samples and seconds; all frequency, damping, dispersion and interpolation behaviour must be evaluated at the actual target rate.

This is expected for a sample-rate port: coefficients derived from the sample rate should be recalculated, not left at their 48 kHz values. It does not prove that every model is perceptually identical to the 48 kHz module.

## Required validation before claiming Eurorack-equivalent behaviour

1. Render the pinned five-model float reference at 48 kHz and the same uncompressed source at 44,117.647 Hz.
2. Compare both after high-quality sample-rate conversion to a common timebase. Do not compare raw sample indices across different rates.
3. For every retained model (Modal, Sympathetic Strings, String, FM Voice, Quantized Sympathetic Strings), compare:
   - resonant peak frequencies and tuning error in cents;
   - decay envelopes and T20/T30 decay times;
   - spectral peak spacing, inharmonicity and beating;
   - attack/trigger latency and repeated-strum response;
   - stereo OUT/AUX balance and phase relationship;
   - long-tail noise and low-level behaviour.
4. Cover notes 36, 48, 60, 72, 84 and 96, plus the full supported pitch range where stable.
5. Cover neutral, dark, bright, high-damping/long-decay, low-level excitation, loud excitation, and repeated excitation. Test each model at its intended polyphony, including the maximum supported four voices per Part.
6. Confirm the target clock on actual FM-1 hardware. The 24 MHz / 544 value is the current firmware clock calculation, not a substitute for measuring the hardware output rate.
7. Only after the uncompressed 44.117 kHz port passes should packed-24 be compared against that target-rate float reference. Keep the weak Sympathetic Strings high-note/dark case under specific scrutiny.

## Current evidence boundary

- The original source pin is `pichenettes/eurorack@08460a69a7e1f7a81c5a2abcc7189c9a6b7208d`.
- The current 75-case float-versus-packed-24 test uses the target sample rate for both variants.
- Its aggregate 94.32 dB SNR and weakest Sympathetic Strings case (~52.13 dB) describe only that same-rate memory-precision comparison.
- No 48 kHz versus 44.117 kHz common-timebase comparison, hardware clock measurement, hardware listening test, or live FM-1 audio integration is currently recorded.

## Non-negotiable sound constraints

Do not reduce the five retained models, eight-string resonator bank, independent Rings A/B state, normal resonator decay, or Clouds' normal buffer size to make the memory map fit. Do not use packed-24 in product firmware until it passes model-specific audio comparison and listening. If the target cannot fit the approved sound configuration, investigate memory placement or hardware capability and report the limitation rather than changing the instrument's sound.
