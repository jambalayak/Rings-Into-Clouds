# RINGS INTO CLOUDS

**An experimental M-VAVE FM-1 instrument inspired by Mutable Instruments' modular-synthesizer design philosophy.**

RINGS INTO CLOUDS is a new instrument built on the Felucca firmware platform for the M-VAVE FM-1. Its musical centre is a playable physical-modeling resonator followed by a rich granular processor: resonant strings, struck objects, metallic tones, frozen grains, evolving textures and spacious ambient soundscapes.

This repository is an independent project. It is not affiliated with or endorsed by Mutable Instruments, M-VAVE, or the Felucca maintainers.

## Project direction

- **Rings-inspired resonator:** modal, sympathetic-string and inharmonic resonances, with expressive excitation and performance controls.
- **Clouds-inspired granular processor:** live granular processing, texture, freeze, stretch and buffer manipulation.
- **Flexible signal routing:** the resonator and granular processor should be independently routable rather than permanently locked to one serial chain.
- **Generative performance:** a Marbles-inspired random CV/trigger system, a separate arpeggiator, and a conventional step sequencer.
- **Additional sound sources:** Plaits-inspired oscillator models and a distinct six-operator FM engine.
- **Effects and modulation:** filtering, envelopes, LFOs and modulation. Legacy global delay, chorus and reverb have been removed to prioritise Rings and Clouds; a dedicated optional modular reverb is planned for a later stage.
- **Performance-first controls:** the FM-1 keyboard and physical controls remain central; deep editing is organised into clear module pages.

The intended first playable milestone is a reliable keyboard-playable resonator → granular signal path with working audio, usable presets and a coherent interface. More engines and generative features follow in measured stages.

## Visual direction

The interface takes inspiration from Mutable Instruments' visual language: distinctive module identities, bold but disciplined colour palettes, playful technical illustration, clear typography, compact parameter groupings and panel-like layouts.

All RINGS INTO CLOUDS artwork, icons, typography treatments and screen compositions will be original. Mutable Instruments graphics, logos, panel artwork and other assets are visual references only and are not copied into this project.

## Development status

This is an early development fork. At this stage the repository contains the Felucca FM-1 hardware/platform foundation; the new RINGS INTO CLOUDS sound architecture and interface are a development plan, not yet a completed implementation. Do not install experimental builds on hardware unless a release is explicitly marked for testing.

See [docs/PROJECT_DIRECTION.md](docs/PROJECT_DIRECTION.md) for the staged plan, [docs/MEMORY_PROFILE_OPTIONS.md](docs/MEMORY_PROFILE_OPTIONS.md) for the memory trade-offs, and [docs/MODULAR_REVERB_PLAN.md](docs/MODULAR_REVERB_PLAN.md) for the future optional reverb design.

## Build foundation

The project currently inherits Felucca's build system and hardware support. Start with [BUILDING.md](BUILDING.md) and follow its prerequisites, including the JieLi toolchain and AC79 SDK. The firmware uses submodules; obtain the complete source with:

```sh
git clone --recurse-submodules https://github.com/jambalayak/Rings-Into-Clouds.git
cd Rings-Into-Clouds
```

The inherited build instructions describe the current Felucca package and firmware identity. The project-specific release identity and installer branding will be changed only after the first project build is verified.

## Upstream platform and licensing

This project is derived from [Felucca](https://github.com/hugelton/Felucca), open-source FM-1 firmware by Leo Kuroshita / Hügelton Instruments. The inherited platform is licensed under GPL-3.0-only, with third-party components retaining their own licences. See [LICENSE](LICENSE), [LICENSING.md](LICENSING.md), [CREDITS.md](CREDITS.md), and the licence files in [LICENSES](LICENSES).

Any new DSP integration must preserve its upstream licence, notices and attribution. Do not assume that all Mutable Instruments modules share one licence: check the exact source revision and files before importing or adapting code.