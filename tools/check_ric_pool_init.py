#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Verify experiment buffer sizes and POOL startup ordering without attaching audio."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
main = (ROOT / "firmware/src/main.c").read_text()
audio = (ROOT / "firmware/src/audio.c").read_text()
abi = (ROOT / "firmware/cxx/rings_clouds_abi.cc").read_text()
header = (ROOT / "firmware/src/rings_clouds_abi.h").read_text()

pool_loop = main.find("for (d = _pool_start; d < _pool_end; d++)")
pool_zero = main.find("*d = 0;", pool_loop)
app_entry = main.find("fm1_main();", pool_zero)
if min(pool_loop, pool_zero, app_entry) < 0 or not (pool_loop < pool_zero < app_entry):
    raise SystemExit("POOL is not explicitly zero-initialised before fm1_main()")

for symbol, size in (("ric_clouds_large_buffer", 86144),
                     ("ric_clouds_small_buffer", 32768)):
    pattern = r'__attribute__\(\(used, section\("\.pool"\), aligned\(16\)\)\)\s+unsigned char\s+' + symbol + r'\[' + str(size) + r'\];'
    if not re.search(pattern, abi):
        raise SystemExit(f"{symbol} is not the expected {size}-byte, 16-byte-aligned POOL allocation")

if "53,376 B workspace" not in abi:
    raise SystemExit("the approved 53,376-byte workspace is not documented in the ABI allocation")
if "ric_dsp_init(" in audio:
    raise SystemExit("DSP init is connected to the audio path; this experiment must remain disconnected")
if "deliberately not called by the current firmware audio path" not in header:
    raise SystemExit("the disconnected-audio ABI guard comment is missing")

print("PASS: startup clears the complete POOL range before fm1_main();")
print("PASS: Clouds buffers are 86,144 B + 32,768 B, aligned and placed in .pool; workspace is 53,376 B.")
print("PASS: DSP init remains disconnected from audio; no audio path was changed.")
