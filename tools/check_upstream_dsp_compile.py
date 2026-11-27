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

    # Compile the upstream Marbles DSP separately for target sizing. It is deliberately
    # not added to the Rings/Clouds link manifest yet: no sequencer behaviour is connected.
    marbles_sources = sorted(set([
        * (eur / "marbles" / "random").glob("*.cc"),
        * (eur / "marbles" / "ramp").glob("*.cc"),
        eur / "marbles" / "resources.cc",
    ]))
    if not sources:
        raise SystemExit("No pinned DSP translation units found.")
    if not marbles_sources:
        raise SystemExit("No pinned Marbles DSP translation units found.")

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

    # The pinned stmlib header contains ARM/NEON inline assembly (ssat/usat/vsqrt),
    # which is not valid for the FM-1 pi32v2 target. Use the same saturating C and
    # sqrtf implementations already used by upstream's TEST branch; this preserves
    # numerical semantics while making the production target translation units valid.
    stmlib_dsp_original = ROOT / "third_party" / "stmlib" / "dsp" / "dsp.h"
    stmlib_dsp_patched = patch_root / "stmlib" / "dsp" / "dsp.h"
    stmlib_dsp_patched.parent.mkdir(parents=True, exist_ok=True)
    stmlib_dsp = stmlib_dsp_original.read_text()
    clip_start = stmlib_dsp.find("#ifdef TEST\n  inline int32_t Clip16")
    sqrt_start = stmlib_dsp.find("#ifdef TEST\n  inline float Sqrt", clip_start)
    end_marker = "\n\ninline int16_t SoftConvert"
    block_end = stmlib_dsp.find(end_marker, sqrt_start)
    if clip_start < 0 or sqrt_start < 0 or block_end < 0:
        raise SystemExit("expected pinned stmlib Clip16/ClipU16/Sqrt implementations were not found")
    portable_clip_sqrt = """  inline int32_t Clip16(int32_t x) {
    if (x < -32768) {
      return -32768;
    } else if (x > 32767) {
      return 32767;
    } else {
      return x;
    }
  }
  inline uint32_t ClipU16(int32_t x) {
    if (x < 0) {
      return 0;
    } else if (x > 65535) {
      return 65535;
    } else {
      return static_cast<uint32_t>(x);
    }
  }
  inline float Sqrt(float x) {
    return sqrtf(x);
  }"""
    stmlib_dsp = stmlib_dsp[:clip_start] + portable_clip_sqrt + stmlib_dsp[block_end:]
    stmlib_dsp_patched.write_text(stmlib_dsp)

    # The FM-1 target's -nostdinc++ environment does not provide std::upper_bound.
    # Replace this one standard-library call with an equivalent local binary search.
    marbles_dist_original = eur / "marbles" / "random" / "distributions.h"
    marbles_dist_patched = patch_root / "marbles" / "random" / "distributions.h"
    marbles_dist_patched.parent.mkdir(parents=True, exist_ok=True)
    marbles_dist = marbles_dist_original.read_text()
    upper_bound_call = "int n = std::upper_bound(&cdf_[1], &cdf_[num_tokens_ + 1], u) - &cdf_[0];"
    binary_search = """int lo = 1;
    int hi = num_tokens_ + 1;
    while (lo < hi) {
      int mid = lo + (hi - lo) / 2;
      if (u < cdf_[mid]) {
        hi = mid;
      } else {
        lo = mid + 1;
      }
    }
    int n = lo;"""
    if upper_bound_call not in marbles_dist:
        raise SystemExit("expected Marbles std::upper_bound call not found")
    marbles_dist = marbles_dist.replace(upper_bound_call, binary_search)

    # Q15 experiment: encode the 45 inverse-CDF tables as signed 16-bit values.
    # They are monotonic values in [0, 1]. Keep the three unrelated float LUTs intact.
    import re
    import math
    resources_original = eur / "marbles" / "resources.cc"
    resources_patched = patch_root / "marbles" / "resources.cc"
    resources_h_original = eur / "marbles" / "resources.h"
    resources_h_patched = patch_root / "marbles" / "resources.h"
    resources_patched.parent.mkdir(parents=True, exist_ok=True)
    resources_text = resources_original.read_text()
    table_pattern = re.compile(
        r"const float (dist_icdf_\d+_\d+)\[\] = \{([\s\S]*?)\};"
    )
    q15_table_count = 0
    def encode_q15_table(match):
        nonlocal q15_table_count
        values = re.findall(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?", match.group(2))
        encoded = []
        for value in values:
            sample = float(value)
            if sample < 0.0 or sample > 1.0:
                raise SystemExit("Marbles inverse-CDF table value outside [0, 1]")
            encoded.append(str(int(math.floor(sample * 32767.0 + 0.5))))
        q15_table_count += 1
        body = "\n  " + ", ".join(
            ", ".join(encoded[i:i + 12]) for i in range(0, len(encoded), 12)
        ) + "\n"
        return "const int16_t " + match.group(1) + "[] = {" + body + "};"
    resources_text = table_pattern.sub(encode_q15_table, resources_text)
    if q15_table_count != 45:
        raise SystemExit(f"expected 45 Marbles inverse-CDF tables, found {q15_table_count}")
    resources_text = resources_text.replace(
        "const float* distributions_table[] = {",
        "const int16_t* distributions_table[] = {"
    )
    resources_patched.write_text(resources_text)

    resources_h = resources_h_original.read_text()
    resources_h = resources_h.replace(
        "extern const float* distributions_table[];",
        "extern const int16_t* distributions_table[];"
    )
    resources_h = re.sub(
        r"extern const float (dist_icdf_\d+_\d+)\[\];",
        r"extern const int16_t \1[];",
        resources_h
    )
    if resources_h.count("extern const int16_t dist_icdf_") != 45:
        raise SystemExit("Marbles Q15 resource header conversion did not cover all 45 tables")
    resources_h_patched.write_text(resources_h)

    q15_interpolator = """inline float InterpolateQ15(const int16_t* table, float phase) {
  float position = phase * kIcdfTableSize;
  size_t index = static_cast<size_t>(position);
  float fraction = position - static_cast<float>(index);
  float a = static_cast<float>(table[index]) * (1.0f / 32767.0f);
  float b = static_cast<float>(table[index + 1]) * (1.0f / 32767.0f);
  return a + (b - a) * fraction;
}
"""
    marbles_dist = marbles_dist.replace(
        "const float kIcdfTableSize = 128.0f;\n",
        "const float kIcdfTableSize = 128.0f;\n\n" + q15_interpolator
    )
    marbles_dist = marbles_dist.replace(
        "stmlib::Interpolate(\n      distributions_table[cell] + offset,\n      uniform,\n      kIcdfTableSize)",
        "InterpolateQ15(distributions_table[cell] + offset, uniform)"
    )
    marbles_dist = marbles_dist.replace(
        "stmlib::Interpolate(\n      distributions_table[cell + 1] + offset,\n      uniform,\n      kIcdfTableSize)",
        "InterpolateQ15(distributions_table[cell + 1] + offset, uniform)"
    )
    marbles_dist = marbles_dist.replace(
        "stmlib::Interpolate(\n      distributions_table[cell + kNumRangeValues + 1] + offset,\n      uniform,\n      kIcdfTableSize)",
        "InterpolateQ15(distributions_table[cell + kNumRangeValues + 1] + offset, uniform)"
    )
    marbles_dist = marbles_dist.replace(
        "stmlib::Interpolate(\n      distributions_table[cell + kNumRangeValues + 2] + offset,\n      uniform,\n      kIcdfTableSize)",
        "InterpolateQ15(distributions_table[cell + kNumRangeValues + 2] + offset, uniform)"
    )
    marbles_dist = marbles_dist.replace(
        "return stmlib::Interpolate(dist_icdf_4_3, uniform, kIcdfTableSize);",
        "return InterpolateQ15(dist_icdf_4_3, uniform);"
    )
    if "stmlib::Interpolate(" in marbles_dist:
        raise SystemExit("unconverted Marbles float interpolation call remains")
    marbles_dist_patched.write_text(marbles_dist)

    marbles_sources = [
        resources_patched if p == resources_original else p
        for p in marbles_sources
    ]


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

    # Compile a true mono Part implementation in a private namespace.
    mono_part_cc = part_cc.replace(
        '#include "rings/dsp/part.h"',
        '#include "rings_mono/dsp/part.h"'
    )
    if mono_part_cc.count("namespace rings {") != 1 or mono_part_cc.count("}  // namespace rings") != 1:
        raise SystemExit("unexpected Rings Part namespace layout for mono implementation")
    mono_part_cc = mono_part_cc.replace(
        "namespace rings {",
        "namespace rings_mono {" + chr(10) + "using namespace rings;",
        1
    ).replace(
        "}  // namespace rings",
        "}  // namespace rings_mono",
        1
    )
    mono_part_cc_path = patch_root / "rings_mono" / "dsp" / "part.cc"
    mono_part_cc_path.parent.mkdir(parents=True, exist_ok=True)
    mono_part_cc_path.write_text(mono_part_cc)
    sources.append(mono_part_cc_path)

    # Compile-time-only second Rings instance experiment: clone the five-model Part
    # declaration into a private namespace and reduce its compile-time polyphony to 1.
    # It shares stateless DSP component types, but owns its own mono resonator state.
    mono_part_h = part_h.replace(
        "#ifndef RINGS_DSP_PART_H_",
        "#ifndef RINGS_MONO_DSP_PART_H_"
    ).replace(
        "#define RINGS_DSP_PART_H_",
        "#define RINGS_MONO_DSP_PART_H_"
    ).replace(
        "namespace rings {",
        "namespace rings_mono {\n\nusing namespace rings;"
    ).replace(
        "const int32_t kMaxPolyphony = 4;",
        "const int32_t kMaxPolyphony = 1;"
    ).replace(
        "}  // namespace rings",
        "}  // namespace rings_mono"
    )
    if "namespace rings_mono" not in mono_part_h or "kMaxPolyphony = 1" not in mono_part_h:
        raise SystemExit("failed to generate mono Rings Part header")
    mono_part_h_path = patch_root / "rings_mono" / "dsp" / "part.h"
    mono_part_h_path.parent.mkdir(parents=True, exist_ok=True)
    mono_part_h_path.write_text(mono_part_h)


    # Optional isolated target-memory probe: replace only Rings' two delay
    # storage typedefs with signed int16 storage. DSP math/interpolation remains float.
    delay_scale = os.environ.get("FELUCCA_RINGS_DELAY_SCALE")
    if delay_scale:
        scale = int(delay_scale)
        if scale < 1 or scale > 32768:
            raise SystemExit("FELUCCA_RINGS_DELAY_SCALE must be in 1..32768")
        string_original = eur / "rings/dsp/string.h"
        string_patched = patch_root / "rings/dsp/string.h"
        string_text = string_original.read_text()
        old_typedefs = ("typedef stmlib::DelayLine<float, kDelayLineSize> StringDelayLine;\n"
                        "typedef stmlib::DelayLine<float, kDelayLineSize / 2> StiffnessDelayLine;")
        new_typedefs = ("typedef QNDelayLine<kDelayLineSize> StringDelayLine;\n"
                        "typedef QNDelayLine<kDelayLineSize / 2> StiffnessDelayLine;")
        if old_typedefs not in string_text:
            raise SystemExit("expected Rings delay-line typedefs not found")
        include_line = '#include "stmlib/stmlib.h"'
        if include_line not in string_text:
            raise SystemExit("expected Rings stmlib include not found")
        qn_header = (ROOT / "tools/rings_delay_test/qn_delay_line.h").read_text()
        qn_path = patch_root / "rings/dsp/qn_delay_line.h"
        qn_path.parent.mkdir(parents=True, exist_ok=True)
        qn_path.write_text(qn_header)
        string_text = string_text.replace(include_line, include_line + '\n#include "rings/dsp/qn_delay_line.h"')
        string_text = string_text.replace(old_typedefs, new_typedefs)
        string_patched.parent.mkdir(parents=True, exist_ok=True)
        string_patched.write_text(string_text)
        print(f"TARGET DELAY STORAGE: signed int16, scale={scale}; float DSP math retained")

    sources = [clouds_patched if p == clouds_original else
               part_cc_patched if p == part_cc_original else p for p in sources]
    BUILD.mkdir(parents=True, exist_ok=True)
    common = [
        "-target", "pi32v2", "-mcpu=r3", "-mfprev1", os.environ.get("FELUCCA_CODE_OPT", "-Os"), "-std=gnu++11", "-DTEST",
        "-fno-math-errno", "-fno-exceptions", "-fno-rtti", "-fno-threadsafe-statics",
        "-fno-use-cxa-atexit", "-nostdinc++", "-ffunction-sections", *(["-fdata-sections"] if os.environ.get("FELUCCA_DATA_SECTIONS") == "1" else []),
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


    marbles_size_src = ROOT / "tools" / "cpp_smoke" / "marbles_size_probe.cc"
    marbles_size_obj = BUILD / "marbles_size_probe.o"
    invoke([*common, "-c", str(marbles_size_src.relative_to(ROOT)),
            "-o", str(marbles_size_obj.relative_to(ROOT))])
    for src in marbles_sources:
        rel = src.relative_to(ROOT)
        obj = BUILD / ("marbles__" + str(rel).replace("/", "__") + ".o")
        obj.parent.mkdir(parents=True, exist_ok=True)
        invoke([*common, "-c", str(rel), "-o", str(obj.relative_to(ROOT))])

    five_size_src = ROOT / "tools" / "cpp_smoke" / "size_probe_five_model.cc"
    five_size_obj = BUILD / "size_probe_five_model.o"

    mono_size_src = ROOT / "tools" / "cpp_smoke" / "rings_mono_size_probe.cc"
    mono_size_obj = BUILD / "rings_mono_size_probe.o"
    invoke([*common, "-c", str(mono_size_src.relative_to(ROOT)),
            "-o", str(mono_size_obj.relative_to(ROOT))])
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
        "ric_marbles_size_t_generator", "ric_marbles_size_xy_generator",
        "ric_marbles_size_output_channel", "ric_marbles_size_random_sequence",
        "ric_marbles_size_random_stream", "ric_marbles_size_random_generator",
        "ric_marbles2_size_rings_mono_part",
    }
    for obj in (upstream_size_obj, five_size_obj, marbles_size_obj, mono_size_obj):
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

    if "--link-objects" in sys.argv:
        # Recompile the exact patched source set without the host-test-only TEST define.
        # These objects are consumed by the real FM-1 app link; no audio routing is added.
        link_build = ROOT / "build" / "rings-clouds-link"
        link_build.mkdir(parents=True, exist_ok=True)
        link_common = [x for x in common if x != "-DTEST"]
        link_objects = []
        for src in sources:
            rel = src.relative_to(ROOT)
            obj = link_build / (str(rel).replace("/", "__") + ".o")
            obj.parent.mkdir(parents=True, exist_ok=True)
            invoke([*link_common, "-Ifirmware/src", "-c", str(rel),
                    "-o", str(obj.relative_to(ROOT))])
            link_objects.append(obj)

        for src in marbles_sources:
            rel = src.relative_to(ROOT)
            obj = link_build / ("marbles__" + str(rel).replace("/", "__") + ".o")
            obj.parent.mkdir(parents=True, exist_ok=True)
            invoke([*link_common, "-Ifirmware/src", "-c", str(rel),
                    "-o", str(obj.relative_to(ROOT))])
            link_objects.append(obj)
        marbles_bridge_src = ROOT / "firmware" / "cxx" / "marbles_sizing_abi.cc"
        marbles_bridge_obj = link_build / "marbles_sizing_abi.o"
        invoke([*link_common, "-Ifirmware/src", "-c",
                str(marbles_bridge_src.relative_to(ROOT)),
                "-o", str(marbles_bridge_obj.relative_to(ROOT))])
        link_objects.append(marbles_bridge_obj)
        bridge_src = ROOT / "firmware" / "cxx" / "rings_clouds_abi.cc"
        bridge_obj = link_build / "rings_clouds_abi.o"
        invoke([*link_common, "-Ifirmware/src", "-c",
                str(bridge_src.relative_to(ROOT)), "-o", str(bridge_obj.relative_to(ROOT))])
        link_objects.append(bridge_obj)
        (link_build / "objects.txt").write_text(
            "\n".join(str(p.relative_to(ROOT)) for p in link_objects) + "\n")
        print(f"LINK OBJECTS: {len(link_objects)} pinned DSP and C ABI objects in build/rings-clouds-link/objects.txt")
    print(f"PASS: compiled {len(sources)} pinned Rings/Clouds/stmlib C++ translation units and {len(marbles_sources)} Marbles DSP translation units for pi32v2.")
    if "--link-objects" in sys.argv:
        print("DSP link objects prepared for the FM-1 app link; no DSP objects are constructed or processed.")
    else:
        print("Compile-only: no DSP objects are constructed, linked into firmware, or run.")
    

if __name__ == "__main__":
    main()
