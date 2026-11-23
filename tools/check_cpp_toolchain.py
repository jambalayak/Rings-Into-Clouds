#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Check whether the configured JieLi toolchain can compile C++ and link a C ABI probe.

This is intentionally separate from the firmware build. It does not modify firmware
objects or claim that the full Rings/Clouds runtime is supported.
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

    # Docker can only see files under ROOT. Keep probe objects in the ignored build tree.
    work = ROOT / "build" / "cpp-smoke"
    work.mkdir(parents=True, exist_ok=True)
    c_obj = work / "caller.o"
    cpp_obj = work / "dsp_probe.o"
    combined = work / "combined.o"
    common = ["-target", "pi32v2", "-mcpu=r3", "-mfprev1", "-O2",
              "-ffunction-sections", "-fdata-sections"]
    run("clang", [*common, "-c", "tools/cpp_smoke/caller.c", "-o", str(c_obj.relative_to(ROOT))],
        ROOT, docker)
    run("clang++", [*common, "-std=gnu++11", "-fno-exceptions", "-fno-rtti",
                    "-fno-threadsafe-statics", "-fno-use-cxa-atexit", "-nostdinc++",
                    "-c", "tools/cpp_smoke/dsp_probe.cc", "-o", str(cpp_obj.relative_to(ROOT))],
        ROOT, docker)
    run("ld", ["-r", str(c_obj.relative_to(ROOT)), str(cpp_obj.relative_to(ROOT)),
               "-o", str(combined.relative_to(ROOT))], ROOT, docker)
    print("PASS: JieLi clang and clang++ compiled C/C++ objects and the linker combined them.")
    print("This verifies only the basic target C ABI/object-link path; it does not verify")
    print("the C++ runtime, upstream DSP dependencies, firmware memory use or audio deadlines.")


if __name__ == "__main__":
    main()
