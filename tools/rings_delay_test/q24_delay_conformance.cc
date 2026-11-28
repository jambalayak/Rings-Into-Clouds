// SPDX-License-Identifier: GPL-3.0-only
// Packed-24 delay API comparison against the pinned upstream stmlib implementation.
#include <cmath>
#include <cstdio>
#include <stdint.h>

#include "stmlib/dsp/delay_line.h"
#include "rings/dsp/q24_delay_line.h"

namespace rings {
uint64_t q24_saturation_count = 0;
float q24_max_abs = 0.0f;
}

static uint32_t Next(uint32_t *state) {
  *state = *state * 1664525u + 1013904223u;
  return *state;
}

static float Unit(uint32_t *state) {
  return static_cast<float>(Next(state) >> 8) / 16777216.0f;
}

template <size_t N>
static bool Run(const char *label, uint32_t seed) {
  stmlib::DelayLine<float, N> reference;
  rings::Q24DelayLine<N> packed;
  reference.Init();
  packed.Init();

  bool ok = reference.Read() == 0.0f && packed.Read() == 0.0f;
  reference.set_delay(31);
  packed.set_delay(31);

  double signal_energy = 0.0;
  double error_energy = 0.0;
  float max_error = 0.0f;
  uint32_t rng = seed;

  for (uint32_t i = 0; i < 250000u; ++i) {
    const float input = (Unit(&rng) * 2.0f - 1.0f) * 0.45f;
    reference.Write(input);
    packed.Write(input);

    const float fractional = 3.0f + Unit(&rng) * static_cast<float>(N - 6u);
    const float integer = 3.0f + static_cast<float>(Next(&rng) % (N - 6u));
    const float coefficient = 0.25f + Unit(&rng) * 0.60f;

    const float outputs_ref[] = {
      reference.Read(),
      reference.Read(static_cast<size_t>(integer)),
      reference.Read(fractional),
      reference.ReadHermite(fractional),
      reference.Allpass(input * 0.2f, static_cast<size_t>(integer), coefficient),
      reference.WriteRead(input * 0.1f, fractional)
    };
    const float outputs_packed[] = {
      packed.Read(),
      packed.Read(static_cast<size_t>(integer)),
      packed.Read(fractional),
      packed.ReadHermite(fractional),
      packed.Allpass(input * 0.2f, static_cast<size_t>(integer), coefficient),
      packed.WriteRead(input * 0.1f, fractional)
    };

    for (size_t k = 0; k < sizeof(outputs_ref) / sizeof(outputs_ref[0]); ++k) {
      const double e = static_cast<double>(outputs_ref[k]) - outputs_packed[k];
      error_energy += e * e;
      signal_energy += static_cast<double>(outputs_ref[k]) * outputs_ref[k];
      if (std::fabs(static_cast<float>(e)) > max_error)
        max_error = std::fabs(static_cast<float>(e));
    }
  }

  const double snr = 10.0 * std::log10(signal_energy / (error_energy + 1e-30));
  const uint64_t saturations = rings::q24_saturation_count;
  packed.Reset();
  ok = ok && packed.Read() == 0.0f && packed.ReadHermite(17.25f) == 0.0f;
  const bool pass = ok && saturations == 0u && snr >= 45.0 && max_error < 0.01f;
  std::printf("%s N=%lu SNR=%.2f dB max_error=%.8f saturations=%llu reset=%s %s\n",
      label, static_cast<unsigned long>(N), snr, max_error,
      static_cast<unsigned long long>(saturations), ok ? "pass" : "fail",
      pass ? "PASS" : "FAIL");
  return pass;
}

int main() {
  rings::q24_saturation_count = 0;
  bool ok = Run<2048>("string-delay", 0x12345678u);
  rings::q24_saturation_count = 0;
  ok = Run<1024>("stiffness-delay", 0x87654321u) && ok;
  return ok ? 0 : 1;
}
