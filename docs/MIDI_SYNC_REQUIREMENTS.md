# MIDI clock and transport synchronisation

## Product requirement

RINGS INTO CLOUDS must synchronise its sequencer, arpeggiator, tempo-based modulation and tempo-aware effects with external hardware over MIDI. MIDI sync is a core instrument requirement, not a later optional extra.

It must be possible to use the FM-1 as either:
- a **MIDI clock follower**, synchronised to an external drum machine, sequencer, groovebox, keyboard or DAW; or
- a **MIDI clock master**, sending tempo and transport to connected hardware.

The intended connection paths are the FM-1's supported USB-MIDI and TRS MIDI interfaces. Actual input/output capability and routing must be confirmed against the FM-1 hardware and BSP before implementation claims are made.

## MIDI input / slave behaviour

Implement and verify:
- MIDI Timing Clock: F8, 24 pulses per quarter note.
- Start: FA.
- Continue: FB.
- Stop: FC.
- Correct transport start/continue/stop behaviour, including phase alignment and predictable restart.
- External tempo estimation that is stable under normal clock jitter and tempo changes.
- Clock-loss detection and a clear stopped/hold policy; never leave stuck notes, gates or feedback running after clock loss.
- Correct clock-source selection: internal, USB-MIDI input or TRS MIDI input, where the hardware exposes both.
- No accidental double-clocking when the same master reaches both input paths.
- MIDI real-time bytes must be handled promptly and must not corrupt running status or SysEx parsing.

Song Position Pointer (F2) support should be evaluated and added where compatible, so Continue can resume at the intended song position rather than always restarting at bar one. Define behaviour for devices that send Start without SPP.

## MIDI output / master behaviour

Implement and verify:
- MIDI Timing Clock at 24 pulses per quarter note, derived from the internal tempo with low jitter.
- Start, Continue and Stop messages aligned with the sequencer transport.
- Configurable output destination: USB-MIDI, TRS MIDI, or both if supported.
- A clear master/internal mode and protection against sending clock back into the selected external input and creating a feedback loop.
- Clock output that remains stable under UI activity, audio load and tempo changes.
- Defined behaviour when tempo changes during playback and when transport stops.

MIDI Thru/merge is a separate routing feature. Do not merge clock streams blindly; avoid duplicate clocks and feedback loops.

## What must follow the clock

External synchronisation must drive the whole time-based instrument consistently, not only the step sequencer:

- Main step sequencer and song/chain playback.
- Arpeggiator rates and note timing.
- Tempo-synchronised LFOs, envelopes and modulation where a tempo division is selected.
- Slicer/stutter timing and any clocked generative modules.
- Metronome and count-in behaviour where applicable.
- Tempo-synchronised delay, rhythmic effects and future Clouds/Beads clock divisions.
- Marbles-inspired clock, gate and random-event timing.

All clock divisions should use a shared phase/timebase or mathematically related accumulators. Avoid each module independently estimating tempo, which can cause drift.

## User controls and feedback

Provide a MIDI SYNC page in the global clock/system settings:
- Clock mode: INTERNAL / USB IN / MIDI IN / USB OUT / MIDI OUT / BOTH, limited to verified hardware capabilities.
- Transport source and output destination.
- Current source status: internal/external, receiving/lost.
- Measured external BPM and lock indication.
- Master BPM when internal clock is active.
- Start/Stop/Continue status.
- Optional clock-thru setting only after safe merge/routing behaviour is implemented.

The interface should clearly distinguish the selected clock source from MIDI note input channel routing. A connected keyboard sending notes must not silently become the clock master unless selected.

## Timing and implementation constraints

- Timestamp incoming realtime events as close to the UART/USB receive boundary as possible.
- Keep clock parsing and timestamp capture lightweight; do not run tempo estimation or graph changes inside the audio interrupt.
- Deliver clock/transport events to the audio/sequencer domain through bounded queues with overflow handling.
- Preserve event ordering and phase across audio blocks.
- Measure input pulse interval jitter, output pulse jitter, start latency, stop latency and drift over long runs.
- Test at slow and fast tempos, tempo ramps/changes, simultaneous MIDI note traffic and heavy DSP load.
- Never block audio rendering while waiting for MIDI.

## Existing foundation — source inspection

The inherited Felucca source already has a useful **external MIDI clock input foundation**:
- `firmware/src/midi_uart.c` recognises F8, FA, FB and FC real-time bytes and queues them.
- `firmware/src/seq.c` consumes real-time messages, calls the external clock pulse/transport handlers, and advances sequencer timing from the received clock.
- `core.h` / global settings expose clock source values for USB and TRS input; `seq.c` stops playback after clock loss rather than leaving the transport running.
- The event queue distinguishes MIDI input sources, allowing the selected source to be used.

This source inspection does **not** yet establish complete bidirectional MIDI sync. In particular, do not assume MIDI clock output, robust output routing, Song Position Pointer support, or sync of every new module is already implemented. Inspect the USB-MIDI and TRS transmit paths and test on actual FM-1 hardware before marking those requirements complete.

## Acceptance tests

1. Slave to an external device at several tempos; compare sequencer downbeats over at least ten minutes.
2. Verify Start, Continue and Stop, including restart after Stop.
3. Disconnect the master while running; verify clock-loss indication and safe note/gate release.
4. Change external tempo while running; verify no phase jumps or audible timing glitches beyond the documented policy.
5. Send MIDI notes and clock simultaneously; verify neither stream corrupts the other.
6. Compare USB and TRS input paths independently and test duplicate-source protection.
7. Master an external drum machine/DAW; verify 24 PPQN clock and transport alignment.
8. Test output jitter and drift under worst-case DSP, UI and MIDI note traffic.
9. Verify tempo divisions for sequencer, arpeggiator, LFOs, slicer, generative events and tempo-based effects stay phase-related.
10. Verify MIDI feedback loops and duplicate clock paths are prevented.

## Status

This is a product requirement and implementation specification. The inherited firmware has external clock-input foundations, but bidirectional, whole-instrument MIDI synchronisation has not yet been verified or implemented as a complete RINGS INTO CLOUDS feature.


## Verified base-firmware transport capabilities

Source audit against the repository's pinned Felucca-BSP submodule commit `9670b5d34082700d0a7413eb6264abe1756c0ece`:

- USB-MIDI is a bidirectional class-compliant interface. EP1 OUT feeds the USB input queue; EP1 IN is driven by a bounded 64-event output queue.
- The audio side can enqueue a four-byte USB-MIDI event through `midi_out_try(pkt)`; the TIMER5 USB poll drains queued events to EP1 IN. This gives the master-clock implementation a non-blocking transport path from the audio timing domain.
- TRS MIDI is UART1 RX on PH8 at 31,250 baud. The current driver explicitly documents and configures RX only; no TRS transmit path is established.
- The existing MIDI clock module implements external clock following and transport, but no internal-clock-to-USB-MIDI F8/FA/FB/FC scheduler was found.

### Master clock implementation design

1. Add an internal-clock pulse scheduler in the audio timing domain, using sample-count/fixed-point phase accumulation rather than TIMER5 wall-clock polling. Emit exactly 24 pulses per quarter note across the supported tempo range.
2. On transport Start, queue USB-MIDI FA before the first F8 pulse. On Continue, queue FB and resume phase without restarting the song. On Stop, queue FC and stop further F8 events.
3. Encode each event as a valid USB-MIDI event packet (cable 0, correct CIN, realtime status in the first MIDI byte).
4. Use the existing bounded output queue only. Never wait for USB endpoint readiness in the audio ISR. If disconnected or full, drop/record diagnostics according to a defined policy and keep the internal sequencer timing unaffected.
5. Avoid clock feedback: when external USB clock is selected as the active master, disable outgoing clock by default (or require an explicit thru mode with loop protection). Do not echo incoming F8/FA/FB/FC automatically.
6. Use the USB link counter to reset/reconcile output state after reconnect; do not replay a stale backlog of clock pulses.
7. TRS master output is a separate hardware investigation. It needs a verified TX-capable pin, mux, electrical interface and connector path. The current PH8 RX path is not enough evidence.

At 240 BPM, 24 PPQN produces 96 clock events per second, well below the 2 kHz USB service cadence. This rate comparison is not a jitter measurement; timing accuracy must still be tested with a MIDI analyser or receiving hardware.

## Master/slave status labels

Until implementation and hardware tests pass:
- USB MIDI IN: existing base capability.
- TRS MIDI IN: existing base capability.
- USB MIDI OUT: transport path exists; clock generation is a firmware task.
- TRS MIDI OUT: unsupported/unverified; do not claim it.
