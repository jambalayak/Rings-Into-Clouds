// SPDX-License-Identifier: GPL-3.0-only
// Freestanding C++11 probe: placement construction + the std::fill dependency
// used by the pinned stmlib delay-line implementation.
#include <algorithm>
#include <new>

namespace {
struct Probe {
    int value;
};
}

extern "C" int rings_clouds_cpp_probe(int value) {
    alignas(Probe) char storage[sizeof(Probe)];
    Probe* p = new (storage) Probe{value};

    int values[4] = {0, 0, 0, 0};
    std::fill(values, values + 4, p->value * 3 + 7);
    return values[0] + values[1] + values[2] + values[3] == 4 * (value * 3 + 7)
        ? values[0] : -1;
}
