# Optional modular reverb plan

## Product decision

The inherited Felucca global ROOM / SPRING / HALL buses stay removed. RINGS INTO CLOUDS may add a new reverb later, but only as an optional, patchable audio-processor node. It must not silently return as a permanent global send or take memory reserved for the two Rings instances and Clouds.

## Intended behaviour

- One independently enabled reverb node in the first implementation.
- Stereo input and stereo output, with explicit dry / wet mix.
- Patchable after Clouds, after Rings, or on a parallel branch through the modular graph.
- Parameters belong to the node: DECAY, DAMPING, SIZE and MIX. Add PRE-DELAY only if its storage cost is justified.
- Bypass must preserve the tail; clearing a tail is a deliberate user action or a documented patch-load policy.
- Save and restore all parameters and routing as part of the patch.
- MIDI clock is not required for the core reverb algorithm. If a tempo-synchronised pre-delay is later added, it follows the shared MIDI clock without generating or echoing clock.

## Memory-first implementation candidate

Start by evaluating a compact four-line feedback-delay-network (FDN) or equivalent small stereo algorithm, using fixed, statically allocated buffers and the FM-1 native sample rate. Avoid a large sample-rate-conversion layer, long stereo delay buffers, dynamic allocation and a second independent global bus.

A provisional design target is no more than 12 KiB of delay/diffuser storage for one instance. This is a design ceiling to evaluate, not a measured fit claim. The final buffer lengths, numeric format and CPU cost must be established against the actual target compiler and measured Rings + Clouds build. If a convincing reverb cannot meet the budget, present the measured options rather than reducing Rings/Clouds fidelity without approval.

## Integration and acceptance gates

1. Define typed stereo audio ports and graph-node lifecycle (initialise, process, bypass, tail-active, clear).
2. Allocate all state statically, outside the audio interrupt; no heap allocation, locks or flash access in the render path.
3. Measure exact target sizeof, linker placement and worst-case CPU for one instance.
4. Prove stable decay and bounded output at minimum / maximum DECAY, DAMPING and MIX, including silence and rapid parameter changes.
5. Verify dry signal, stereo image, tail continuity through bypass, patch save/load and graph routing.
6. Re-run MIDI clock jitter and audio-deadline tests with the node enabled.
7. Only enable it in a release when the measured memory map retains the project's required RAM and POOL headroom.

This is a future module specification only. No reverb DSP is currently included or claimed to be working.
