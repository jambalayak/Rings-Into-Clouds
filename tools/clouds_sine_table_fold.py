#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Temporary, verified Clouds-to-Rings sine-table folding source overlay."""
import re
import struct
from pathlib import Path

def values(path, symbol):
    text = path.read_text()
    m = re.search(r"const\s+float\s+" + re.escape(symbol) + r"\s*\[\s*\]\s*=\s*\{(.*?)\};", text, re.S)
    if not m:
        raise SystemExit("could not locate source table " + symbol + " in " + str(path))
    tokens = re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", m.group(1))
    return [struct.pack("<f", float(x)) for x in tokens]

def apply_sine_table_fold(root, patch_root):
    eur = root / "third_party/eurorack"
    clouds = values(eur / "clouds/resources.cc", "lut_sin")
    rings = values(eur / "rings/resources.cc", "lut_sine")
    if len(clouds) != 1281 or len(rings) != 5121:
        raise SystemExit(f"unexpected sine table lengths: Clouds={len(clouds)}, Rings={len(rings)}")
    if any(clouds[i] != rings[4 * i] for i in range(len(clouds))):
        raise SystemExit("Clouds lut_sin is not bit-identical to every fourth Rings lut_sine entry")

    source = eur / "clouds/dsp/granular_sample_player.h"
    original = source.read_text()
    old_left = "gain_l = Interpolate(lut_sin, pan, 256.0f);"
    old_right = "gain_r = Interpolate(lut_sin + 256, pan, 256.0f);"
    if original.count(old_left) != 1 or original.count(old_right) != 1:
        raise SystemExit("expected the two original Clouds sine interpolation callsites exactly once")
    patched = original.replace('#include "clouds/resources.h"',
                               '#include "clouds/resources.h"\n#include "rings/resources.h"', 1)
    marker = "const int32_t kMaxNumGrains = 64;"
    helper = """// Exact stride-4 view of Clouds' original 1281-entry lut_sin table.
 // Keep the original index scaling, truncation, fraction and linear interpolation.
 inline float InterpolateRingsSine(float index, int32_t offset) {
   index *= 256.0f;
   int32_t integral = static_cast<int32_t>(index);
   float fractional = index - static_cast<float>(integral);
   float a = rings::lut_sine[4 * integral + offset];
   float b = rings::lut_sine[4 * (integral + 1) + offset];
   return a + (b - a) * fractional;
 }

 """
    if patched.count(marker) != 1:
        raise SystemExit("Clouds namespace insertion marker not unique")
    patched = patched.replace(marker, helper + marker, 1)
    patched = patched.replace(old_left, "gain_l = InterpolateRingsSine(pan, 0);", 1)
    patched = patched.replace(old_right, "gain_r = InterpolateRingsSine(pan, 1024);", 1)
    if "Interpolate(lut_sin" in patched or "InterpolateRingsSine" not in patched:
        raise SystemExit("Clouds sine-table reference remains after overlay")
    destination = patch_root / "clouds/dsp/granular_sample_player.h"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(patched)

    # The Spectral-mode phase vocoder has a second, direct integer lookup in
    # FrameTransformation::fast_p2r. Fold that access through the same exact
    # stride-4 table mapping; preserve its angle quantisation and no-interp path.
    phase_source = eur / "clouds/dsp/pvoc/frame_transformation.h"
    phase_original = phase_source.read_text()
    old_fast_p2r = """  inline void fast_p2r(float magnitude, uint16_t angle, float* re, float* im) {
    angle >>= 6;
    *re = magnitude * lut_sin[angle + 256];
    *im = magnitude * lut_sin[angle];
  }"""
    new_fast_p2r = """  inline void fast_p2r(float magnitude, uint16_t angle, float* re, float* im) {
    angle >>= 6;
    *re = magnitude * rings::lut_sine[4 * angle + 1024];
    *im = magnitude * rings::lut_sine[4 * angle];
  }"""
    if phase_original.count(old_fast_p2r) != 1:
        raise SystemExit("expected the phase-vocoder fast_p2r sine lookups exactly once")
    phase_patched = phase_original.replace(
        '#include "clouds/resources.h"',
        '#include "clouds/resources.h"\n#include "rings/resources.h"', 1)
    phase_patched = phase_patched.replace(old_fast_p2r, new_fast_p2r, 1)
    if "lut_sin[" in phase_patched:
        raise SystemExit("phase-vocoder lut_sin lookup remains after overlay")
    phase_destination = patch_root / "clouds/dsp/pvoc/frame_transformation.h"
    phase_destination.parent.mkdir(parents=True, exist_ok=True)
    phase_destination.write_text(phase_patched)

    if "lut_sin[" in patched:
        raise SystemExit("granular-player lut_sin lookup remains after overlay")
    report = patch_root.parent / "sine-table-fold-verification.txt"
    report.write_text(
        "Clouds lut_sin entries: 1281\n"
        "Rings lut_sine entries: 5121\n"
        "Float32 bit-identical stride-4 comparison: PASS (1281/1281 entries)\n"
        "Granular player lookups: left offset 0; right offset 256; original scale 256 preserved\n"
        "Phase-vocoder fast_p2r lookups: lut_sin[angle] -> rings[4*angle]; lut_sin[angle+256] -> rings[4*angle+1024]\n"
        "Phase-vocoder angle domain: uint16 >> 6 gives 0..1023; maximum mapped index 5116 within 5121 entries\n"
        "Original Interpolate arithmetic preserved: index multiply, int32 truncation, fraction, a+(b-a)*fraction\n"
        "Overlay only: pinned submodules and production firmware source untouched\n"
    )
    print(report.read_text(), end="")
