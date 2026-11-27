#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Verify and size the pinned upstream float Rings delay storage for a diagnostic link."""
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TC = pathlib.Path(os.environ.get("JIELI_TOOLCHAIN", pathlib.Path.home()/".jieli/toolchain"))
OBJDUMP = TC / "common/bin/objdump"
EUR = ROOT / "third_party/eurorack"
PATCH = ROOT / "build/upstream-dsp-compile/source-patches/rings/dsp"
OUT = ROOT / "build/float-delay-target-probe"
OUT.mkdir(parents=True, exist_ok=True)

original = (EUR / "rings/dsp/string.h").read_text()
expected = ("typedef stmlib::DelayLine<float, kDelayLineSize> StringDelayLine;\n"
            "typedef stmlib::DelayLine<float, kDelayLineSize / 2> StiffnessDelayLine;")
if expected not in original or "Q24DelayLine" in original:
    raise SystemExit("Pinned upstream Rings string.h is not the expected float-delay source.")
overlay = PATCH / "string.h"
if overlay.exists():
    raise SystemExit("Unexpected string.h overlay exists; refusing a mixed float/Q24 build.")
q24 = PATCH / "q24_delay_line.h"
if q24.exists():
    raise SystemExit("Unexpected Q24 delay header exists; refusing a mixed float/Q24 build.")

probe = ROOT / "build/upstream-dsp-compile/size_probe_five_model.o"
if not probe.is_file() or not OBJDUMP.is_file():
    raise SystemExit("Missing upstream float size probe or target objdump.")
p = subprocess.run([str(OBJDUMP), "-t", str(probe)], cwd=ROOT, text=True, capture_output=True)
if p.returncode:
    raise SystemExit("objdump failed: " + p.stderr)
wanted = {"ric_five_size_rings_part", "ric_five_size_rings_string",
          "ric_five_size_rings_strummer", "ric_five_size_clouds_processor"}
sizes = {}
for line in p.stdout.splitlines():
    fields = line.split()
    if len(fields) >= 5 and fields[-1] in wanted:
        sizes[fields[-1]] = int(fields[-2], 16)
if wanted - sizes.keys():
    raise SystemExit("Missing float target size symbols: " + ", ".join(sorted(wanted - sizes.keys())))
report = [
    "RINGS INTO CLOUDS upstream float-delay diagnostic",
    "Rings delay arrays: pinned upstream float; no Q24 overlay",
    "Clouds sine tables: pinned upstream tables; stride-4 sine fold is not applied",
    "Rings five-model scope: unchanged; String-and-Reverb model excluded",
]
for name in sorted(sizes):
    report.append(f"{name}: {sizes[name]} bytes (upstream float)")
(OUT / "sizes.txt").write_text("\n".join(report) + "\n")
print("\n".join(report))
