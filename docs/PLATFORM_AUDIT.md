# Platform audit — initial source inspection

Inspection target: `rings-into-clouds-development`, inherited Felucca 1.8.3 source. This is a source-level inspection only; no firmware build or device test has been run in this session.

## Confirmed foundations

- `firmware/src/felucca.c` is the single compilation unit and shows the order of the HAL, audio engine, MIDI/sequencer, UI, storage and update code.
- `firmware/src/panel.c` defines 14 panel buttons and 7 encoder roles, including SELECT, ALGORITHM, PRESETS and four parameter knobs. It explicitly says the printed-label mapping is a best guess that can be calibrated on the device. Therefore, the project must retain/verify hardware calibration rather than hard-code assumptions from a product photo.
- `firmware/src/audio.c` renders stereo audio in I2S half-buffers. `HALF_FRAMES` is 128 in `core.h`, documented as about 2.9 ms at 44.1 kHz. `audio_block()` calls `mix_block()` before the stereo output conversion.
- `firmware/src/core.h` currently defines four synth parts and a shared budget of eight sounding voices across those parts. This is not four independent eight-voice polyphonic synths.
- `firmware/src/voice.c` owns voice allocation, envelopes, LFO processing and per-track rendering in the audio interrupt.
- `firmware/src/fx.c` already contains shared chorus, tempo delay and ROOM/SPRING/HALL reverb buses, plus per-track distortion and an insert path.
- `FELUCCA_CPU2` enables the optional second-core path. The source comments describe fallback/retirement behaviour and the need to keep late work from breaking audio.

## Existing sound engines relevant to this project

- `firmware/src/eng_phys.c` already provides a PHYS engine with MODAL, STRNG, MEMB and SYMP models. Its DSP combines DaisySP physical models with a fixed-point port of Rings sympathetic strings (`phys_symp.c`). It is Rings-related physical modelling, but it is not the complete Mutable Instruments Rings module.
- PHYS currently caps each part at three voices because of its per-part engine-state allocation.
- `firmware/src/eng_grain.c` already provides a sample-based granular engine with a per-part pool of 12 grains, up to three voices per part, position, density, size, spread, random detune/reverse and tone. It is Felucca's own design over sample zones; it is not the complete Mutable Instruments Clouds processor.
- `firmware/src/eng_fm6.c` is included as a six-operator FM engine, using the msfa port documented in the licensing files.
- `firmware/src/engines.c` shows the engine table and a shared per-part engine-memory region. The normal build's `ENG_MEM_PART` is 12,888 bytes per part (13,344 bytes when ADPCM is enabled). Engines with larger state share this region because each part runs one engine at a time.

## UI foundations

- `firmware/src/ui_draw.c` documents a 240 × 240 screen, four knob cards, a central panel and a footer.
- `firmware/src/gfx.c` uses RGB565 drawing, rasterised fonts and theme colour tokens; `ui_palettes.h` contains the palette definitions.
- The current design is a flat card-and-panel interface. This is a useful technical base for a new module-inspired visual language, but the project still needs original artwork, module identity and page layouts.

## Consequences for RINGS INTO CLOUDS

1. We should not duplicate PHYS or GRAIN before evaluating whether to extend, replace or selectively reuse them. The current PHYS and GRAIN engines already provide useful starting points, but neither should be misrepresented as a full Rings or Clouds port.
2. The first milestone should be one playable resonator-to-granular path, not three simultaneous fully independent Clouds processors.
3. The voice budget, per-part memory union and audio deadline must shape the architecture. Polyphony and simultaneous module count will be decided by target profiling.
4. Reverb, chorus, delay, distortion and insert infrastructure already exist. First assess whether their current controls and routing meet the instrument design before adding duplicate DSP.
5. The actual panel mapping must be verified with the FM-1 calibration flow and/or physical hardware; the source itself warns that the printed labels are a best guess.
6. The display is 240 × 240, so module-inspired layouts need compact typography, deliberate grouping and legible parameter labels.

## Next technical task

Build and test the inherited firmware unchanged, then inspect the exact engine interfaces, parameter mapping, preset persistence and FX routing before changing DSP. Keep the baseline build and test results so later audio and UI changes can be compared.