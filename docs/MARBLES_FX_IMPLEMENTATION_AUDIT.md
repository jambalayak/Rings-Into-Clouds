# Marbles FX page — implementation audit

Status: source audit only. The page controls and Marbles DSP are not yet implemented.

## Confirmed UI integration points

- `firmware/src/params.c` owns the `FAM_FX` page family and the `PAGES[]` table. Current FX pages are DRIVE, INSERT and INSERT 2. `page_t` supports four parameter IDs and one graph renderer.
- `page_desc()` resolves ordinary page knobs to the selected track's stored parameters. A Marbles page must not pretend its controls are ordinary Rings parameters.
- `firmware/src/ui_input.c:edit_param()` dispatches special graph types before ordinary parameter editing. A dedicated `GR_MARBLES` branch can edit the eight Marbles controls directly.
- The main knob scan in `ui_input.c` already reads physical K1..K4 and calls `edit_param(k, s)`. The page therefore needs no separate hardware polling path; it needs a stable bank selector and a dedicated edit handler.
- `firmware/src/ui_graph.c:draw_graph()` owns the graph panel and switches on `pg->graph`. A dedicated renderer belongs here; the existing `GR_FX` renderer is the Drive page visual and should not be repurposed.
- `firmware/src/ui.c:page_visible()` is the visibility gate for pages and can keep the Marbles page visible only on the Rings part.

## Existing gaps

- There is no Marbles runtime state, generator, output routing or DSP consumer in `firmware/src`.
- The official Mutable Instruments Eurorack repository is already declared as the `third_party/eurorack` submodule, but its Marbles module is not integrated into the FM-1 build or signal path.
- There is no current page parameter descriptor or persistence mapping for RATE, JITTER, LENGTH, STEPS, DEJA VU, SPREAD, BIAS or t.
- The current project format is frozen FUN10 at 3840 bytes. Its reserved tail is tightly accounted for: FM6 patches, MIDI channel metadata, project name and checksum occupy defined regions. Do not consume these bytes casually or change FUN10 size/checksum.

## Required implementation sequence

1. Add a dedicated FX-family Marbles page and `GR_MARBLES` graph type. It must be visible only while the Rings part is selected.
2. Add a CLOCK / RANDOM bank state. Four physical knobs keep the same K1..K4 positions in either bank. Bank switching must not reset parameter values.
3. Add a compact renderer in the graph panel: four legible knob arcs/cards, value readouts, RUN/HOLD, clock and output activity. Use existing palette tokens and canvas primitives; no new framebuffer.
4. Port/integrate the official Marbles random generator under its upstream license and document the exact upstream revision. First establish its memory and CPU cost; do not claim Eurorack-identical behaviour until its algorithm and timing are validated.
5. Add a host-testable FM-1 adapter for clock, random CV, trigger streams and output routing. Keep Marbles control-rate only: no third audio engine or voice allocation.
6. Connect T1/T2/T3 independently to Rings trigger/strum and X/X1/X2/X3 to explicitly supported Rings modulation destinations.
7. Define versioned persistence outside the frozen FUN10 byte layout. The existing FUN10 checksum and all historical import paths must remain unchanged. Until persistence is ready, do not imply settings survive project reload or power cycle.
8. Add tests for all eight knob ranges and bank transitions, deterministic seeded output, jitter bounds, sequence memory/Deja Vu, steps, spread/bias, t gate probability, external-clock priority, independent T1/T2 routing, save/load migration and disabled-state silence.

## Safety rails

- Never use retired track parameter IDs or reserved project bytes without a format audit.
- Never route Marbles outputs to a third audio part.
- Never let t randomly mute Rings audio.
- External clock takes priority when selected; RATE only controls the internal clock.
- JITTER must be bounded within its current step.
- Keep Clouds independently bypassable.
- Preserve old FUN1..FUN10 projects and existing Rings patterns.
- Treat a successful host test as host validation only, not FM-1 hardware validation.
