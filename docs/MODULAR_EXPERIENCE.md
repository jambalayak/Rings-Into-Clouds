# Modular instrument experience

## Product direction

RINGS INTO CLOUDS should feel and behave like a compact modular synthesizer housed inside the M-VAVE FM-1. This is a core product requirement, not a cosmetic theme.

The interface should combine Mutable Instruments-inspired visual language with the organisation and signal-flow clarity of a Eurorack system. All artwork and UI assets must be original; use the references as design inspiration, not as material to copy.

## 1. Visual language: a virtual modular rack

- Organise the instrument into recognisable module panels: EXCITER, RINGS, CLOUDS, RIPPLE, PEAKS, MARBLES, YARNS, PLaits, FX, MIXER and ROUTING.
- Give each module a consistent identity through a restrained accent colour, title, compact controls, status indicators and a miniature signal-flow graphic.
- Use original panel illustrations, fine technical lines, subtle grid/rack markings, knob arcs, patch sockets, signal traces and clear typographic hierarchy.
- Use patch-cable curves and animated signal pulses in routing views, while keeping the 240 × 240 screen readable.
- Avoid cramming a full desktop Eurorack wall onto the display. Show one selected module at a time, with a persistent overview of connected modules and signal activity.
- Provide a distinctive RACK overview screen showing the active modules and their connections.
- Keep colour meaningful: module identity, signal type, modulation, audio, clock and triggers should have consistent visual conventions and remain distinguishable without colour alone.

## 2. Functional modularity

The user should be able to build a patch by connecting virtual module inputs and outputs, rather than being limited to a fixed internal signal chain.

### Audio patching
Support a graph of audio modules with selectable source, destination, routing order and parallel paths. The intended topology includes:
- Exciter / Plaits / external input -> Rings -> Clouds -> FX -> Mixer
- Exciter -> Clouds -> Rings -> FX -> Mixer
- Rings -> Reverb / Delay / Distortion
- Frozen Clouds buffer -> Rings
- Parallel dry and processed paths
- Feedback paths only where stability and headroom can be safely managed

### Modulation patching
Provide assignable modulation connections from Peaks envelopes/LFOs, Marbles random/CV streams, envelopes, velocity, aftertouch and other supported sources to compatible module parameters.

Each connection should have:
- Source and destination
- Amount and polarity
- Attenuation/attenuverter where appropriate
- Optional offset or scaling where supported
- A clear indication of the current modulation value

### Clock, gate and trigger patching
Keep clock, gate, trigger and reset routes distinct from audio and continuous modulation. Allow Marbles/Yarns/step sequencer clocks and triggers to drive compatible modules and envelopes. Avoid pretending that a signal type can connect to an incompatible destination.

## MIDI clock as a first-class event source
External MIDI clock and transport must be available to the modular event system. Treat clock, Start, Continue, Stop and Reset as timestamped events, not audio or continuous modulation. The selected MIDI clock source must be able to drive the sequencer, arpeggiator, clocked modulation, generative modules and tempo-aware processors. The instrument should also expose its internal clock/transport as an event source for MIDI output. Keep input source selection distinct from MIDI note-channel routing, and prevent duplicate-clock feedback. Full requirements are in `docs/MIDI_SYNC_REQUIREMENTS.md`.

## 3. FM-1 control experience

The FM-1 has limited physical controls, so the modular experience must be navigable rather than requiring a physical socket for every connection.

- RACK: overview of modules and active connections.
- MODULE: select a module and edit its parameters.
- PATCH: choose a source, destination and connection amount using encoders and page controls.
- MOD: inspect and edit modulation assignments.
- ROUTE: choose audio order, parallel paths and mixer levels.
- PRESET: save and recall complete patches, including module states, routing, modulation and sequencer configuration.
- Provide a quick performance view with the most important macro controls for a patch.
- Keep the currently selected module and parameter visible; never make the user guess which module a knob controls.
- Use context-sensitive encoder labels and clear focus/highlight states.
- Provide sensible default patches so the instrument remains immediately playable without requiring patch programming.

## 4. Patch data model

Represent a patch as a graph rather than a hard-coded list of effects.

Conceptual entities:
- Module instance: module type, instance ID, enabled state and parameter state.
- Audio connection: source output, destination input, gain and channel mapping.
- Modulation connection: source, destination parameter, amount, polarity and scaling.
- Event connection: clock, gate, trigger or reset source and destination.
- Patch metadata: name, version, module configuration, mixer state and performance macros.

The graph must validate connection types, detect unsupported cycles, protect against runaway feedback, and enforce memory/CPU budgets before activation. Use stable IDs so saving and loading does not depend on screen order.

## 5. Resource-aware behaviour

Modularity must be real but bounded by the FM-1. Define a resource budget for module instances, audio paths, modulation routes, buffers, voices and CPU time. Profile worst-case configurations on target hardware.

When a patch exceeds the available budget:
- Explain which module or route exceeds the budget.
- Offer a lower-quality or lower-polyphony option where it is safe.
- Never silently remove a connection or change a module's algorithm.
- Keep audio deadline protection and safe feedback limiting.

Start with a reliable small graph and expand only after profiling. The first milestone is a working, editable audio route with at least one resonator, one granular processor, a mixer and a spatial effect. Then add modulation and event routing.

## 6. Validation

- Verify that saved patches restore module instances, parameter values and all connections.
- Test audio routing, stereo mapping, modulation scaling, clock/trigger timing and feedback safety.
- Test UI navigation with the FM-1's actual controls and 240 × 240 display.
- Ensure every visible connection corresponds to a real DSP route; no decorative patch cables.
- Maintain clear documentation of supported module ports and signal types.

## Status

This document defines the intended experience. It is not a claim that graph routing, virtual patch cables or the module rack UI have already been implemented.
