# C++ smoke probe coverage

The standalone `tools/check_cpp_toolchain.py` probe is deliberately separate from the production build. It now compiles at `-Os`, matching the firmware's size-optimised C build, and exercises the narrow C++ facilities already identified in the pinned dependency audit:

- C-to-C++ `extern "C"` function boundary;
- GNU C++11 compilation with exceptions and RTTI disabled;
- placement construction into caller-owned storage;
- `std::fill` through an explicitly supplied freestanding header while `-nostdinc++` is active;
- relocatable combination of the C and C++ objects with the target linker.

The headers under `tools/cpp_smoke/include` are probe fixtures only. They are not production headers and must not be included by firmware DSP sources. In particular, this probe does not establish that the minimal `std::algorithm` surface is sufficient for Rings/Clouds, nor does it provide a general C++ runtime.

Run from a Linux x86-64 development environment with the configured JieLi toolchain:

```sh
python3 tools/check_cpp_toolchain.py
```

A successful result remains only a narrow compiler/ABI feature check. The next decisive test is compiling the actual pinned upstream translation units and inspecting their undefined symbols, constructors, sections and target link requirements.
