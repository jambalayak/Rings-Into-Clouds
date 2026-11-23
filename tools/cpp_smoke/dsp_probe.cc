// SPDX-License-Identifier: GPL-3.0-only
// C++ ABI probe for the FM-1 JieLi toolchain. No DSP or runtime dependency.
extern "C" int rings_clouds_cpp_probe(int value) {
    return value * 3 + 7;
}
