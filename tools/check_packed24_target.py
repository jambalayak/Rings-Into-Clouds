#!/usr/bin/env python3
import os, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TC = pathlib.Path(os.environ.get("JIELI_TOOLCHAIN", pathlib.Path.home()/".jieli/toolchain"))
BIN = TC / "pi32v2/bin"
PATCH = ROOT / "build/upstream-dsp-compile/source-patches"
OUT = ROOT / "build/packed24-target-probe"
OUT.mkdir(parents=True, exist_ok=True)
CXX = BIN / "clang++"
OBJDUMP = TC / "common/bin/objdump"
if not CXX.is_file() or not OBJDUMP.is_file():
    raise SystemExit("JieLi clang++/objdump toolchain missing")

eur = ROOT / "third_party/eurorack"
orig = (eur / "rings/dsp/string.h").read_text()
needle = "typedef stmlib::DelayLine<float, kDelayLineSize> StringDelayLine;\ntypedef stmlib::DelayLine<float, kDelayLineSize / 2> StiffnessDelayLine;"
replacement = "typedef Q24DelayLine<kDelayLineSize> StringDelayLine;\ntypedef Q24DelayLine<kDelayLineSize / 2> StiffnessDelayLine;"
patched = orig.replace('#include "stmlib/stmlib.h"',
                       '#include "stmlib/stmlib.h"\n#include "rings/dsp/q24_delay_line.h"').replace(needle, replacement)
if patched == orig:
    raise SystemExit("Could not apply packed-24 String delay overlay")
(PATCH / "rings/dsp/q24_delay_line.h").write_text((ROOT / "tools/rings_delay_test/q24_delay_line.h").read_text())
(PATCH / "rings/dsp/string.h").write_text(patched)

common = [
    "-target", "pi32v2", "-mcpu=r3", "-mfprev1", os.environ.get("FELUCCA_CODE_OPT", "-Os"), "-std=gnu++11", "-DTEST",
    "-fno-math-errno", "-fno-exceptions", "-fno-rtti", "-fno-threadsafe-statics",
    "-fno-use-cxa-atexit", "-nostdinc++", "-ffunction-sections", "-fdata-sections",
    "-Wall", "-Wno-unused-function", "-Wno-unused-variable", "-Wno-unused-local-typedef",
    "-Wframe-larger-than=1024", "-Ibuild/upstream-dsp-compile/source-patches",
    "-Ifirmware/cxx", "-Ifirmware/sys", "-Ithird_party", "-Ithird_party/eurorack",
    "-isystem", str(TC / "pi32v2/include")
]
def run(args):
    p = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if p.stdout: print(p.stdout, end="")
    if p.stderr: print(p.stderr, end="", file=sys.stderr)
    if p.returncode: raise SystemExit("target packed-24 compile failed: " + " ".join(args[-4:]))

# Compile every Rings translation unit against the packed-24 delay overlay.
sources = sorted(set(list((eur / "rings/dsp").glob("*.cc")) + [eur / "rings/resources.cc"]))
sources = [PATCH / "rings/dsp/part.cc" if p.name == "part.cc" else p for p in sources]
sources = [p for p in sources if "string_synth" not in p.name]
for src in sources:
    rel = src.relative_to(ROOT)
    obj = OUT / (str(rel).replace("/", "__") + ".o")
    run([str(CXX), *common, "-c", str(rel), "-o", str(obj)])

# The existing float five-model target size probe is retained by the preceding
# check_upstream_dsp_compile.py step. Compile the same probe with packed-24.
probe = ROOT / "tools/cpp_smoke/size_probe_five_model.cc"
obj = OUT / "size_probe_packed24.o"
run([str(CXX), *common, "-c", str(probe.relative_to(ROOT)), "-o", str(obj)])

def symbols(path):
    p = subprocess.run([str(OBJDUMP), "-t", str(path)], cwd=ROOT, text=True, capture_output=True)
    if p.returncode: raise SystemExit("objdump failed: " + p.stderr)
    result = {}
    for line in p.stdout.splitlines():
        f = line.split()
        if len(f) >= 5 and f[-1].startswith("ric_five_size_"):
            result[f[-1]] = int(f[-2], 16)
    return result

float_obj = ROOT / "build/upstream-dsp-compile/size_probe_five_model.o"
if not float_obj.is_file():
    raise SystemExit("float five-model target size probe missing")
base, q24 = symbols(float_obj), symbols(obj)
required = {"ric_five_size_rings_part", "ric_five_size_rings_string",
            "ric_five_size_rings_strummer", "ric_five_size_clouds_processor"}
if required-base.keys() or required-q24.keys():
    raise SystemExit("missing size symbols: " + repr((required-base.keys(), required-q24.keys())))
for name in sorted(required):
    old, new = base[name], q24[name]
    print(f"TARGET SIZE {name}: float={old} packed24={new} saving={old-new}")
(OUT / "sizes.txt").write_text("\n".join(
    f"{name} float={base[name]} packed24={q24[name]} saving={base[name]-q24[name]}"
    for name in sorted(required)) + "\n")
