# MIDI implementation audit

## Status

Source-level audit of the current Felucca-derived base. This records what already exists and what RINGS INTO CLOUDS still needs. It is not a claim of physical-device validation.

## Existing input paths

### TRS MIDI input

`firmware/src/midi_uart.c` implements TRS MIDI IN through UART1 RX:
- FM-1 TRS input is documented as PH8 / UART1 RX at 31,250 baud.
- DMA writes to a 128-byte ring; TIMER5 polls and parses it.
- `FELUCCA_UART=0` disables this input.
- MIDI channel messages are enqueued alongside USB input.
- MIDI Timing Clock (F8), Start (FA), Continue (FB) and Stop (FC) are timestamped/enqueued.
- Realtime bytes do not disturb channel running status.
- Overflow is counted and flagged.

### Clock follower

`firmware/src/midi_clock.c` already provides a clock-follower foundation:
- Timing Clock is interpreted at 24 pulses per quarter note.
- Start resets sequence position and starts playback.
- Continue preserves the rendered sequence position.
- Stop stops the sequencer.
- Six-pulse intervals estimate tempo; accepted interval range is 62–375 ms, corresponding to a broad practical tempo range.
- Sequencer, arpeggiator, click/metronome and tempo-synchronised LFO phase are adjusted to the measured external tempo.
- Clock interpolation advances musical position between incoming pulses without moving beyond the next unreceived pulse.
- The audio engine's tempo-aware functions use the external measured tempo while external clock is active.

The USB-MIDI receive parser and TRS parser feed the shared MIDI input queue. The TRS source comments explicitly say clock/transport retain timestamps and source.

## What is not established by this source audit

- No outgoing MIDI Timing Clock (F8) implementation was found in the inspected `midi_clock.c` or `midi_uart.c`.
- No TRS MIDI OUT implementation was found in the inspected UART input driver. The current TRS path is explicitly RX.
- USB-MIDI OUT capability must be checked in the USB device/BSP descriptors and endpoint implementation; the presence of USB-MIDI input is not proof of host-visible MIDI output.
- No physical FM-1 loopback or external-device master test has been run.
- Song Position Pointer (F2), clock-loss policy and duplicate USB/TRS clock-source arbitration require additional verification against the complete queue/transport implementation.

Therefore, the base currently gives us meaningful **USB and TRS MIDI slave/input** functionality. **USB MIDI master/output is supported by the existing USB transport and can be implemented in firmware; TRS MIDI master/output remains unverified and is not supported by the inspected RX-only UART path.** Do not advertise TRS clock output until connector wiring and a TX route are proven.

## RINGS INTO CLOUDS requirements

1. Keep the existing input clock path working for both supported USB-MIDI and TRS MIDI IN.
2. Add explicit source selection (internal / USB / TRS / automatic only if the source can be identified reliably).
3. Prevent double-clocking when the same master reaches both input paths.
4. Add robust clock-loss detection and define whether playback stops, holds, or falls back to internal tempo. The chosen behaviour must be consistent across sequencer, arp, LFO and tempo-aware effects.
5. Evaluate F2 Song Position Pointer and Continue semantics.
6. Implement USB-MIDI OUT clock/transport using the existing audio-ISR producer / TIMER5 USB endpoint consumer queue. Keep the queue bounded and define what happens on disconnect/full queue.
7. Verify the FM-1 TRS connector pinout and any UART TX route before considering TRS master output; current UART1 MIDI path is RX-only.
8. Implement 24 PPQN clock plus Start/Continue/Stop from internal transport over USB, with bounded jitter and no input/output feedback loop.
9. Test with at least one external hardware clock master and one external USB MIDI slave, then test simultaneous USB and TRS input cases.

## Acceptance tests

- USB-MIDI external clock drives sequencer, arp, tempo-synced LFO and tempo-aware effects.
- TRS MIDI external clock does the same.
- Start, Continue and Stop produce deterministic transport and no stuck notes.
- Tempo changes preserve phase without jumps.
- Missing clock follows the documented loss policy.
- Two simultaneous clock sources cannot advance the engine twice.
- If MIDI OUT is supported, the FM-1 sends 24 PPQN clock and correct transport messages to an external device with measured jitter.
- No MIDI feedback loop occurs when devices are connected bidirectionally.

## Next source inspections

- Trace USB-MIDI endpoint descriptors and transmit functions in the BSP.
- Trace MIDI queue consumer and clock-source identity in `timer5.c`, `seq.c`, and the MIDI control path.
- Trace UART pin mux / connector wiring in the FM-1 BSP before considering any TRS OUT use.
- Add host tests for source arbitration, clock loss, Start/Continue/Stop and master clock scheduling before target integration.
