# Patch engine architecture — implementation plan

## Purpose

Turn the modular instrument specification into a feasible FM-1 audio architecture without pretending that the inherited Felucca engine already supports arbitrary module-to-module patching.

This is an implementation plan, not a claim that the patch graph or new module DSP has been implemented.

## 1. Current firmware reality

The inherited firmware is organised around four synth parts. Each part selects one engine at a time, owns its parameter and voice state, and is rendered by the track/voice path. Each part also has its own engine-memory region for the selected engine's large mutable state. The four parts share a global sounding-voice budget of eight. This existing model supports selecting one Rings engine on a single selected part; the Rings port should own one dedicated state object, not duplicated per-part instances.

The audio interrupt renders short blocks: 128 frames per I2S half, internally processed in 32-sample control blocks. The current mixer combines the four part outputs, applies per-track processing and sends, then processes shared chorus, delay and reverb buses before stereo output.

Large engine state is overlaid in one memory region per part because only one engine is active on a part at a time. That is efficient for the existing track model, but it is not a general-purpose pool for several simultaneously active modular processors.

Consequences:

- A track-to-track cable cannot be implemented by drawing a cable in the UI; the mixer and DSP ownership must change.
- A conventional effect insert is not automatically equivalent to a modular processor node.
- A full graph must not allocate memory, lock, search dynamically or compile its topology inside the audio interrupt.
- Multiple large module instances need an explicit memory and CPU budget. The product target is one Rings instance feeding Clouds; no second Rings allocation is required.
- Existing voice allocation, engine switching, MIDI, sequencer and preset compatibility should be preserved while the graph is introduced incrementally.

## 2. Separate the module roles

Use explicit node classes. Do not force every Mutable Instruments module into the existing single-engine-per-track abstraction.

### Voice / sound-source nodes

These receive note, gate, velocity and modulation events and produce audio:

- Plaits
- Rings when used as a note-triggered resonator/instrument
- Existing Felucca sound engines during the transition

### Audio processor nodes

These receive audio blocks and produce processed audio:

- Clouds
- Beads
- Ripples when used as an audio filter
- Distortion, chorus, delay and reverb
- Mixer / output

### Control and event nodes

These produce non-audio signals:

- Peaks envelopes and LFOs
- Marbles random, pitch and gate streams
- Yarns / MIDI and clock utilities
- Sequencer, keyboard, velocity, aftertouch, clock, gate, trigger and reset sources

A module may expose more than one port class. Each port must declare its signal type and channel count.

## 3. Runtime design

### 3.1 Edit-time patch model

Store a patch as bounded, versioned data:

- Module instance: stable ID, module type, enabled/bypass state, parameter state.
- Port: stable module-local port ID, direction, signal type and channel layout.
- Connection: source module/port, destination module/port, gain or modulation amount, polarity and channel mapping.
- Patch metadata: version, name, performance macros, clock configuration and mixer state.

Use fixed maximum counts for the first implementation. Reject an over-limit patch with a clear error; never silently discard modules or cables.

### 3.2 Compiled audio plan

Build a compact execution plan when a patch is loaded or edited, outside the audio interrupt:

1. Validate module IDs and port IDs.
2. Validate signal types, directions and channel layouts.
3. Detect unsupported audio cycles.
4. Check module-instance, buffer, memory and estimated CPU budgets.
5. Topologically order the audio graph.
6. Assign preallocated block buffers and module state.
7. Publish the completed plan atomically at a safe block boundary.

The audio interrupt should only execute the already-compiled plan. It must not run graph searches, allocate/free memory, wait on a mutex or perform flash operations.

### 3.3 Audio block contract

Use the existing internal control-block size as the initial processing contract (currently 32 samples). Each audio node should expose a predictable block-processing interface with:

- Explicit input and output buffers.
- Fixed channel count and sample format.
- Persistent state owned by that node instance.
- A bypass path with defined latency/level behaviour.
- A declared worst-case CPU estimate and memory requirement.

Do not assume every processor can safely be called at a lower sample rate. Any downsampling or oversampling must be an explicit part of that module's faithful DSP implementation.

### 3.4 Modulation and events

Keep audio buffers separate from control/event data.

- Continuous modulation: block-rate or audio-rate values, explicitly declared per destination.
- Gate/trigger: edge-aware events with sample or block offsets.
- Clock/reset: timestamped events, not audio samples.
- Pitch/CV: typed control values with documented units and range.

Define each module parameter's modulation range, scaling, polarity and smoothing. Avoid implicit conversions between incompatible signal classes.

## 4. Memory and CPU safety

The graph is a bounded embedded system, not a desktop modular environment.

- Use statically allocated pools for node state, audio buffers and connection tables.
- No heap allocation in the audio path.
- Every module declares minimum and maximum state memory, buffer needs, voice cost and estimated block cost.
- Enforce a conservative CPU ceiling below the measured audio deadline; leave headroom for MIDI, UI, FX and interrupt variation.
- Profile with the actual FM-1 build and hardware. Host tests are necessary but cannot establish target CPU cost.
- Preserve existing audio-overload protection as a final safety net, not as the normal resource manager.
- Reject a patch before activation if it cannot fit. Explain the reason and identify the module or route that exceeds the budget.
- Feedback is disabled in the first graph version. Later feedback requires an explicit delay element, bounded gain, DC protection and stability tests.

The existing per-part engine-memory union must not be reused as if it were a simultaneous multi-node pool. Its lifetime and ownership assumptions are different.

## 5. Migration strategy

### Stage A — baseline and preservation

- Build and test the inherited firmware unchanged.
- Record baseline image size, RAM/pool usage, CPU load and audio regression results.
- Preserve existing track, preset, project and MIDI behaviour.

### Stage B — explicit track audio outputs

- Give each of the four existing parts a clearly defined audio output bus.
- Keep current track rendering and voice allocation intact.
- Make the current mixer consume these buses without changing sound.
- Add regression renders proving the default mix remains unchanged.

This creates real source ports without prematurely rewriting every engine.

### Stage C — first bounded processor graph

- Add a small, fixed graph after the track buses.
- Start with mixer, bypassable filter/drive and existing shared FX where their interfaces permit.
- Support serial and parallel audio routes, stereo routing and explicit gain.
- Add graph validation and patch save/load.
- Confirm that every UI cable changes the actual DSP route.

### Stage D — module-native processors

- Add one module at a time behind a common processor interface.
- Prioritise the first complete resonator-to-granular path.
- Treat Rings as a faithful resonator/instrument implementation, not merely a filter preset.
- Treat Clouds and Beads as distinct processors with their own algorithms and state.
- Add modulation/event routing only after audio routing is stable.

### Stage E — full modular instrument

- Add richer source nodes, Peaks/Marbles/Yarns control paths, patch templates and performance macros.
- Add carefully controlled feedback only after the non-feedback graph is proven.
- Expand node and connection limits only when target profiling supports it.

## 6. First playable patch

The first reference patch should be simple and testable:

Part 1 (exciter source) -> Rings resonator -> Clouds processor -> Mixer -> stereo output

The initial source can be an existing sound engine while the dedicated Plaits port is developed. This is a temporary source substitution, not a claim that the final instrument should be limited to Felucca engines.

The first milestone is complete only when:

- Audio actually passes through the selected resonator and granular processor.
- Changing a module parameter audibly changes that processor.
- Bypass and route changes behave predictably.
- A saved patch restores all modules, parameters and connections.
- A render test checks output against a stored reference.
- The FM-1 target build meets the measured audio deadline with safe headroom.

## 7. UI contract

The rack UI is a view of the same patch data used by the audio engine.

- Selecting a cable selects its connection record.
- Moving a connection changes the compiled route after validation.
- Bypassing a module changes the actual signal path.
- Port labels and signal colours come from port metadata.
- Invalid connections are visibly rejected with a short reason.
- The 240 × 240 display shows a compact rack overview and one focused module; it does not attempt to draw a full desktop Eurorack wall.

No decorative cable, fake socket or unconnected module may be presented as an active part of the sound.

## 8. Test requirements

Host-side tests:

- Valid and invalid port connections.
- Duplicate IDs and missing modules.
- Graph ordering and cycle rejection.
- Buffer assignment and pool exhaustion.
- Patch serialization, version migration and round-trip restore.
- Deterministic block processing and bypass behaviour.
- Modulation scaling and event ordering.

Target-side tests:

- Worst-case CPU time per audio half and per graph configuration.
- Maximum pool/RAM use and stack use.
- Audio deadline misses and overload recovery.
- Long-running patch stability, save/load and rapid route changes.
- Stereo correctness, clipping/headroom and feedback safety.
- UI responsiveness while the audio graph is active.

## 9. Non-goals for the first implementation

- Unlimited Eurorack-style module count.
- Arbitrary zero-delay feedback loops.
- Dynamic memory allocation in the audio thread.
- Replacing the entire voice allocator before a working audio graph exists.
- Claiming a module is a faithful Mutable Instruments port until its source revision, DSP behaviour, modes, controls and tests have been verified.

## Status

This is an architecture and migration plan based on source inspection of the current Felucca-derived firmware. No graph runtime, new DSP module or target performance result is claimed by this document.
