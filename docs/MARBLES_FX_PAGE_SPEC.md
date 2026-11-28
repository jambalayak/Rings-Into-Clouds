# Marbles FX page — FM-1 interface and control contract

Status: interface specification only. This document does not claim that the Marbles random generator, screen page, or hardware controls have been implemented.

## Intent

Add a dedicated **MARBLES** page in the FX family for the Rings track. It should read as a compact instrument panel inspired by the supplied Mutable Instruments Marbles reference: pale panel, dark circular controls, restrained green/cyan/yellow/pink status accents, dotted signal relationships, and clear clock/output indicators. Reinterpret the visual language for the FM-1 display; do not reproduce the source panel artwork or its exact layout.

Marbles remains a sequencing/modulation source for the single Rings instrument. It is not an audio track, voice engine, or independent sound generator. Clouds remains a separate optional/bypassable Rings processor.

## FM-1 screen adaptation

The reference is a full Eurorack panel; the FM-1 display is much smaller. Preserve its visual hierarchy rather than shrinking every jack and label:

- Header: `MARBLES`, with a small RUN / HOLD state.
- Main area: four large parameter cards with circular knob arcs and readable numeric/value labels.
- Lower strip: clock pulse, random-output activity, and the current sequence position.
- Signal graphic: a compact dotted path from clock/random generation into Rings modulation; no tiny decorative patch sockets.
- Use the original reference's high-contrast dark rings and white knob pointers, with green as active, cyan as clock, yellow as probability/variation, and magenta as repeat/Deja Vu. Maintain legibility in the existing theme and monochrome/low-colour modes.

## Control pages and FM-1 knobs

The page has two banks so all eight controls are directly editable with the four FM-1 knobs. The four knob positions must be stable across banks.

### CLOCK bank

| FM-1 knob | Control | Function |
|---|---|---|
| K1 | RATE | Internal clock division/multiplication; external clock remains selectable |
| K2 | JITTER | Timing variation, from straight clock to humanised/random timing |
| K3 | LENGTH | Random sequence memory length |
| K4 | STEPS | Number of active steps in the current sequence |

### RANDOM bank

| FM-1 knob | Control | Function |
|---|---|---|
| K1 | DEJA VU | Probability/amount of repeating remembered random values |
| K2 | SPREAD | Width of the random value distribution |
| K3 | BIAS | Distribution tilt / centre bias |
| K4 | t | Probability balance for the timing/gate stream |

A bank-select action switches CLOCK / RANDOM without changing values. The display must show the current value and a clear active-bank indicator. Turning a knob changes its parameter immediately; pressing/selecting must not be required to enter a hidden edit mode.

## Signal behaviour

- RATE drives Marbles' internal clock only when internal clock is selected; external clock pulses take precedence when external sync is active.
- JITTER affects generated trigger timing, bounded so events cannot cross into the next step or become negative-time events.
- LENGTH bounds the remembered random sequence; DEJA VU controls reuse of that history.
- STEPS bounds the active sequence length and must not change the stored Rings pattern length.
- SPREAD and BIAS shape the generated random control values, not Rings' audio output directly.
- t shapes the generated gate/trigger stream. It must not randomly mute the audio output or bypass Rings.
- Marbles outputs are control/sequencing signals. They feed Rings' trigger/strum and modulation destinations, never a third audio part.
- Clouds processing remains independently bypassable and must not be required for Marbles to operate.

## Output and routing model

Expose the useful Marbles outputs in a compact output monitor:

- t1 / t2 / t3: three trigger streams; each can be assigned to Rings' trigger/strum input or left unassigned.
- X / X1 / X2 / X3: random control values; each can be assigned to a supported Rings parameter/modulation destination.
- Keep the existing requirement that Marbles T1 and T2 are independently selectable as triggers for Rings strum/trigger. Do not silently hard-wire both to one destination.
- Output routing should be configured on a separate ROUTE subpage, not squeezed into the eight performance controls.
- Output LEDs/pips show pulse/value activity, not decorative animation.

## Functional and persistence requirements

1. Each visible control has a real stored value, range, default, and audible/control-rate consumer. No decorative knobs.
2. Physical K1..K4 edits update the displayed control and its actual Marbles DSP behaviour in the same interaction.
3. Values survive page changes, project save/load, and power cycle.
4. Project/FUN1..FUN10 binary layouts and checksums remain unchanged. Any new state must use an explicitly versioned extension or a compatibility-safe sidecar; never repurpose retired serialized parameter IDs without an audit.
5. Motion recording/playback and MIDI learn must either support the new controls deliberately or report them as unavailable; never write an invalid parameter ID.
6. Knob pickup/acceleration, value formatting, motion capture, undo, and preset defaults must be tested.
7. If the Marbles generator is disabled, the page must show OFF and output indicators must remain inactive; the Rings engine and Clouds bypass continue normally.

## Implementation order

1. Add the page and bank navigation to the FX family, using the existing four-card UI and input dispatch.
2. Define a versioned Marbles state object and explicit default/reset/save/load policy.
3. Implement deterministic host-testable clock, random-value, sequence-memory, Deja Vu, jitter, and output-routing logic.
4. Connect t1/t2/t3 to Rings trigger/strum and X outputs to supported Rings modulation destinations.
5. Add motion/MIDI integration and regression tests.
6. Validate target RAM/CPU/flash costs before enabling the feature by default.

## Acceptance tests

- Every one of the eight knobs changes its intended state and DSP result, including both bank transitions.
- RATE follows internal/external clock selection; JITTER remains bounded.
- LENGTH and DEJA VU repeat the intended history; STEPS changes the active random sequence length without altering the Rings pattern.
- SPREAD, BIAS, and t alter the generated distributions/gates in the expected direction.
- t1 and t2 can be independently assigned to Rings strum/trigger.
- Save/reload, old project import, motion playback, and MIDI routing do not corrupt existing projects or map retired tracks into the live Rings/Drums pair.
- Audio output remains Rings + drums only; Marbles adds no independent audio voice.
