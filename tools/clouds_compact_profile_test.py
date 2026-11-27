#!/usr/bin/env python3
"""ASan/UBSan host validation and same-gain stock-vs-compact Clouds WAV render."""
import os
import pathlib
import shutil
import subprocess
import sys
import wave
import struct

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "clouds-compact-profile"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "tools"))
from clouds_compact_profile import apply_compact_profile

EUR = ROOT / "third_party" / "eurorack"
STM = ROOT / "third_party" / "stmlib"
if not (EUR / "clouds/dsp/granular_processor.cc").is_file():
    raise SystemExit("Pinned eurorack submodule is missing.")
if not (STM / "stmlib.h").is_file():
    raise SystemExit("Pinned stmlib submodule is missing.")

baseline_patch = OUT / "baseline-patch"
baseline_patch.mkdir(parents=True, exist_ok=True)
baseline_gp = (EUR / "clouds/dsp/granular_processor.cc").read_text()
debug_include = '#include "clouds/drivers/debug_pin.h"\n'
if baseline_gp.count(debug_include) != 1:
    raise SystemExit("Expected hardware-only Clouds debug pin include not found.")
(baseline_patch / "clouds/dsp").mkdir(parents=True, exist_ok=True)
(baseline_patch / "clouds/dsp/granular_processor.cc").write_text(
    baseline_gp.replace(debug_include, "", 1))

compact_patch = OUT / "compact-patch"
profile = apply_compact_profile(ROOT, compact_patch)
if profile["workspace_non_spectral"] != 41752:
    raise SystemExit("Unexpected non-Spectral workspace arithmetic.")
if profile["stereo_spectral_2048_per_channel"] != 32576:
    raise SystemExit("2048 stereo Spectral estimate changed.")
if profile["mono_spectral_4096"] != 81728:
    raise SystemExit("4096 mono Spectral estimate changed.")
(OUT / "allocation-proof.txt").write_text(
    "Pinned Clouds compact-profile allocation proof\n"
    f"Non-Spectral FX workspace: {profile['workspace_non_spectral']} B / 53,376 B\n"
    f"Stereo Spectral 2048 per channel: {profile['stereo_spectral_2048_per_channel']} B / 32,768 B\n"
    f"  = 20,480 B FFT/IFFT + analysis/synthesis + 12,096 B textures (2 usable + phase)\n"
    f"Mono Spectral 4096: {profile['mono_spectral_4096']} B / 86,144 B\n"
    "  = 57,344 B FFT + IFFT + analysis/synthesis + 24,384 B textures (2 usable + phase)\n"
    "  = 4,416 B remaining\n"
    "The 40,960 B stereo 4096 base allocation leaves no texture storage and is rejected.\n"
)

sources = set(EUR.glob("clouds/dsp/**/*.cc"))
sources.add(EUR / "clouds/resources.cc")
sources.update(STM.glob("dsp/*.cc"))
sources.update(STM.glob("utils/*.cc"))
sources = sorted(p for p in sources if p.is_file())
if not sources:
    raise SystemExit("No pinned Clouds/stmlib sources found.")

common = [
    os.environ.get("CXX", "g++"), "-std=c++11", "-DTEST", "-O1", "-g",
    "-fno-omit-frame-pointer", "-fsanitize=address,undefined",
    "-Wall", "-Wextra", "-Wno-unused-parameter", "-Wno-unused-variable",
    "-I", str(ROOT / "third_party"),
    "-I", str(ROOT / "third_party/eurorack"),
]
harness = ROOT / "tools" / "clouds_compact_profile_host.cc"

def build(name, patch, compact):
    binary = OUT / name
    command = [common[0], "-I", str(patch)] + common[1:]
    if compact:
        command += ["-DRIC_COMPACT_PROFILE=1"]
    command += [str(harness)]
    for source in sources:
        selected = source
        if source == EUR / "clouds/dsp/granular_processor.cc":
            selected = patch / "clouds/dsp/granular_processor.cc"
        elif compact and source == EUR / "clouds/dsp/pvoc/phase_vocoder.cc":
            selected = patch / "clouds/dsp/pvoc/phase_vocoder.cc"
        command.append(str(selected))
    command += ["-o", str(binary)]
    print("BUILD", name, flush=True)
    subprocess.run(command, cwd=ROOT, check=True)
    return binary

baseline = build("clouds-stock-host", baseline_patch, False)
compact = build("clouds-compact-host", compact_patch, True)

env = os.environ.copy()
env["ASAN_OPTIONS"] = "detect_leaks=0:halt_on_error=1"
env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
print("RUN compact matrix", flush=True)
subprocess.run([str(compact), "--self-test"], cwd=ROOT, env=env, check=True)

stock_wav = OUT / "stereo-spectral-stock-4096.wav"
compact_wav = OUT / "stereo-spectral-compact-2048.wav"
print("RENDER stock 4096", flush=True)
subprocess.run([str(baseline), "--render", str(stock_wav)], cwd=ROOT, env=env, check=True)
print("RENDER compact 2048", flush=True)
subprocess.run([str(compact), "--render", str(compact_wav)], cwd=ROOT, env=env, check=True)

def wav_stats(path):
    with wave.open(str(path), "rb") as f:
        params = f.getparams()
        raw = f.readframes(f.getnframes())
    values = struct.unpack("<" + "h" * (len(raw) // 2), raw)
    peak = max(abs(x) for x in values) if values else 0
    rms = (sum(x * x for x in values) / max(1, len(values))) ** 0.5
    if params.nchannels != 2 or params.sampwidth != 2 or params.framerate != 32000:
        raise SystemExit(f"Unexpected WAV format: {path} {params}")
    if peak == 0 or rms == 0:
        raise SystemExit(f"Silent WAV: {path}")
    return params.nframes, peak, rms

stock_stats = wav_stats(stock_wav)
compact_stats = wav_stats(compact_wav)
(OUT / "wav-comparison.txt").write_text(
    "Same-gain WAV comparison; no normalization or per-file gain adjustment.\n"
    "Both renders use identical 32 kHz stereo input, full-quality setting, dry/wet=1,\n"
    "feedback=0, reverb=0, pitch=0, density=0.5 and size/position=0.5.\n"
    f"Stock Spectral 4096: frames={stock_stats[0]} peak={stock_stats[1]} rms={stock_stats[2]:.3f}\n"
    f"Compact Spectral 2048: frames={compact_stats[0]} peak={compact_stats[1]} rms={compact_stats[2]:.3f}\n"
)
print("PASS host tests and WAV generation", flush=True)
