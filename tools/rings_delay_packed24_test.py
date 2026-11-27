#!/usr/bin/env python3
import csv, json, math, pathlib, subprocess, wave
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
EUR = ROOT / "third_party" / "eurorack"
STM = ROOT / "third_party" / "stmlib"
PATCH = ROOT / "build" / "upstream-dsp-compile" / "source-patches"
WORK = ROOT / "build" / "rings-delay-packed24-experiment"
OUT = WORK / "results"
OUT.mkdir(parents=True, exist_ok=True)

part_h = (PATCH / "rings/dsp/part.h").read_text()
part_cc = (PATCH / "rings/dsp/part.cc").read_text()
assert "STRING_AND_REVERB" not in part_h + part_cc
dsp_h = (EUR / "rings/dsp/dsp.h").read_text().replace("48000.0f", "44117.6470588f")
(PATCH / "rings/dsp").mkdir(parents=True, exist_ok=True)
(PATCH / "rings/dsp/dsp.h").write_text(dsp_h)

orig_string = (EUR / "rings/dsp/string.h").read_text()
needle = "typedef stmlib::DelayLine<float, kDelayLineSize> StringDelayLine;\ntypedef stmlib::DelayLine<float, kDelayLineSize / 2> StiffnessDelayLine;"
replacement = "typedef Q24DelayLine<kDelayLineSize> StringDelayLine;\ntypedef Q24DelayLine<kDelayLineSize / 2> StiffnessDelayLine;"
q24_string = orig_string.replace(
    '#include "stmlib/stmlib.h"',
    '#include "stmlib/stmlib.h"\n#include "rings/dsp/q24_delay_line.h"').replace(needle, replacement)
if q24_string == orig_string:
    raise SystemExit("Could not apply signed-16 delay typedef overlay")
(PATCH / "rings/dsp/string.h").write_text(orig_string)
(PATCH / "rings/dsp/q24_delay_line.h").write_text((ROOT / "tools/rings_delay_test/q24_delay_line.h").read_text())

sources = sorted(set(list((EUR / "rings/dsp").glob("*.cc")) + [EUR / "rings/resources.cc"] +
                         list((STM / "dsp").glob("*.cc")) + list((STM / "utils").glob("*.cc"))))
sources = [PATCH / "rings/dsp/part.cc" if p.name == "part.cc" else p for p in sources if "string_synth" not in p.name]
main = ROOT / "tools/rings_delay_test/main_q24.cc"
include = ["-I" + str(PATCH), "-I" + str(ROOT / "tools/rings_delay_test"),
           "-I" + str(ROOT / "third_party"),
           "-I" + str(EUR), "-I" + str(STM)]
common = ["g++", "-std=c++11", "-O2", "-D_GNU_SOURCE", "-DTEST", "-ffunction-sections", "-fdata-sections",
          "-Wno-unused-function", "-Wno-unused-variable", *include]
variants = [("float", None), ("packed24_q3_21", 2097152)]
for variant, scale in variants:
    build = WORK / variant
    build.mkdir(parents=True, exist_ok=True)
    objects = []
    extra = [] if scale is None else [[]]
    if scale is not None:
        (PATCH / "rings/dsp/string.h").write_text(q24_string)
    else:
        (PATCH / "rings/dsp/string.h").write_text(orig_string)
    for src in sources:
        obj = build / (str(src).replace("/", "__") + ".o")
        subprocess.run([*common, *extra, "-c", str(src), "-o", str(obj)], cwd=ROOT, check=True)
        objects.append(str(obj))
    exe = build / "rings_delay_test"
    subprocess.run([*common, *extra, str(main), *objects, "-Wl,--gc-sections", "-o", str(exe)], cwd=ROOT, check=True)
    subprocess.run([str(exe), str(build / "audio.f32")], cwd=build, check=True)
    stats = {}
    for line in (build / "delay_stats.txt").read_text().splitlines():
        k, v = line.split("=", 1); stats[k] = float(v)
    (build / "delay_stats.json").write_text(json.dumps(stats, indent=2) + "\n")

reference = np.fromfile(WORK / "float/audio.f32", dtype=np.float32).reshape(-1, 2)
def rms(x):
    return float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2)))
def snr_db(ref, test):
    err = rms(test-ref)
    return 20.0 * math.log10(max(rms(ref), 1e-15) / max(err, 1e-15))
summary = {"sample_rate_hz_exact": 24000000/544, "cases": 75, "models": [
    "Modal", "Sympathetic Strings", "String", "FM Voice", "Quantized Sympathetic Strings"],
    "notes_midi": [36,60,84], "profiles": ["neutral","dark","bright","long_decay","loud_external"],
    "variants": {}}
float_stats = json.loads((WORK / "float" / "delay_stats.json").read_text())
summary["float_reference_host_sizes"] = {
    "host_part_size_bytes": int(float_stats["part_size_bytes"]),
    "host_string_size_bytes": int(float_stats["string_size_bytes"]),
    "note": "Host g++ -O2 object sizes only; not FM-1 target RAM measurements."
}
for variant, scale in variants[1:]:
    rendered = np.fromfile(WORK / variant / "audio.f32", dtype=np.float32).reshape(-1, 2)
    segments = list(csv.DictReader(open(WORK / variant / "segments.csv", newline="")))
    stats = json.loads((WORK / variant / "delay_stats.json").read_text())
    per_model = []
    for model in range(5):
        rows = []
        for s in segments:
            if int(s["model"]) != model: continue
            start, count = int(s["start"]), int(s["frames"])
            x, y = reference[start:start+count], rendered[start:start+count]
            rows.append({"note":int(s["note"]), "profile":s["profile"],
                         "snr_db":snr_db(x,y), "rms_error":rms(y-x),
                         "reference_rms":rms(x), "variant_rms":rms(y),
                         "delay_saturation_count":int(s["saturation_count"]),
                         "max_abs_delay_value":float(s["max_abs_delay_value"])})
        per_model.append({"model":summary["models"][model],
                          "mean_snr_db":float(np.mean([r["snr_db"] for r in rows])),
                          "worst_snr_db":min(r["snr_db"] for r in rows),
                          "worst_case":min(rows,key=lambda r:r["snr_db"]),
                          "delay_saturation_count":sum(r["delay_saturation_count"] for r in rows),
                          "worst_saturation_case":max(rows,key=lambda r:r["delay_saturation_count"]),
                          "max_abs_delay_value":max(r["max_abs_delay_value"] for r in rows),
                          "cases":rows})
    summary["variants"][variant] = {
        "quantizer_scale":int(scale),
        "positive_full_scale":8388607.0/scale,
        "negative_full_scale":-8388608.0/scale,
        "host_part_size_bytes":int(stats["part_size_bytes"]),
        "host_string_size_bytes":int(stats["string_size_bytes"]),
                "overall_snr_db":snr_db(reference,rendered),
        "overall_rms_error":rms(rendered-reference),
        "peak":float(np.max(np.abs(rendered))),
        "output_samples_over_full_scale":int(np.count_nonzero(np.abs(rendered)>1.0)),
        "delay_saturation_count":int(stats["q24_saturation_count"]),
        "max_abs_delay_value":float(stats["q24_max_abs"]),
        "worst_saturation_case":max(
            [case for model in per_model for case in model["cases"]],
            key=lambda r:r["delay_saturation_count"]),
        "per_model":per_model}
    pcm = np.rint(np.clip(rendered,-1.0,1.0)*32767.0).astype("<i2")
    with wave.open(str(OUT / f"rings-{variant}.wav"),"wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(44118); w.writeframes(pcm.tobytes())
# Include float WAV from the same fixed conversion for direct listening comparison.
pcm = np.rint(np.clip(reference,-1.0,1.0)*32767.0).astype("<i2")
with wave.open(str(OUT / "rings-float-reference.wav"),"wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(44118); w.writeframes(pcm.tobytes())
(OUT / "metrics.json").write_text(json.dumps(summary, indent=2)+"\n")
print(json.dumps({k:v for k,v in summary.items() if k!="variants"},indent=2))
for name, v in summary["variants"].items():
    print(name, json.dumps({k:x for k,x in v.items() if k!="per_model"}))
