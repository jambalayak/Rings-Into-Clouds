// SPDX-License-Identifier: GPL-3.0-only
// Freestanding C++11 probe for Rings/Clouds header dependencies and ABI.
#include <algorithm>
#include <cmath>
#include <cstring>
#include <new>

namespace {
struct Probe {
    int value;
};
}

extern "C" int rings_clouds_cpp_probe(int value) {
    alignas(Probe) char storage[sizeof(Probe)];
    Probe* p = new (storage) Probe{value};

    if (std::fabs(-2.5f) != 2.5f) return -1;

    int values[4] = {0, 0, 0, 0};
    std::fill(values, values + 4, p->value * 3 + 7);
    int copied = 0;
    memcpy(&copied, std::max_element(values, values + 4), sizeof(copied));
    return copied;
}
