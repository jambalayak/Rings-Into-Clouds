#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Compile-only probe of removing Rings' external audio-input pathway.

The pinned submodules and production firmware sources are never modified.
The probe compares the existing five-model overlay with a temporary overlay
that removes the input pointer, input copy and input-thru bypass path.
"""
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TC = Path(os.environ.get("JIELI_TOOLCHAIN", Path.home() / ".jieli/toolchain"))
BIN = TC / "pi32v2/bin"
COMMON = TC / "common/bin"
BASE = ROOT / "build/upstream-dsp-compile/source-patches"
OUT = ROOT / "build/rings-no-input-probe"
NOINPUT = OUT / "source-patches"
DOCKER_IMAGE = os.environ.get("JIELI_DOCKER_IMAGE", "debian:bookworm-slim")


def run(args):
    p = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if p.stdout:
        print(p.stdout, end="")
    if p.stderr:
        print(p.stderr, end="", file=sys.stderr)
    if p.returncode:
        raise SystemExit("no-external-input compile probe failed: " + " ".join(map(str, args[-5:])))


def compile_target(src, obj, includes, flags):
    compiler = BIN / "clang++"
    if not compiler.is_file():
        raise SystemExit("missing target clang++")
    args = [str(compiler), *flags, *["-I" + str(p) for p in includes],
            "-c", str(src.relative_to(ROOT)), "-o", str(obj.relative_to(ROOT))]
    run(args)


def text_bytes(obj):
    p = subprocess.run([str(COMMON / "objdump"), "-h", str(obj.relative_to(ROOT))],
                       cwd=ROOT, text=True, capture_output=True)
    if p.returncode:
        raise SystemExit("objdump -h failed: " + p.stderr)
    total = 0
    for line in p.stdout.splitlines():
        f = line.split()
        if len(f) >= 3 and f[1].startswith(".text"):
            try:
                total += int(f[2], 16)
            except ValueError:
                pass
    return total


def main():
    if not (BASE / "rings/dsp/part.h").is_file() or not (BASE / "rings/dsp/part.cc").is_file():
        raise SystemExit("five-model baseline overlay missing; run check_upstream_dsp_compile.py first")
    if not (COMMON / "objdump").is_file():
        raise SystemExit("missing target objdump")
    OUT.mkdir(parents=True, exist_ok=True)
    (NOINPUT / "rings/dsp").mkdir(parents=True, exist_ok=True)
    part_h = (BASE / "rings/dsp/part.h").read_text()
    part_cc = (BASE / "rings/dsp/part.cc").read_text()

    old_decl = """  void Process(
      const PerformanceState& performance_state,
      const Patch& patch,
      const float* in,
      float* out,"""
    new_decl = """  void Process(
      const PerformanceState& performance_state,
      const Patch& patch,
      float* out,"""
    if old_decl not in part_h:
        raise SystemExit("expected five-model Part::Process declaration not found")
    part_h = part_h.replace(old_decl, new_decl, 1)

    old_def = """    const PerformanceState& performance_state,
    const Patch& patch,
    const float* in,
    float* out,"""
    new_def = """    const PerformanceState& performance_state,
    const Patch& patch,
    float* out,"""
    if old_def not in part_cc:
        raise SystemExit("expected five-model Part::Process definition not found")
    part_cc = part_cc.replace(old_def, new_def, 1)

    old_bypass = """  if (bypass_) {
    copy(&in[0], &in[size], &out[0]);
    copy(&in[0], &in[size], &aux[0]);
    return;
  }"""
    new_bypass = """  if (bypass_) {
    fill(&out[0], &out[size], 0.0f);
    fill(&aux[0], &aux[size], 0.0f);
    return;
  }"""
    if old_bypass not in part_cc:
        raise SystemExit("expected input-thru bypass block not found")
    part_cc = part_cc.replace(old_bypass, new_bypass, 1)

    old_copy = """    if (voice == active_voice_) {
      copy(&in[0], &in[size], &resonator_input_[0]);
    } else {
      fill(&resonator_input_[0], &resonator_input_[size], 0.0f);
    }"""
    new_copy = """    fill(&resonator_input_[0], &resonator_input_[size], 0.0f);"""
    if old_copy not in part_cc:
        raise SystemExit("expected active-voice external input copy not found")
    part_cc = part_cc.replace(old_copy, new_copy, 1)
    if re.search(r"\bin\b", part_cc[part_cc.index("void Part::Process("):]):
        raise SystemExit("external input identifier remains in Part::Process")

    (NOINPUT / "rings/dsp/part.h").write_text(part_h)
    (NOINPUT / "rings/dsp/part.cc").write_text(part_cc)

    # The C ABI wrapper is also compiled in both forms. This is a temporary
    # compile-only copy; no firmware source or exported product ABI is changed.
    abi_h = (ROOT / "firmware/src/rings_clouds_abi.h").read_text()
    abi_cc = (ROOT / "firmware/cxx/rings_clouds_abi.cc").read_text()
    old_proto = "void ric_rings_process(const void *performance_state, const void *patch,\n                       const float *input, float *out, float *aux, uint32_t frames);"
    new_proto = "void ric_rings_process(const void *performance_state, const void *patch,\n                       float *out, float *aux, uint32_t frames);"
    old_abi_sig = 'extern "C" void ric_rings_process(const void *performance_state, const void *patch,\n                                  const float *input, float *out, float *aux, uint32_t frames)'
    new_abi_sig = 'extern "C" void ric_rings_process(const void *performance_state, const void *patch,\n                                  float *out, float *aux, uint32_t frames)'
    old_call = """    rings_part()->Process(*static_cast<const rings::PerformanceState *>(performance_state),
                          *static_cast<const rings::Patch *>(patch),
                          input, out, aux, frames);"""
    new_call = """    rings_part()->Process(*static_cast<const rings::PerformanceState *>(performance_state),
                          *static_cast<const rings::Patch *>(patch),
                          out, aux, frames);"""
    if old_proto not in abi_h or old_abi_sig not in abi_cc or old_call not in abi_cc:
        raise SystemExit("expected baseline C ABI input signature/call not found")
    abi_h_new = abi_h.replace(old_proto, new_proto, 1)
    abi_cc_new = abi_cc.replace(old_abi_sig, new_abi_sig, 1).replace(old_call, new_call, 1)
    (NOINPUT / "rings_clouds_abi.h").write_text(abi_h_new)
    (OUT / "rings_clouds_abi.cc").write_text(abi_cc_new)

    opt = os.environ.get("FELUCCA_CODE_OPT", "-Oz")
    flags = ["-target", "pi32v2", "-mcpu=r3", "-mfprev1", opt, "-std=gnu++11", "-DTEST",
             "-fno-math-errno", "-fno-exceptions", "-fno-rtti", "-fno-threadsafe-statics",
             "-fno-use-cxa-atexit", "-nostdinc++", "-ffunction-sections", "-fdata-sections",
             "-Wall", "-Wno-unused-function", "-Wno-unused-variable", "-Wno-unused-local-typedef",
             "-Wframe-larger-than=1024"]
    sysinc = ("/opt/jieli/pi32v2/include" if os.environ.get("JIELI_DOCKER", "0") == "1"
              else str(TC / "pi32v2/include"))
    flags += ["-isystem", sysinc]

    # Compile baseline and no-input Part + ABI objects with identical flags.
    baseline_includes = [BASE, ROOT / "firmware/src", ROOT / "firmware/cxx",
                         ROOT / "firmware/sys", ROOT / "third_party", ROOT / "third_party/eurorack"]
    noinput_includes = [NOINPUT, BASE, ROOT / "firmware/src", ROOT / "firmware/cxx",
                        ROOT / "firmware/sys", ROOT / "third_party", ROOT / "third_party/eurorack"]
    baseline_part = BASE / "rings/dsp/part.cc"
    noinput_part = NOINPUT / "rings/dsp/part.cc"
    baseline_abi = ROOT / "firmware/cxx/rings_clouds_abi.cc"
    noinput_abi = OUT / "rings_clouds_abi.cc"

    objects = {}
    for label, src, inc in (
        ("baseline_part", baseline_part, baseline_includes),
        ("noinput_part", noinput_part, noinput_includes),
        ("baseline_abi", baseline_abi, baseline_includes),
        ("noinput_abi", noinput_abi, noinput_includes),
    ):
        obj = OUT / (label + ".o")
        compile_target(src, obj, inc, flags)
        objects[label] = obj

    baseline = text_bytes(objects["baseline_part"]) + text_bytes(objects["baseline_abi"])
    noinput = text_bytes(objects["noinput_part"]) + text_bytes(objects["noinput_abi"])
    part_base = text_bytes(objects["baseline_part"])
    part_new = text_bytes(objects["noinput_part"])
    abi_base = text_bytes(objects["baseline_abi"])
    abi_new = text_bytes(objects["noinput_abi"])
    report = [
        "Rings external-input removal: compile-only target object comparison",
        f"Optimization: {opt}; target: pi32v2; same flags for both variants",
        "Scope: five-model Part::Process plus C ABI wrapper; no link, runtime, audio or installable image",
        f"Part .text baseline: {part_base} B",
        f"Part .text no-input: {part_new} B",
        f"Part .text saving: {part_base-part_new} B",
        f"C ABI .text baseline: {abi_base} B",
        f"C ABI .text no-input: {abi_new} B",
        f"C ABI .text saving: {abi_base-abi_new} B",
        f"Combined .text baseline: {baseline} B",
        f"Combined .text no-input: {noinput} B",
        f"Combined .text saving: {baseline-noinput} B",
        "Part object size/layout is unchanged by this method-only probe; no class data members were removed.",
        "Internal Modal/FM/String excitation code is retained; only external input copy/thru is removed.",
        "No claim of bit-exactness or cycle improvement: this changes behavior for non-zero external input by design.",
    ]
    (OUT / "report.txt").write_text("\n".join(report) + "\n")
    print("\n".join(report))


if __name__ == "__main__":
    main()
