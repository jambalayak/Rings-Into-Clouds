#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Float-reference vs packed-24 Rings delay scale sweep; host only, no Clouds/audio route."""
import csv
import json
import math
import pathlib
import struct
import subprocess
import wave
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
EUR = ROOT / "third_party" / "eurorack"
STM = ROOT / "third_party" / "stmlib"
PATCH = ROOT / "build" / "upstream-dsp-compile" / "source-patches"
WORK = ROOT / "build" / "rings-delay-packed24-scale-sweep"
OUT = WORK / "results"
OUT.mkdir(parents=True, exist_ok=True)

part_h = (PATCH / "rings/dsp/part.h").read_text()
part_cc = (PATCH / "rings/dsp/part.cc").read_text()
assert "STRING_AND_REVERB" not in part_h + part_cc
dsp_h = (EUR / "rings/dsp/dsp.h").read_text().replace("48000.0f", "44117.6470588f")
(PATCH / "rings/dsp/dsp.h").write_text(dsp_h)

orig_string = (EUR / "rings/dsp/string.h").read_text()
needle = ("typedef stmlib::DelayLine<float, kDelayLineSize> StringDelayLine;\n"
          "typedef stmlib::DelayLine<float, kDelayLineSize / 2> StiffnessDelayLine;")
replacement = ("typedef Q24DelayLine<kDelayLineSize> StringDelayLine;\n"
               "typedef Q24DelayLine<kDelayLineSize / 2> StiffnessDelayLine;")
q24_string = orig_string.replace(
    '#include "stmlib/stmlib.h"',
    '#include "stmlib/stmlib.h"\n#include "rings/dsp/q24_delay_line.h"').replace(needle, replacement)
if q24_string == orig_string:
    raise SystemExit("Could not apply packed-24 String/Stiffness delay typedef overlay")

(PATCH / "rings/dsp").mkdir(parents=True, exist_ok=True)
(PATCH / "rings/dsp/q24_delay_line.h").write_text(
    (ROOT / "tools/rings_delay_test/q24_delay_line.h").read_text())

sources = sorted(set(
    list((EUR / "rings/dsp").glob("*.cc")) + [EUR / "rings/resources.cc"] +
    list((STM / "dsp").glob("*.cc")) + list((STM / "utils").glob("*.cc"))))
sources = [PATCH / "rings/dsp/part.cc" if p.name == "part.cc" else p
           for p in sources if "string_synth" not in p.name]
main = ROOT / "tools" / "rings_delay_test" / "main_scale_sweep.cc"
include = [
    "-I" + str(PATCH), "-I" + str(ROOT / "tools/rings_delay_test"),
    "-I" + str(ROOT / "third_party"), "-I" + str(EUR), "-I" + str(STM)
]
common = [
    "g++", "-std=c++11", "-O2", "-D_GNU_SOURCE", "-DTEST",
    "-ffunction-sections", "-fdata-sections",
    "-Wno-unused-function", "-Wno-unused-variable", *include
]
variants = [("float", None), ("scale-131072", 131072),
            ("scale-524288", 524288), ("scale-1048576", 1048576)]

for name, scale in variants:
    build = WORK / name
    build.mkdir(parents=True, exist_ok=True)
    (PATCH / "rings/dsp/string.h").write_text(
        orig_string if scale is None else q24_string)
    extra = [] if scale is None else [
        f"-DRINGS_DELAY_SCALE={scale}", "-DRINGS_DELAY_DIAGNOSTICS=1"
    ]
    objects = []
    for src in sources:
        obj = build / (str(src).replace("/", "__") + ".o")
        subprocess.run([*common, *extra, "-c", str(src), "-o", str(obj)],
                       cwd=ROOT, check=True)
        objects.append(str(obj))
    exe = build / "rings_scale_sweep"
    subprocess.run([*common, *extra, str(main), *objects,
                    "-Wl,--gc-sections", "-o", str(exe)], cwd=ROOT, check=True)
    subprocess.run([str(exe), str(build / "audio.f32")], cwd=build, check=True)

def rms(x):
    return float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2)))

def snr(reference, test):
    return 20.0 * math.log10(max(rms(reference), 1e-15) /
                             max(rms(reference - test), 1e-15))

def write_float_wav(path, samples):
    samples = np.asarray(samples, dtype="<f4")
    payload = samples.tobytes()
    fmt = struct.pack("<HHIIHH", 3, 2, 44118, 44118 * 8, 8, 32)
    header = (b"RIFF" + struct.pack("<I", 36 + len(payload)) + b"WAVE" +
              b"fmt " + struct.pack("<I", 16) + fmt +
              b"data" + struct.pack("<I", len(payload)))
    pathlib.Path(path).write_bytes(header + payload)

reference = np.fromfile(WORK / "float" / "audio.f32", dtype=np.float32).reshape(-1, 2)
ref_segments = list(csv.DictReader(open(WORK / "float" / "segments.csv", newline="")))
models = ["Modal", "Sympathetic Strings", "String", "FM Voice",
          "Quantized Sympathetic Strings"]
summary = {
    "test": "Five Rings models; four-resonator polyphony; neutral, bright, high-resonance, loud-external and rapid-note-change profiles; no Clouds processing",
    "notes_midi": [36, 48, 60, 84],
    "polyphony": 4,
    "strums_per_case": 4,
    "profiles": ["neutral", "bright", "high_resonance", "loud_external", "rapid_note_change"],
    "cases_per_scale": 25,
    "sample_rate_hz_exact": 24000000 / 544,
    "wav_sample_rate_hz": 44118,
    "wav_format": "32-bit IEEE float stereo; no normalization, no gain adjustment, no output clipping",
    "variants": {}
}

for name, scale in variants[1:]:
    rendered = np.fromfile(WORK / name / "audio.f32", dtype=np.float32).reshape(-1, 2)
    segments = list(csv.DictReader(open(WORK / name / "segments.csv", newline="")))
    if len(segments) != len(ref_segments) or rendered.shape != reference.shape:
        raise SystemExit(f"{name}: output length or segment count differs from float reference")
    rows = []
    for ref_meta, test_meta in zip(ref_segments, segments):
        if any(ref_meta[k] != test_meta[k] for k in ("start", "frames", "model", "profile")):
            raise SystemExit(f"{name}: segment layout differs from float reference")
        start, count = int(ref_meta["start"]), int(ref_meta["frames"])
        x, y = reference[start:start + count], rendered[start:start + count]
        rows.append({
            "model": int(ref_meta["model"]),
            "model_name": models[int(ref_meta["model"])],
            "profile": ref_meta["profile"],
            "snr_db": snr(x, y),
            "rms_error": rms(y - x),
            "reference_peak": float(np.max(np.abs(x))),
            "packed24_peak": float(np.max(np.abs(y))),
            "reference_samples_over_full_scale": int(np.count_nonzero(np.abs(x) > 1.0)),
            "packed24_samples_over_full_scale": int(np.count_nonzero(np.abs(y) > 1.0)),
            "delay_saturation_count": int(test_meta["saturation_count"]),
            "max_abs_delay_value": float(test_meta["max_abs_delay_value"]),
            "external_exciter_peak": float(test_meta["external_peak"]),
            "damping": float(test_meta["damping"]),
            "polyphony": int(test_meta["polyphony"]),
            "strums": int(test_meta["strums"])
        })
    per_model = []
    for model_index, model_name in enumerate(models):
        cases = [r for r in rows if r["model"] == model_index]
        per_model.append({
            "model": model_name,
            "mean_snr_db": float(np.mean([r["snr_db"] for r in cases])),
            "worst_snr_db": min(r["snr_db"] for r in cases),
            "worst_case": min(cases, key=lambda r: r["snr_db"]),
            "reference_peak_max": max(r["reference_peak"] for r in cases),
            "packed24_peak_max": max(r["packed24_peak"] for r in cases),
            "reference_over_full_scale_samples": sum(r["reference_samples_over_full_scale"] for r in cases),
            "packed24_over_full_scale_samples": sum(r["packed24_samples_over_full_scale"] for r in cases),
            "delay_saturation_count": sum(r["delay_saturation_count"] for r in cases)
        })
    stats = {}
    for line in (WORK / name / "delay_stats.txt").read_text().splitlines():
        key, value = line.split("=", 1)
        stats[key] = float(value)
    variant = {
        "scale": int(scale),
        "positive_range": 8388607.0 / scale,
        "negative_range": -8388608.0 / scale,
        "overall_snr_db": snr(reference, rendered),
        "overall_rms_error": rms(rendered - reference),
        "delay_saturation_count": int(stats["qn_saturation_count"]),
        "max_abs_delay_value": float(stats["qn_max_abs"]),
        "host_part_size_bytes": int(stats["part_size_bytes"]),
        "host_string_size_bytes": int(stats["string_size_bytes"]),
        "per_model": per_model,
        "cases_detail": rows
    }
    summary["variants"][name] = variant
    write_float_wav(OUT / f"rings-packed24-{name}.wav", rendered)
    for model_index, model_name in ((1, "sympathetic-strings"),):
        model_cases = [r for r in rows if r["model"] == model_index]
        worst = min(model_cases, key=lambda r: r["snr_db"])
        start, count = int(ref_segments[rows.index(worst)]["start"]), int(ref_segments[rows.index(worst)]["frames"])
        write_float_wav(OUT / f"worst-{model_name}-float-{name}.wav", reference[start:start + count])
        write_float_wav(OUT / f"worst-{model_name}-{name}.wav", rendered[start:start + count])
        variant["worst_sympathetic_case"] = {
            "profile": worst["profile"], "snr_db": worst["snr_db"],
            "reference_peak": worst["reference_peak"],
            "packed24_peak": worst["packed24_peak"],
            "delay_saturation_count": worst["delay_saturation_count"],
            "reference_samples_over_full_scale": worst["reference_samples_over_full_scale"],
            "packed24_samples_over_full_scale": worst["packed24_samples_over_full_scale"]
        }

write_float_wav(OUT / "rings-packed24-float-reference.wav", reference)
(OUT / "wav-readme.txt").write_text(
    "All WAVs are 32-bit IEEE-float stereo at nominal 44,118 Hz.\n"
    "They are unnormalised and use identical DSP stimulus/gain across float and packed-24 variants.\n"
    "Values above +/-1.0 are preserved in the files; over-full-scale sample counts are reported in metrics.json.\n"
    "The packed-24 WAVs are the float DSP outputs from a Rings engine whose String/Stiffness delay memories use signed packed 24-bit storage.\n"
)
(OUT / "metrics.json").write_text(json.dumps(summary, indent=2) + "\n")
with open(OUT / "cases.csv", "w", newline="") as f:
    fields = ["scale", "model_name", "profile", "snr_db", "reference_peak",
              "packed24_peak", "reference_samples_over_full_scale",
              "packed24_samples_over_full_scale", "delay_saturation_count",
              "max_abs_delay_value", "damping", "external_exciter_peak"]
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for variant_name, variant in summary["variants"].items():
        for row in variant["cases_detail"]:
            writer.writerow({"scale": variant["scale"], **{k: row[k] for k in fields if k != "scale"}})

print(json.dumps({
    "cases_per_scale": summary["cases_per_scale"],
    "variants": {k: {"overall_snr_db": v["overall_snr_db"],
                     "delay_saturation_count": v["delay_saturation_count"],
                     "worst_sympathetic_case": v["worst_sympathetic_case"]}
                 for k, v in summary["variants"].items()}
}, indent=2))
