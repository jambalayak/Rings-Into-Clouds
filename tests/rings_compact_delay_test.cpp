// SPDX-License-Identifier: GPL-3.0-only
// Host experiment comparing Q-format delay storage with pinned upstream stmlib.
#include <cmath>
#include <cstdio>
#include <stdint.h>

#include "stmlib/dsp/delay_line.h"
#include "tests/compact_delay_line.h"

static uint32_t Next(uint32_t *s) {
  *s = *s * 1664525u + 1013904223u;
  return *s;
}
static float Unit(uint32_t *s) {
  return static_cast<float>(Next(s) >> 8) / 16777216.0f;
}

template<size_t N, int32_t Scale>
static bool Run(const char *label, float amplitude, uint32_t seed) {
  stmlib::DelayLine<float, N> reference;
  CompactDelayLine<N, Scale> compact;
  reference.Init();
  compact.Init();

  double error_energy = 0.0;
  double reference_energy = 0.0;
  float max_error = 0.0f;
  uint32_t rng = seed;

  for (uint32_t i = 0; i < 250000u; ++i) {
    const float input = (Unit(&rng) * 2.0f - 1.0f) * amplitude;
    const float delay = 4.0f + Unit(&rng) * static_cast<float>(N - 8u);
    reference.Write(input);
    compact.Write(input);

    const float a = reference.ReadHermite(delay);
    const float b = compact.ReadHermite(delay);
    const float e = a - b;
    error_energy += static_cast<double>(e) * e;
    reference_energy += static_cast<double>(a) * a;
    if (std::fabs(e) > max_error) max_error = std::fabs(e);

    const size_t integer_delay = 4u + (Next(&rng) % (N - 8u));
    const float coefficient = 0.2f + Unit(&rng) * 0.75f;
    const float ap_ref = reference.Allpass(input * 0.25f, integer_delay, coefficient);
    const float ap_cmp = compact.Allpass(input * 0.25f, integer_delay, coefficient);
    const float ap_error = ap_ref - ap_cmp;
    error_energy += static_cast<double>(ap_error) * ap_error;
    reference_energy += static_cast<double>(ap_ref) * ap_ref;
    if (std::fabs(ap_error) > max_error) max_error = std::fabs(ap_error);

    const float fractional_delay = 4.0f + Unit(&rng) * static_cast<float>(N - 8u);
    const float wr_ref = reference.WriteRead(input * 0.125f, fractional_delay);
    const float wr_cmp = compact.WriteRead(input * 0.125f, fractional_delay);
    const float wr_error = wr_ref - wr_cmp;
    error_energy += static_cast<double>(wr_error) * wr_error;
    reference_energy += static_cast<double>(wr_ref) * wr_ref;
    if (std::fabs(wr_error) > max_error) max_error = std::fabs(wr_error);

    const float read_ref = reference.Read();
    const float read_cmp = compact.Read();
    const float read_error = read_ref - read_cmp;
    error_energy += static_cast<double>(read_error) * read_error;
    reference_energy += static_cast<double>(read_ref) * read_ref;
    if (std::fabs(read_error) > max_error) max_error = std::fabs(read_error);
  }

  const double snr = 10.0 * std::log10(reference_energy / (error_energy + 1e-30));
  const uint32_t saturations = compact.saturation_count();
  std::printf("%s N=%lu scale=%ld SNR=%.2f dB max_err=%.7f saturations=%lu\n",
              label, static_cast<unsigned long>(N), static_cast<long>(Scale),
              snr, max_error, static_cast<unsigned long>(saturations));
  return saturations == 0u && snr >= 60.0 && max_error < 0.01f;
}

int main() {
  bool ok = true;
  ok &= Run<2048, 8192>("Q3.13", 1.0f, 0x12345678u);
  ok &= Run<1024, 8192>("Q3.13", 1.0f, 0x87654321u);
  ok &= Run<2048, 16384>("Q2.14", 1.0f, 0x23456789u);
  ok &= Run<1024, 16384>("Q2.14", 1.0f, 0x98765432u);
  return ok ? 0 : 1;
}
