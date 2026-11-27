#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Apply a CI-workspace-only guard so diagnostic links emit no firmware images."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / "tools/build.py"
text = path.read_text()

def once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    text = text.replace(old, new, 1)

once(
    '    (OUT / "felucca.bin").write_bytes(img)\n',
    '    if os.environ.get("FELUCCA_DIAGNOSTIC_ONLY") != "1":\n'
    '        (OUT / "felucca.bin").write_bytes(img)\n',
    "app image write",
)
once(
    '    with ThreadPoolExecutor(2) as ex:\n'
    '        gen, ldr = ex.submit(generate), ex.submit(build_loader)\n'
    '        gen.result()\n'
    '        ota = ldr.result()\n',
    '    if os.environ.get("FELUCCA_DIAGNOSTIC_ONLY") == "1":\n'
    '        generate()\n'
    '        ota = b""\n'
    '    else:\n'
    '        with ThreadPoolExecutor(2) as ex:\n'
    '            gen, ldr = ex.submit(generate), ex.submit(build_loader)\n'
    '            gen.result()\n'
    '            ota = ldr.result()\n',
    "loader build",
)
once(
    '    if errors:\n'
    '        raise SystemExit("build: checks failed")\n'
    '    pkg = fm1pkg_make.ufw(fm1pkg_make.flash_image(img, fm1pkg_make.KEY), ota, PRODUCT)\n',
    '    if errors:\n'
    '        raise SystemExit("build: checks failed")\n'
    '    if os.environ.get("FELUCCA_DIAGNOSTIC_ONLY") == "1":\n'
    '        print("DIAGNOSTIC ONLY: skipped loader, felucca.bin and .fwsc package generation.")\n'
    '        return 0\n'
    '    pkg = fm1pkg_make.ufw(fm1pkg_make.flash_image(img, fm1pkg_make.KEY), ota, PRODUCT)\n',
    "package generation",
)
for name in ("felucca.bin", "felucca.fwsc", "felucca-*.fwsc"):
    if "*" in name:
        for stale in (root / "build").glob(name):
            stale.unlink()
    else:
        (root / "build" / name).unlink(missing_ok=True)
(root / "build" / "loader" / "ota.bin").unlink(missing_ok=True)
path.write_text(text)
print("PASS: CI-only diagnostic guard applied; no app binary, OTA loader or FWSC package will be written.")
