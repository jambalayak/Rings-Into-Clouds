#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Probe the JieLi C/C++ object ABI and the minimal freestanding features Rings needs.

This remains separate from the production firmware build. It does not prove that
all upstream dependencies or the complete firmware link successfully.
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
CPP = BIN / "clang++"
CC = BIN / "clang"
LD = BIN / "ld"
DOCKER_IMAGE = os.environ.get("JIELI_DOCKER_IMAGE", "debian:bookworm-slim")


def run(tool, args, cwd, docker):
    if docker:
        cmd = [
            "docker", "run", "--rm", "--platform", "linux/amd64",
            "-v", f"{ROOT}:/work", "-v", f"{TOOLCHAIN}:/opt/jieli:ro",
            "-w", "/work", DOCKER_IMAGE, f"/opt/jieli/pi32v2/bin/{tool}", *args,
        ]
    else:
        cmd = [str(BIN / tool), *args]
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode:
        raise SystemExit(f"toolchain probe failed: {tool} exited {result.returncode}")


def main():
    if not CPP.is_file() or not CC.is_file() or not LD.is_file():
        missing = [str(p) for p in (CPP, CC, LD) if not p.is_file()]
        raise SystemExit("Missing JieLi C++ probe tools: " + ", ".join(missing))
    native = platform.system() == "Linux" and platform.machine() in ("x86_64", "AMD64")
    docker = os.environ.get("JIELI_DOCKER", "0" if native else "1") == "1"
    if docker and not shutil.which("docker"):
        raise SystemExit("Docker is required for this host; install Docker or use Linux x86-64.")

    work = ROOT / "build" / "cpp-smoke"
    work.mkdir(parents=True, exist_ok=True)
    c_obj = work / "caller.o"
    cpp_obj = work / "dsp_probe.o"
    combined = work / "combined.o"
    # Match the firmware's size optimisation level, target and FPU selection.
    common = ["-target", "pi32v2", "-mcpu=r3", "-mfprev1", "-Os",
              "-ffunction-sections", "-fdata-sections"]
    run("clang", [*common, "-c", "tools/cpp_smoke/caller.c", "-o", str(c_obj.relative_to(ROOT))],
        ROOT, docker)
    run("clang++", [*common, "-std=gnu++11", "-fno-exceptions", "-fno-rtti",
                    "-fno-threadsafe-statics", "-fno-use-cxa-atexit", "-nostdinc++",
                    "-Itools/cpp_smoke/include", "-c", "tools/cpp_smoke/dsp_probe.cc",
                    "-o", str(cpp_obj.relative_to(ROOT))], ROOT, docker)
    run("ld", ["-r", str(c_obj.relative_to(ROOT)), str(cpp_obj.relative_to(ROOT)),
               "-o", str(combined.relative_to(ROOT))], ROOT, docker)
    print("PASS: target C/C++ objects compiled and the linker combined them.")
    print("Covered: C ABI, C++11, placement construction, std::fill/max_element, and cmath/cstring header bridges.")
    print("Not covered: complete upstream dependencies, C++ runtime, final firmware link,")
    print("memory use, DSP timing, audio behaviour or physical-device operation.")


if __name__ == "__main__":
    main()
