#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Compile pinned Rings/Clouds/stmlib translation units for the FM-1 target only.

No DSP objects are constructed and no audio path or firmware memory is changed.
"""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLCHAIN = Path(os.environ.get("JIELI_TOOLCHAIN", Path.home() / ".jieli/toolchain")).expanduser()
BIN = TOOLCHAIN / "pi32v2" / "bin"
DOCKER_IMAGE = os.environ.get("JIELI_DOCKER_IMAGE", "debian:bookworm-slim")
BUILD = ROOT / "build" / "upstream-dsp-compile"


def invoke(args):
    docker = os.environ.get("JIELI_DOCKER", "0" if platform.system() == "Linux" and platform.machine() in ("x86_64", "AMD64") else "1") == "1"
    if docker:
        if not shutil.which("docker"):
            raise SystemExit("Docker is required for the target compiler on this host.")
        cmd = ["docker", "run", "--rm", "--platform", "linux/amd64",
               "-v", f"{ROOT}:/work", "-v", f"{TOOLCHAIN}:/opt/jieli:ro",
               "-w", "/work", DOCKER_IMAGE, "/opt/jieli/pi32v2/bin/clang++", *args]
    else:
        cmd = [str(BIN / "clang++"), *args]
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode:
        raise SystemExit(f"upstream DSP compile failed: {cmd[-1]}")


def main():
    if not (BIN / "clang++").is_file():
        raise SystemExit(f"Missing target C++ compiler: {BIN / 'clang++'}")
    eur = ROOT / "third_party" / "eurorack"
    stm = ROOT / "third_party" / "stmlib"
    if not (eur / "rings/dsp/part.cc").is_file() or not (stm / "stmlib.h").is_file():
        raise SystemExit("Pinned Rings/Clouds and stmlib submodules were not checked out.")
    sources = []
    for pattern in (
        "rings/dsp/*.cc", "rings/resources.cc",
        "clouds/dsp/**/*.cc", "clouds/resources.cc",
        "dsp/*.cc", "utils/*.cc",
    ):
        root = eur if pattern.startswith(("rings/", "clouds/")) else stm
        sources.extend(root.glob(pattern))
    sources = sorted(p for p in set(sources) if "string_synth" not in p.name)
    if not sources:
        raise SystemExit("No pinned DSP translation units found.")

    # Apply reviewed FM-1 source overlays without modifying either pinned submodule.
    patch_root = BUILD / "source-patches"

    # The STM32 debug-pin include is unused by the DSP and has no FM-1 equivalent.
    clouds_original = eur / "clouds/dsp/granular_processor.cc"
    clouds_patched = patch_root / "clouds/dsp/granular_processor.cc"
    clouds_patched.parent.mkdir(parents=True, exist_ok=True)
    clouds_text = clouds_original.read_text()
    debug_include = '#include "clouds/drivers/debug_pin.h"'
    if debug_include not in clouds_text:
        raise SystemExit("expected upstream Clouds debug-pin include was not found")
    clouds_patched.write_text("\n".join(line for line in clouds_text.splitlines() if line.strip() != debug_include) + "\n")

    # Product-approved scope: five Rings models only. Remove the sixth String-and-Reverb
    # model and its embedded Reverb member; do not pass NULL or reserve a dummy 64 KiB buffer.
    part_h_original = eur / "rings/dsp/part.h"
    part_cc_original = eur / "rings/dsp/part.cc"
    part_h_patched = patch_root / "rings/dsp/part.h"
    part_cc_patched = patch_root / "rings/dsp/part.cc"
    part_h_patched.parent.mkdir(parents=True, exist_ok=True)
    part_h = part_h_original.read_text()
    for line in (
        '#include "rings/dsp/fx/reverb.h"',
        "  RESONATOR_MODEL_STRING_AND_REVERB,",
        "  Reverb reverb_;",
    ):
        if line not in part_h.splitlines():
            raise SystemExit("expected upstream Rings Part header line not found: " + line)
    part_h = "\n".join(line for line in part_h.splitlines()
                       if line not in (
                           '#include "rings/dsp/fx/reverb.h"',
                           "  RESONATOR_MODEL_STRING_AND_REVERB,",
                           "  Reverb reverb_;",
                       )) + "\n"
    signature = "  void Init(uint16_t* reverb_buffer);"
    if signature not in part_h:
        raise SystemExit("expected upstream Rings Init declaration not found")
    part_h_patched.write_text(part_h.replace(signature, "  void Init();"))

    part_cc = part_cc_original.read_text()
    part_cc = part_cc.replace("void Part::Init(uint16_t* reverb_buffer) {", "void Part::Init() {")
    lines = part_cc.splitlines()
    lines = [line for line in lines if line.strip() not in (
        "reverb_.Init(reverb_buffer);",
        "case RESONATOR_MODEL_STRING_AND_REVERB:",
        "1.4f,  // RESONATOR_MODEL_STRING_AND_REVERB",
    )]
    part_cc = "\n".join(lines) + "\n"
    has_dispersion_old = (
        "bool has_dispersion = model_ == RESONATOR_MODEL_STRING || " + chr(92) +
        "\n              model_ == RESONATOR_MODEL_STRING_AND_REVERB;"
    )
    if has_dispersion_old not in part_cc:
        raise SystemExit("expected Rings String dispersion selector not found")
    part_cc = part_cc.replace(has_dispersion_old, "bool has_dispersion = model_ == RESONATOR_MODEL_STRING;")
    damping_block = (
        "    if (model_ == RESONATOR_MODEL_STRING_AND_REVERB) {\n"
        "      damping *= (2.0f - damping);\n"
        "    }\n"
    )
    if damping_block not in part_cc:
        raise SystemExit("expected Rings String-and-Reverb damping block not found")
    part_cc = part_cc.replace(damping_block, "")
    reverb_block = """  if (model_ == RESONATOR_MODEL_STRING_AND_REVERB) {
    for (size_t i = 0; i < size; ++i) {
      float l = out[i];
      float r = aux[i];
      out[i] = l * patch.position + (1.0f - patch.position) * r;
      aux[i] = r * patch.position + (1.0f - patch.position) * l;
    }
    reverb_.set_amount(0.1f + patch.damping * 0.5f);
    reverb_.set_diffusion(0.625f);
    reverb_.set_time(0.35f + 0.63f * patch.damping);
    reverb_.set_input_gain(0.2f);
    reverb_.set_lp(0.3f + patch.brightness * 0.6f);
    reverb_.Process(out, aux, size);
    for (size_t i = 0; i < size; ++i) {
      aux[i] = -aux[i];
    }
  }
"""
    if reverb_block not in part_cc:
        raise SystemExit("expected Rings String-and-Reverb processing block not found")
    part_cc = part_cc.replace(reverb_block, "")
    if "RESONATOR_MODEL_STRING_AND_REVERB" in part_cc or "reverb_" in part_cc:
        raise SystemExit("Rings Reverb references remain in five-model source overlay")
    part_cc_patched.write_text(part_cc)

    sources = [clouds_patched if p == clouds_original else
               part_cc_patched if p == part_cc_original else p for p in sources]
    BUILD.mkdir(parents=True, exist_ok=True)
    common = [
        "-target", "pi32v2", "-mcpu=r3", "-mfprev1", "-Os", "-std=gnu++11", "-DTEST",
        "-fno-math-errno", "-fno-exceptions", "-fno-rtti", "-fno-threadsafe-statics",
        "-fno-use-cxa-atexit", "-nostdinc++", "-ffunction-sections", "-fdata-sections",
        "-Wall", "-Wno-unused-function", "-Wno-unused-variable", "-Wno-unused-local-typedef",
        "-Wframe-larger-than=1024", "-Ibuild/upstream-dsp-compile/source-patches", "-Ifirmware/cxx", "-Ifirmware/sys",
        "-Ithird_party", "-Ithird_party/eurorack",
        "-isystem", "/opt/jieli/pi32v2/include" if os.environ.get("JIELI_DOCKER", "0") == "1" else str(TOOLCHAIN / "pi32v2/include"),
    ]
    for src in sources:
        rel = src.relative_to(ROOT)
        obj = BUILD / (str(rel).replace("/", "__") + ".o")
        obj.parent.mkdir(parents=True, exist_ok=True)
        invoke([*common, "-c", str(rel), "-o", str(obj.relative_to(ROOT))])
    # Measure both the untouched six-model upstream class and the five-model FM-1 overlay.
    # Each probe is compile-time symbol extent only; neither constructs a DSP object.
    upstream_size_src = ROOT / "tools" / "cpp_smoke" / "size_probe.cc"
    upstream_size_obj = BUILD / "size_probe_upstream.o"
    upstream_common = [x for x in common if x != "-Ibuild/upstream-dsp-compile/source-patches"]
    invoke([*upstream_common, "-c", str(upstream_size_src.relative_to(ROOT)),
            "-o", str(upstream_size_obj.relative_to(ROOT))])

    five_size_src = ROOT / "tools" / "cpp_smoke" / "size_probe_five_model.cc"
    five_size_obj = BUILD / "size_probe_five_model.o"
    invoke([*common, "-c", str(five_size_src.relative_to(ROOT)),
            "-o", str(five_size_obj.relative_to(ROOT))])

    docker = os.environ.get("JIELI_DOCKER", "0" if platform.system() == "Linux" and platform.machine() in ("x86_64", "AMD64") else "1") == "1"
    if docker:
        dump_prefix = ["docker", "run", "--rm", "--platform", "linux/amd64",
                       "-v", f"{ROOT}:/work", "-v", f"{TOOLCHAIN}:/opt/jieli:ro",
                       "-w", "/work", DOCKER_IMAGE, "/opt/jieli/common/bin/objdump", "-t"]
    else:
        dump_prefix = [str(TOOLCHAIN / "common/bin/objdump"), "-t"]
    sizes = {}
    wanted = {
        "ric_upstream_size_rings_part", "ric_upstream_size_rings_string",
        "ric_upstream_size_rings_strummer", "ric_upstream_size_clouds_processor",
        "ric_five_size_rings_part", "ric_five_size_rings_string",
        "ric_five_size_rings_strummer", "ric_five_size_clouds_processor",
    }
    for obj in (upstream_size_obj, five_size_obj):
        dumped = subprocess.run([*dump_prefix, str(obj.relative_to(ROOT))],
                                cwd=ROOT, text=True, capture_output=True)
        if dumped.returncode:
            sys.stderr.write(dumped.stdout + dumped.stderr)
            raise SystemExit("could not read target DSP sizeof symbols")
        for line in dumped.stdout.splitlines():
            fields = line.split()
            if len(fields) >= 5 and fields[-1] in wanted:
                sizes[fields[-1]] = int(fields[-2], 16)
    missing = wanted - sizes.keys()
    if missing:
        raise SystemExit("missing target sizeof symbols: " + ", ".join(sorted(missing)))
    for name in sorted(sizes):
        print(f"TARGET SIZE {name}: {sizes[name]} bytes")

    print(f"PASS: compiled {len(sources)} pinned Rings/Clouds/stmlib C++ translation units for pi32v2.")
    print("Compile-only: no DSP objects are constructed, linked into firmware, or run.")
    

if __name__ == "__main__":
    main()
