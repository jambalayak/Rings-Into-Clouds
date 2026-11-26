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

    sources = [clouds_patched if p == clouds_original else p for p in sources]
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
    # Measure the complete pinned upstream Rings class and Clouds processor.
    # Each probe is compile-time symbol extent only; neither constructs a DSP object.
    upstream_size_src = ROOT / "tools" / "cpp_smoke" / "size_probe.cc"
    upstream_size_obj = BUILD / "size_probe_upstream.o"
    upstream_common = [x for x in common if x != "-Ibuild/upstream-dsp-compile/source-patches"]
    invoke([*upstream_common, "-c", str(upstream_size_src.relative_to(ROOT)),
            "-o", str(upstream_size_obj.relative_to(ROOT))])


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
    }
    for obj in (upstream_size_obj,):
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
        bridge_src = ROOT / "firmware" / "cxx" / "rings_clouds_abi.cc"
        bridge_obj = link_build / "rings_clouds_abi.o"
        invoke([*link_common, "-Ifirmware/src", "-c",
                str(bridge_src.relative_to(ROOT)), "-o", str(bridge_obj.relative_to(ROOT))])
        link_objects.append(bridge_obj)
        (link_build / "objects.txt").write_text(
            "\n".join(str(p.relative_to(ROOT)) for p in link_objects) + "\n")
        print(f"LINK OBJECTS: {len(link_objects)} pinned DSP and C ABI objects in build/rings-clouds-link/objects.txt")
    print(f"PASS: compiled {len(sources)} pinned Rings/Clouds/stmlib C++ translation units for pi32v2.")
    if "--link-objects" in sys.argv:
        print("DSP link objects prepared for the FM-1 app link; no DSP objects are constructed or processed.")
    else:
        print("Compile-only: no DSP objects are constructed, linked into firmware, or run.")
    

if __name__ == "__main__":
    main()
