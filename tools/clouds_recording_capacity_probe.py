#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""CI-only probe: enlarge Clouds recording buffers while preserving 53,376 B workspace.

The POOL increase is 24,544 B, leaving 4,112 B uncommitted (4,096 B reserves
plus 16 B). No DSP algorithms, FFT sizes, mode behavior or audio routing change.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LARGE, SMALL, MONO_RECORD, WORKSPACE = 98416, 45040, 45040, 53376
OLD_LARGE, OLD_SMALL, OLD_RECORD = 86144, 32768, 32768
DELTA = (LARGE - OLD_LARGE) + (SMALL - OLD_SMALL)
assert DELTA == 24544
assert LARGE - MONO_RECORD == WORKSPACE
assert LARGE - SMALL == WORKSPACE
assert LARGE % 16 == SMALL % 16 == MONO_RECORD % 16 == 0

def once(path, old, new, label):
    s = path.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected one match in {path}, found {n}")
    path.write_text(s.replace(old, new, 1))

abi = ROOT / "firmware/cxx/rings_clouds_abi.cc"
once(abi,
''' * 86,144 B large buffer = 32,768 B recording + 53,376 B workspace;
 * 32,768 B small buffer = the second 32,768 B recording channel.''',
''' * 98,416 B large buffer = 45,040 B recording + 53,376 B workspace;
 * 45,040 B small buffer = the second 45,040 B recording channel.''',
     "ABI layout comment")
once(abi, "ric_clouds_large_buffer[86144]", "ric_clouds_large_buffer[98416]",
     "large POOL buffer")
once(abi, "ric_clouds_small_buffer[32768]", "ric_clouds_small_buffer[45040]",
     "small POOL buffer")

profile = ROOT / "tools/clouds_compact_profile.py"
once(profile,
'''LARGE = 86144
SMALL = 32768
MONO_RECORD = 32768''',
'''LARGE = 98416
SMALL = 45040
MONO_RECORD = 45040''',
     "profile constants")
once(profile,
'''        buffer_size_[0] < 86144 || buffer_size_[1] < 32768''',
'''        buffer_size_[0] < 98416 || buffer_size_[1] < 45040''',
     "buffer-size preflight")
once(profile,
'''        // Mono non-Spectral: 32 KiB recording followed by the full 53,376 B
        // FX workspace inside the 86,144 B large POOL allocation.
        buffer_size[0] = 32768;
        workspace = static_cast<uint8_t*>(buffer_[0]) + 32768;
        workspace_size = buffer_size_[0] - 32768;''',
'''        // Mono non-Spectral: 45,040 B recording followed by the full 53,376 B
        // FX workspace inside the 98,416 B large POOL allocation.
        buffer_size[0] = MONO_RECORD;
        workspace = static_cast<uint8_t*>(buffer_[0]) + MONO_RECORD;
        workspace_size = buffer_size_[0] - MONO_RECORD;''',
     "mono recording/workspace partition")
once(profile,
'''        ? 32768 : buffer_size_[num_channels_ - 1];''',
'''        ? MONO_RECORD : buffer_size_[num_channels_ - 1];''',
     "persistent recording size")

harness = ROOT / "tools/clouds_compact_profile_host.cc"
h = harness.read_text()
for old, new, label, expected in (
    ("GuardedBuffer large(86144);", "GuardedBuffer large(98416);", "matrix large buffer", 2),
    ("GuardedBuffer small(32768);", "GuardedBuffer small(45040);", "matrix small buffer", 3),
    ("p->Init(large.data(), 86144, small.data(), 32768);",
     "p->Init(large.data(), 98416, small.data(), 45040);", "matrix processor init", 2),
    ("GuardedBuffer large(86143);", "GuardedBuffer large(98415);", "undersized large buffer", 1),
    ("p->Init(large.data(), 86143, small.data(), 32768);",
     "p->Init(large.data(), 98415, small.data(), 45040);", "undersized processor init", 1),
    ("const size_t large_size = 86144, small_size = 32768;",
     "const size_t large_size = 98416, small_size = 45040;", "render buffer sizes", 1),
):
    if h.count(old) != expected:
        raise SystemExit(f"{label}: expected {expected} matches, found {h.count(old)}")
    h = h.replace(old, new)
harness.write_text(h)

test = ROOT / "tools/clouds_compact_profile_test.py"
once(test,
'''if profile["workspace_non_spectral"] != 41752:
    raise SystemExit("Unexpected non-Spectral workspace arithmetic.")''',
'''if profile["workspace_non_spectral"] != 41752:
    raise SystemExit("Unexpected non-Spectral workspace arithmetic.")
if (profile["large_buffer"], profile["small_buffer"], profile["mono_record"],
        profile["recording_workspace"]) != (98416, 45040, 45040, 53376):
    raise SystemExit("Unexpected recording-capacity partition.")''',
     "recording profile assertions")
once(test,
'''    "Pinned Clouds compact-profile allocation proof\\n"
    f"Non-Spectral FX workspace: {profile['workspace_non_spectral']} B / 53,376 B\\n"''',
'''    "Pinned Clouds recording-capacity profile allocation proof\\n"
    f"Large POOL buffer: {profile['large_buffer']} B = {profile['mono_record']} B mono recording + {profile['recording_workspace']} B workspace\\n"
    f"Small POOL buffer: {profile['small_buffer']} B = second stereo recording channel\\n"
    f"Stereo recording at 32 kHz/16-bit: {profile['small_buffer'] / 64000:.3f} seconds per channel\\n"
    f"Non-Spectral FX workspace: {profile['workspace_non_spectral']} B / 53,376 B\\n"''',
     "allocation proof report")
profile = profile.read_text()
needle = '''    return {
        "workspace_non_spectral": NON_SPECTRAL_WORKSPACE,'''
replacement = '''    return {
        "large_buffer": LARGE,
        "small_buffer": SMALL,
        "mono_record": MONO_RECORD,
        "recording_workspace": WORKSPACE,
        "workspace_non_spectral": NON_SPECTRAL_WORKSPACE,'''
if profile.count(needle) != 1:
    raise SystemExit("profile return dictionary did not match")
(ROOT / "tools/clouds_compact_profile.py").write_text(profile.replace(needle, replacement, 1))

out = ROOT / "build/clouds-recording-capacity-probe"
out.mkdir(parents=True, exist_ok=True)
(out / "allocation-report.txt").write_text(
    "Clouds recording-capacity POOL probe (CI workspace only)\\n"
    f"Large buffer: {LARGE} B = {MONO_RECORD} B recording + {WORKSPACE} B workspace\\n"
    f"Small buffer: {SMALL} B = second stereo recording channel\\n"
    f"Additional POOL: {DELTA} B; net free after reserves: 16 B\\n"
    f"Recording duration at 32 kHz / 16-bit: {SMALL / 64000:.3f} s per channel\\n"
    "All four modes and existing FFT sizes retained; no DSP algorithm edits.\\n"
    "No firmware behavior/audio routing is activated; target build is link-only.\\n"
    "No .bin, .fwsc, OTA loader or installable package is generated.\\n"
)
print((out / "allocation-report.txt").read_text(), end="")
