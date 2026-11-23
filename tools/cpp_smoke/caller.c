/* SPDX-License-Identifier: GPL-3.0-only */
/* C side of the C/C++ ABI probe. */
extern int rings_clouds_cpp_probe(int value);

int rings_clouds_caller_probe(void) {
    return rings_clouds_cpp_probe(5) == 22 ? 0 : 1;
}
