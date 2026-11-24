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
        "stmlib/dsp/*.cc", "stmlib/utils/*.cc",
    ):
        root = eur if pattern.startswith(("rings/", "clouds/")) else stm
        sources.extend(root.glob(pattern))
    sources = sorted(p for p in set(sources) if "string_synth" not in p.name)
    if not sources:
        raise SystemExit("No pinned DSP translation units found.")

    # Upstream includes an unused STM32 debug-pin header in this translation unit.
    # Mirror the minimal FM-1 port patch without modifying the pinned submodule.
    original = eur / "clouds/dsp/granular_processor.cc"
    patched = BUILD / "source-patches/clouds/dsp/granular_processor.cc"
    patched.parent.mkdir(parents=True, exist_ok=True)
    text = original.read_text()
    text = text.replace('#include "clouds/drivers/debug_pin.h"\n', "")
    patched.write_text(text)
    sources = [patched if p == original else p for p in sources]

    BUILD.mkdir(parents=True, exist_ok=True)
    common = [
        "-target", "pi32v2", "-mcpu=r3", "-mfprev1", "-Os", "-std=gnu++11", "-DTEST",
        "-fno-math-errno", "-fno-exceptions", "-fno-rtti", "-fno-threadsafe-statics",
        "-fno-use-cxa-atexit", "-nostdinc++", "-ffunction-sections", "-fdata-sections",
        "-Wall", "-Wno-unused-function", "-Wno-unused-variable", "-Wno-unused-local-typedef",
        "-Wframe-larger-than=1024", "-Ifirmware/cxx", "-Ifirmware/sys",
        "-Ithird_party/eurorack", "-Ithird_party",
        "-isystem", "/opt/jieli/pi32v2/include" if os.environ.get("JIELI_DOCKER", "0") == "1" else str(TOOLCHAIN / "pi32v2/include"),
    ]
    for src in sources:
        rel = src.relative_to(ROOT)
        obj = BUILD / (str(rel).replace("/", "__") + ".o")
        obj.parent.mkdir(parents=True, exist_ok=True)
        invoke([*common, "-c", str(rel), "-o", str(obj.relative_to(ROOT))])
    print(f"PASS: compiled {len(sources)} pinned Rings/Clouds/stmlib C++ translation units for pi32v2.")
    print("Compile-only: no DSP instantiation, link, RAM allocation, audio routing or runtime claim.")
    

if __name__ == "__main__":
    main()
