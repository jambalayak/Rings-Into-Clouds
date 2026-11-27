#!/usr/bin/env python3
import csv, json, math, pathlib, subprocess, wave
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
EUR = ROOT / "third_party" / "eurorack"
STM = ROOT / "third_party" / "stmlib"
PATCH = ROOT / "build" / "upstream-dsp-compile" / "source-patches"
WORK = ROOT / "build" / "rings-delay-polyphonic-stress"
OUT = WORK / "results"
OUT.mkdir(parents=True, exist_ok=True)

part_h = (PATCH / "rings/dsp/part.h").read_text()
part_cc = (PATCH / "rings/dsp/part.cc").read_text()
assert "STRING_AND_REVERB" not in part_h + part_cc
dsp_h = (EUR / "rings/dsp/dsp.h").read_text().replace("48000.0f", "44117.6470588f")
(PATCH / "rings/dsp/dsp.h").write_text(dsp_h)
orig = (EUR / "rings/dsp/string.h").read_text()
needle = "typedef stmlib::DelayLine<float, kDelayLineSize> StringDelayLine;\ntypedef stmlib::DelayLine<float, kDelayLineSize / 2> StiffnessDelayLine;"
replacement = "typedef QNDelayLine<kDelayLineSize> StringDelayLine;\ntypedef QNDelayLine<kDelayLineSize / 2> StiffnessDelayLine;"
qn = orig.replace('#include "stmlib/stmlib.h"',
                  '#include "stmlib/stmlib.h"\n#include "rings/dsp/qn_delay_line.h"').replace(needle, replacement)
if qn == orig:
    raise SystemExit("Could not patch Rings delay typedefs")
(PATCH / "rings/dsp").mkdir(parents=True, exist_ok=True)
(PATCH / "rings/dsp/qn_delay_line.h").write_text((ROOT / "tools/rings_delay_test/qn_delay_line.h").read_text())
sources = sorted(set(list((EUR / "rings/dsp").glob("*.cc")) + [EUR / "rings/resources.cc"] +
                         list((STM / "dsp").glob("*.cc")) + list((STM / "utils").glob("*.cc"))))
sources = [PATCH / "rings/dsp/part.cc" if p.name == "part.cc" else p for p in sources if "string_synth" not in p.name]
main = ROOT / "tools/rings_delay_test/main_poly.cc"
include = ["-I" + str(PATCH), "-I" + str(ROOT / "tools/rings_delay_test"),
           "-I" + str(ROOT / "third_party"), "-I" + str(EUR), "-I" + str(STM)]
common = ["g++", "-std=c++11", "-O2", "-D_GNU_SOURCE", "-DTEST", "-ffunction-sections", "-fdata-sections",
          "-Wno-unused-function", "-Wno-unused-variable", *include]
variants = [("float", None), ("q275", 11915), ("q300", 10922), ("q313", 8192), ("q412", 4096), ("q511", 2048)]
for name, scale in variants:
    build = WORK / name
    build.mkdir(parents=True, exist_ok=True)
    (PATCH / "rings/dsp/string.h").write_text(orig if scale is None else qn)
    extra = [] if scale is None else [f"-DRINGS_DELAY_SCALE={scale}"]
    objects = []
    for src in sources:
        obj = build / (str(src).replace("/", "__") + ".o")
        subprocess.run([*common, *extra, "-c", str(src), "-o", str(obj)], cwd=ROOT, check=True)
        objects.append(str(obj))
    exe = build / "rings_poly_test"
    subprocess.run([*common, *extra, str(main), *objects, "-Wl,--gc-sections", "-o", str(exe)], cwd=ROOT, check=True)
    subprocess.run([str(exe), str(build / "audio.f32")], cwd=build, check=True)

def rms(x):
    return float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2)))
def snr(a, b):
    return 20.0 * math.log10(max(rms(a), 1e-15) / max(rms(a-b), 1e-15))

reference = np.fromfile(WORK / "float/audio.f32", dtype=np.float32).reshape(-1, 2)
ref_segments = list(csv.DictReader(open(WORK / "float/segments.csv", newline="")))
models = ["Modal", "Sympathetic Strings", "String", "FM Voice", "Quantized Sympathetic Strings"]
summary = {
    "test": "Mono (one strum) and Quad (four overlapping strums) Rings Part stress; no Clouds processing",
    "models": models, "profiles": ["neutral", "bright", "long_decay"],
    "configurations": [{"name":"Mono","polyphony":1,"notes_midi":[36]},{"name":"Quad","polyphony":4,"notes_midi":[36,48,60,72]}], "cases": 30,
    "variants": {}
}
for name, scale in variants[1:]:
    rendered = np.fromfile(WORK / name / "audio.f32", dtype=np.float32).reshape(-1, 2)
    segs = list(csv.DictReader(open(WORK / name / "segments.csv", newline="")))
    stats = {}
    for line in (WORK / name / "delay_stats.txt").read_text().splitlines():
        k, v = line.split("=", 1); stats[k] = float(v)
    rows = []
    for a, b in zip(ref_segments, segs):
        start, count = int(a["start"]), int(a["frames"])
        x, y = reference[start:start+count], rendered[start:start+count]
        rows.append({"model": int(a["model"]), "profile": a["profile"], "polyphony": int(a["polyphony"]),
                     "strums": int(a["strums"]), "snr_db": snr(x, y), "rms_error": rms(y-x),
                     "saturation_count": int(b["saturation_count"]),
                     "max_abs_delay_value": float(b["max_abs_delay_value"])})
    per_model = []
    for i, model_name in enumerate(models):
        cases = [r for r in rows if r["model"] == i]
        per_model.append({"model": model_name, "mean_snr_db": float(np.mean([r["snr_db"] for r in cases])),
                          "worst_snr_db": min(r["snr_db"] for r in cases),
                          "worst_case": min(cases, key=lambda r: r["snr_db"]),
                          "saturation_count": sum(r["saturation_count"] for r in cases)})
    summary["variants"][name] = {
        "quantizer_scale": int(scale), "positive_full_scale": 32767.0/scale,
        "negative_full_scale": -32768.0/scale, "overall_snr_db": snr(reference, rendered),
        "overall_rms_error": rms(rendered-reference), "saturation_count": int(stats["qn_saturation_count"]),
        "max_abs_delay_value": stats["qn_max_abs"], "host_part_size_bytes": int(stats["part_size_bytes"]),
        "host_string_size_bytes": int(stats["string_size_bytes"]), "per_model": per_model, "cases_detail": rows
    }
    pcm = np.rint(np.clip(rendered, -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(str(OUT / f"rings-poly-{name}.wav"), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(44118); w.writeframes(pcm.tobytes())
pcm = np.rint(np.clip(reference, -1.0, 1.0) * 32767.0).astype("<i2")
with wave.open(str(OUT / "rings-poly-float-reference.wav"), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(44118); w.writeframes(pcm.tobytes())
summary["limitations"] = [
    "Host g++ -O2 only; not FM-1 target RAM or CPU measurements.",
    "Mono uses one note; Quad uses four overlapping notes in one Rings Part. FM-1 allocator voice routing is not exercised.",
    "Clouds, resampling, MIDI, voice stealing and physical hardware are not exercised."
]
(OUT / "metrics.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
