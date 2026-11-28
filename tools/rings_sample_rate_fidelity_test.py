#!/usr/bin/env python3
"""Compare original-float Rings at 48 kHz and the FM-1 calculated codec rate."""
import csv
import json
import math
import pathlib
import subprocess

import numpy as np
from scipy.signal import resample_poly, welch, find_peaks

ROOT = pathlib.Path(__file__).resolve().parents[1]
EUR = ROOT / "third_party" / "eurorack"
STM = ROOT / "third_party" / "stmlib"
BASE_PATCH = ROOT / "build" / "upstream-dsp-compile" / "source-patches"
WORK = ROOT / "build" / "rings-sample-rate-fidelity"
OUT = WORK / "results"
OUT.mkdir(parents=True, exist_ok=True)

TARGET_RATE = 24000000.0 / 544.0
REFERENCE_RATE = 48000.0
# TARGET_RATE / REFERENCE_RATE reduces exactly to 125 / 136.
UP, DOWN = 125, 136

for required in (BASE_PATCH / "rings/dsp/part.h",
                 BASE_PATCH / "rings/dsp/part.cc"):
    if not required.is_file():
        raise SystemExit("Run tools/check_upstream_dsp_compile.py first; missing " + str(required))

sources = sorted(set(
    list((EUR / "rings/dsp").glob("*.cc")) +
    [EUR / "rings/resources.cc"] +
    list((STM / "dsp").glob("*.cc")) +
    list((STM / "utils").glob("*.cc"))
))
sources = [p for p in sources if "string_synth" not in p.name]
sources = [BASE_PATCH / "rings/dsp/part.cc" if p == EUR / "rings/dsp/part.cc" else p
           for p in sources]

common = [
    "g++", "-std=c++11", "-O2", "-D_GNU_SOURCE", "-DTEST",
    "-ffunction-sections", "-fdata-sections",
    "-Wno-unused-function", "-Wno-unused-variable",
    "-I" + str(BASE_PATCH),
    "-I" + str(ROOT / "tools/rings_delay_test"),
    "-I" + str(ROOT / "third_party"),
    "-I" + str(EUR), "-I" + str(STM),
]

variants = [("eurorack_48k", REFERENCE_RATE),
            ("fm1_codec_rate", TARGET_RATE)]
for name, rate in variants:
    patch = WORK / name / "patch"
    (patch / "rings/dsp").mkdir(parents=True, exist_ok=True)
    dsp_header = (EUR / "rings/dsp/dsp.h").read_text()
    if dsp_header.count("48000.0f") != 1:
        raise SystemExit("Pinned Rings sample-rate definition changed; review overlay")
    dsp_header = dsp_header.replace("48000.0f", f"{rate:.10f}f")
    (patch / "rings/dsp/dsp.h").write_text(dsp_header)

    build = WORK / name
    build.mkdir(parents=True, exist_ok=True)
    include = ["-I" + str(patch), *common[common.index("-I" + str(BASE_PATCH)) + 1:]]
    # Ensure the sample-rate-specific header wins, while retaining the common
    # FM-1 portability overlays for Part and stmlib.
    include = ["-I" + str(patch), "-I" + str(BASE_PATCH),
               "-I" + str(ROOT / "tools/rings_delay_test"),
               "-I" + str(ROOT / "third_party"), "-I" + str(EUR), "-I" + str(STM)]
    objects = []
    for src in sources:
        obj = build / (str(src).replace("/", "__") + ".o")
        subprocess.run([
            "g++", "-std=c++11", "-O2", "-D_GNU_SOURCE", "-DTEST",
            "-ffunction-sections", "-fdata-sections",
            "-Wno-unused-function", "-Wno-unused-variable",
            *include, "-c", str(src), "-o", str(obj)
        ], cwd=ROOT, check=True)
        objects.append(str(obj))

    exe = build / "rings_rate_test"
    subprocess.run([
        "g++", "-std=c++11", "-O2", "-D_GNU_SOURCE", "-DTEST",
        f"-DRINGS_TEST_SAMPLE_RATE={rate:.10f}f",
        "-ffunction-sections", "-fdata-sections",
        *include, str(ROOT / "tools/rings_delay_test/main.cc"),
        *objects, "-Wl,--gc-sections", "-o", str(exe)
    ], cwd=ROOT, check=True)
    subprocess.run([str(exe), str(build / "audio.f32")], cwd=build, check=True)

def rms(x):
    return float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2)))

def snr_db(ref, test):
    return 20.0 * math.log10(max(rms(ref), 1e-15) / max(rms(test - ref), 1e-15))

def feature_metrics(reference, target):
    """Compare resonant behaviour without requiring sample-perfect phase lock."""
    result = {}
    window = max(1, int(TARGET_RATE * 0.010))
    for channel, label in enumerate(("out", "aux")):
        r = reference[:, channel].astype(np.float64)
        t = target[:, channel].astype(np.float64)
        usable = min(len(r), len(t)) // window * window
        re = np.sqrt(np.mean(r[:usable].reshape(-1, window) ** 2, axis=1))
        te = np.sqrt(np.mean(t[:usable].reshape(-1, window) ** 2, axis=1))
        corr = float(np.corrcoef(re, te)[0, 1]) if len(re) > 2 else 0.0
        # 100 ms envelopes reduce sensitivity to individual beating cycles.
        # Also report the best bounded alignment so small onset offsets do not
        # masquerade as a change in the decay shape.
        coarse_window = max(1, int(TARGET_RATE * 0.100))
        coarse_count = usable // coarse_window
        max_lag = 0
        if coarse_count > 2:
            re_coarse = np.sqrt(np.mean(
                r[:coarse_count * coarse_window].reshape(-1, coarse_window) ** 2,
                axis=1))
            te_coarse = np.sqrt(np.mean(
                t[:coarse_count * coarse_window].reshape(-1, coarse_window) ** 2,
                axis=1))
            coarse_corr = float(np.corrcoef(re_coarse, te_coarse)[0, 1])
            # Search up to 5 seconds: several long-tail cases still hit the 2-second bound.
            max_lag = min(50, max(0, coarse_count // 10))
            aligned = []
            for lag in range(-max_lag, max_lag + 1):
                if lag < 0:
                    a, b = re_coarse[-lag:], te_coarse[:lag]
                elif lag > 0:
                    a, b = re_coarse[:-lag], te_coarse[lag:]
                else:
                    a, b = re_coarse, te_coarse
                if len(a) > 2 and np.std(a) > 1e-12 and np.std(b) > 1e-12:
                    aligned.append((float(np.corrcoef(a, b)[0, 1]), lag))
            best_coarse_corr, best_coarse_lag = (
                max(aligned, key=lambda item: item[0]) if aligned else (None, None))
        else:
            coarse_corr, best_coarse_corr, best_coarse_lag = None, None, None
        def t20(env):
            if not len(env) or np.max(env) <= 1e-12:
                return None
            peak = int(np.argmax(env))
            below = np.flatnonzero(env[peak:] <= np.max(env) * 0.1)
            return float((below[0] * window) / TARGET_RATE) if len(below) else None
        def peaks(x):
            if len(x) < 32 or np.max(np.abs(x)) <= 1e-12:
                return []
            freq, power = welch(x, fs=TARGET_RATE, nperseg=min(8192, len(x)))
            inds, _ = find_peaks(power)
            inds = [int(i) for i in inds if freq[i] >= 20.0]
            inds.sort(key=lambda i: power[i], reverse=True)
            return [float(freq[i]) for i in inds[:5]]
        rp, tp = peaks(r), peaks(t)
        result[label] = {
            "rms_ratio_target_to_reference": float(rms(t) / max(rms(r), 1e-12)),
            "envelope_correlation_10ms": corr,
            "envelope_correlation_100ms": coarse_corr,
            "envelope_correlation_100ms_best_lag": best_coarse_corr,
            "envelope_best_lag_100ms_max_search_seconds": (
                float(max_lag * coarse_window / TARGET_RATE)
                if max_lag else 0.0),
            "envelope_best_lag_100ms_seconds": (
                float(best_coarse_lag * coarse_window / TARGET_RATE)
                if best_coarse_lag is not None else None),
            "envelope_best_lag_100ms_boundary_hit": (
                bool(abs(best_coarse_lag) == max_lag)
                if best_coarse_lag is not None and max_lag > 0 else False),
            "reference_t20_seconds": t20(re),
            "target_t20_seconds": t20(te),
            "reference_top_peaks_hz": rp,
            "target_top_peaks_hz": tp,
        }
    return result

def load_segments(path):
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))

ref_audio = np.fromfile(WORK / "eurorack_48k/audio.f32", dtype=np.float32).reshape(-1, 2)
target_audio = np.fromfile(WORK / "fm1_codec_rate/audio.f32", dtype=np.float32).reshape(-1, 2)
ref_segments = load_segments(WORK / "eurorack_48k/segments.csv")
target_segments = load_segments(WORK / "fm1_codec_rate/segments.csv")
if len(ref_segments) != 75 or len(target_segments) != 75:
    raise SystemExit("Expected 75 aligned Rings test cases")
if [(s["model"], s["note"], s["profile"]) for s in ref_segments] != [
    (s["model"], s["note"], s["profile"]) for s in target_segments
]:
    raise SystemExit("48 kHz and target-rate segment manifests differ")

models = ["Modal", "Sympathetic Strings", "String",
          "FM Voice", "Quantized Sympathetic Strings"]
cases = []
all_reference = []
all_target = []
for sr, st in zip(ref_segments, target_segments):
    r0, rn = int(sr["start"]), int(sr["frames"])
    t0, tn = int(st["start"]), int(st["frames"])
    ref = ref_audio[r0:r0+rn]
    target = target_audio[t0:t0+tn]
    # Convert 48 kHz reference to the exact target timebase using polyphase
    # windowed-sinc resampling; compare equal-duration portions only.
    converted = resample_poly(ref, UP, DOWN, axis=0)
    count = min(len(converted), len(target))
    converted, target = converted[:count], target[:count]
    all_reference.append(converted)
    all_target.append(target)
    if count < int(0.95 * min(rn * UP / DOWN, tn)):
        raise SystemExit("Unexpected resampler alignment loss")
    cases.append({
        "model": int(sr["model"]), "note": int(sr["note"]),
        "profile": sr["profile"], "frames_compared": count,
        "snr_db": snr_db(converted, target),
        "rms_error": rms(target - converted),
        "reference_rms": rms(converted), "target_rms": rms(target),
        "peak_error": float(np.max(np.abs(target - converted))),
        "features": feature_metrics(converted, target),
    })

per_model = []
for model, label in enumerate(models):
    rows = [c for c in cases if c["model"] == model]
    worst = min(rows, key=lambda c: c["snr_db"])
    per_model.append({
        "model": label, "mean_snr_db": float(np.mean([c["snr_db"] for c in rows])),
        "worst_snr_db": worst["snr_db"], "worst_case": worst,
        "mean_rms_error": float(np.mean([c["rms_error"] for c in rows])),
    })

summary = {
    "reference_sample_rate_hz": REFERENCE_RATE,
    "target_sample_rate_hz": TARGET_RATE,
    "resampler_ratio": f"{UP}/{DOWN}",
    "comparison": "original-float Rings 48 kHz reference resampled to FM-1 codec rate vs original-float Rings rendered at FM-1 codec rate",
    "cases": len(cases), "models": models, "per_model": per_model,
    "overall_snr_db": snr_db(np.concatenate(all_reference), np.concatenate(all_target)),
    "note": "Waveform SNR is phase-sensitive and is not a perceptual pass/fail metric for resonant tails. Compare 10 ms RMS envelopes, decay T20, and dominant spectral peaks. The FM-1 rate is calculated from the current clock divider and still requires hardware measurement."
}
(OUT / "sample_rate_metrics.json").write_text(json.dumps(summary, indent=2) + "\n")
(OUT / "sample_rate_cases.json").write_text(json.dumps(cases, indent=2) + "\n")
print(json.dumps(summary, indent=2))
