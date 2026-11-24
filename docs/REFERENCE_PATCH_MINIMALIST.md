# Reference patch: Minimalist Marbles → Rings → Clouds

## Source and attribution

This is the RINGS INTO CLOUDS adaptation reference for the Patchstorage composition [“Minimalist” Patch – Marbles + Rings + Clouds](https://patchstorage.com/minimalist-patch-marbles-rings-clouds/), by koma2000. The Patchstorage page describes the composition as a three-module ambient patch and lists its licence as Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0). Preserve attribution and the ShareAlike requirement for any adaptation of the patch itself.

The user also supplied `Ambient4.vcv`. Its saved Rack patch contains:
- Audible Instruments Marbles
- Audible Instruments Rings
- Audible Instruments Clouds
- Bogaudio LLFO
- Core AudioInterface

The LLFO is present but has no cables in the supplied patch. It is therefore not part of the core three-module patch.

This document records the patch as a musical and routing reference. VCV Rack plugin parameter IDs and values are not FM-1 parameter IDs; do not copy them directly into firmware preset arrays.

## Musical behaviour to reproduce

### Marbles — generative source

- Use a slowly evolving random sequence.
- Quantize generated pitches to a minor scale.
- Set Deja Vu around 10:30, giving a restrained amount of repetition.
- T section: use T1 only as the Rings strum/trigger source.
- X section: use X2 as the pitch source for Rings.
- Start X spread around 11 o’clock, favouring notes near the central value.
- Set Steps around 2 o’clock, retaining a broad selection of the minor-scale notes.
- Set Bias around 2 o’clock; expose it as a performance offset for shifting the pitch centre.
- Keep the trigger and pitch streams related to the same generative clock so the strums and notes remain coherent.

### Rings — resonator

- Use the sympathetic-strings model.
- Use duophonic behaviour.
- Marbles T1 triggers/strums the resonator.
- Marbles X2 controls pitch.
- Keep the resonator sustained and expressive enough that the Clouds buffer receives overlapping decays.
- The supplied VCV patch's Rings parameter values are retained in the source `Ambient4.vcv`; they are VCV plugin values and must be translated by meaning, not by numeric parameter index.

### Clouds — granular processor

- Use the classic granular mode.
- Set the blend fully wet.
- Set feedback to approximately 70%.
- Set stereo spread to approximately 70%.
- Set the reverb control fully up in the reference patch.
- Retain the other controls as adjustable sound-design parameters rather than treating their exact VCV numeric values as FM-1 values.
- The Clouds output is stereo.

## Supplied VCV patch routing

The cable graph in `Ambient4.vcv` is recorded below by Rack module and port IDs. Port IDs are deliberately kept literal; they should be resolved against the corresponding plugin version before any attempt to translate them into named firmware routes.

| From module | Output ID | To module | Input ID |
|---|---:|---|---:|
| Rings (module 24) | 0 | Clouds (module 25) | 6 |
| Rings (module 24) | 1 | Clouds (module 25) | 7 |
| Marbles (module 41) | 6 | Rings (module 24) | 6 |
| Marbles (module 41) | 0 | Rings (module 24) | 5 |
| Marbles (module 41) | 2 | Clouds (module 25) | 0 |
| Clouds (module 25) | 0 | AudioInterface (module 1) | 0 |
| Clouds (module 25) | 1 | AudioInterface (module 1) | 1 |
| Clouds (module 25) | 1 | Clouds (module 25) | 2 |

The last cable is an internal Clouds feedback/return connection in the supplied Rack graph. Verify its exact port meaning against the installed Audible Instruments Clouds plugin revision before translating it. Do not create an unbounded digital feedback loop in firmware; implement a bounded, gain-controlled feedback path with stability tests.

## RINGS INTO CLOUDS adaptation

The target FM-1 patch should preserve the musical relationship, not emulate VCV's cabling literally:

1. Marbles-style generative pitch and trigger lanes create a slow minor-scale phrase.
2. The trigger lane strums the Rings-inspired sympathetic resonator.
3. The pitch lane sets the resonator note.
4. The resonator's stereo output feeds the Clouds-inspired granular processor.
5. The granular processor returns stereo audio to the main output.
6. Feedback is bounded and protected against runaway level/DC build-up.
7. The patch is saved as a named factory starting preset, provisionally **MINIMALIST CLOUDS**.

The reference's “full wet” setting means the starter preset should favour the granular output. If a dry path is provided in the FM-1 architecture, retain a separate dry/wet control rather than hard-wiring the dry signal away.

## Current implementation boundary

A first partial firmware adaptation is now present on `rings-into-clouds-development`:

- PHYS `MINIMALIST` uses the existing Rings-derived sympathetic-string model, selects the minor sympathetic chord, and uses a long release so the resonator can ring naturally.
- The `MIST` factory phrase is a sparse C-minor sequence intended to be loaded with that sound.
- This is a playable resonator-and-sequence starting point, not the complete Patchstorage patch.

The current GRAIN engine is a sample-based granular voice, not a live-input Clouds processor. The Marbles-inspired generator is also not implemented yet. The current preset therefore does not claim Clouds processing, Marbles T1/X2 behaviour, full-wet feedback, or the VCV patch's complete routing.

Next implementation steps:
- Implement and profile a bounded live-audio granular buffer processor before calling it CLOUDS.
- Add a clock-coherent Marbles-style trigger and minor-scale pitch generator, with repetition/deja-vu control.
- Connect the generated trigger and pitch to the sympathetic resonator, then route its stereo output through the granular processor.
- Keep the preset lean: no extra oscillator or LFO is required for the core reference patch.
- Defer optional reverb until the Rings → Clouds signal path is stable and profiled. The reference's reverb setting is a desired sound-design target, not permission to reintroduce the removed global reverb bus.

## Verification checklist

- [ ] Minor-scale pitch quantisation is correct.
- [ ] Deja Vu/repetition amount creates a slowly evolving phrase.
- [ ] T1-like trigger reliably strums Rings.
- [ ] X2-like pitch output controls Rings pitch.
- [ ] Sympathetic resonator mode and duophonic behaviour are audible.
- [ ] Stereo resonator output reaches the granular processor.
- [ ] Clouds-style processor is full wet by default.
- [ ] Feedback is bounded and stable at the reference setting.
- [ ] Stereo output is correct.
- [ ] Preset saves and reloads all parameters and routing.
- [ ] CPU/RAM use is measured on the FM-1 before enabling any optional extras.
- [ ] Harbor testing is completed on a verified firmware artifact; physical FM-1 testing remains separate.
