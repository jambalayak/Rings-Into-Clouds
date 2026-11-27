# Rings performance screen

## User-approved interaction

When either independent Rings instance is the selected sound, the performance view is a dedicated resonator panel inspired by the supplied reference. It presents five always-visible controls:

- FREQUENCY
- STRUCTURE
- BRIGHTNESS
- DAMPING
- POSITION

The screen should retain the reference's hierarchy: two larger controls across the upper row (Frequency and Structure), three smaller controls across the lower row (Brightness, Damping and Position). Each control has a clear pointer/arc and readable label. The selected/active control is visually highlighted, and its value is shown without obscuring the panel.

The four physical K1–K4 encoders edit four parameters at a time. SELECT cycles the five-parameter assignment so every on-screen parameter can be brought into the active encoder set. Selection and parameter values are independent for Rings 1 and Rings 2. The physical controls must update the actual DSP state, not just a UI-only value.

## DSP parameter mapping

The pinned Mutable Instruments Rings `Patch` contains `structure`, `brightness`, `damping` and `position`. The fifth control, Frequency, is pitch/frequency input: `Part::Process` consumes `PerformanceState.note` (then combines it with tonic and FM) to derive the resonator frequency. For the FM-1 performance screen, Frequency should therefore act as a semitone offset on the incoming note, preserving the sequencer/MIDI note as the baseline; its final range and scaling must be calibrated against FM-1 pitch handling. Do not fake Frequency by changing Structure or another Patch field.

The screen must preserve the existing Rings model selection and each instance's independent Patch and PerformanceState. It must not change the approved five-model set or the full eight-string sound design.

## Integration gates

The current C ABI in `firmware/src/rings_clouds_abi.h` exposes Rings processing entry points, but the existing boot anchor and target compile diagnostics do not prove the processors are connected to the audio path. Before enabling this screen as a live performance view:

1. Complete and test the audio routing for both independent Rings instances.
2. Establish the FM-1-safe representation and persistence of both Patch objects and their Frequency/note offsets.
3. Add UI input handling with correct track/instance selection and independent values.
4. Draw the panel using the existing 240x240 UI drawing primitives and normal invalidation/redraw path.
5. Add host UI/input tests and target build/memory checks.
6. Measure real-time CPU headroom with both Rings instances, Clouds and Marbles active.

Until these gates pass, the screen is a design specification, not a claim of working live DSP controls.
