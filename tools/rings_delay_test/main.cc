#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "rings/dsp/part.h"
#include "rings/dsp/performance_state.h"
#include "rings/dsp/patch.h"
#include "stmlib/utils/random.h"

namespace rings {
uint64_t q15_saturation_count = 0;
float q15_max_abs = 0.0f;
// The shared delay overlay also exports Q24 diagnostics. The original-float
// sample-rate harness does not exercise them, but must satisfy those symbols.
uint64_t q24_saturation_count = 0;
float q24_max_abs = 0.0f;
}

#ifndef RINGS_TEST_SAMPLE_RATE
#define RINGS_TEST_SAMPLE_RATE (24000000.0f / 544.0f)
#endif
static const float kRate = RINGS_TEST_SAMPLE_RATE;
static const size_t kBlock = rings::kMaxBlockSize;

struct TestCase {
  const char *name;
  float structure, brightness, damping, position;
  float seconds;
  bool loud;
};
static const TestCase kCases[] = {
  {"neutral", 0.50f, 0.50f, 0.50f, 0.50f, 1.25f, false},
  {"dark", 0.18f, 0.12f, 0.72f, 0.10f, 1.25f, false},
  {"bright", 0.86f, 0.96f, 0.30f, 0.90f, 1.25f, false},
  {"long_decay", 0.55f, 0.78f, 0.995f, 0.55f, 12.0f, false},
  {"loud_external", 0.70f, 0.92f, 0.55f, 0.45f, 1.25f, true}
};
static const int kNotes[] = {36, 60, 84};

int main(int argc, char **argv) {
  if (argc != 2) return 2;
  FILE *audio = fopen(argv[1], "wb");
  FILE *meta = fopen("segments.csv", "w");
  if (!audio || !meta) return 3;
  fprintf(meta, "start,frames,model,note,profile,damping\n");
  uint64_t cursor = 0;
  for (int model = 0; model < 5; ++model) {
    for (size_t ni = 0; ni < sizeof(kNotes)/sizeof(kNotes[0]); ++ni) {
      for (size_t ci = 0; ci < sizeof(kCases)/sizeof(kCases[0]); ++ci) {
        const TestCase &tc = kCases[ci];
        rings::Part part;
        part.Init();
        part.set_model(static_cast<rings::ResonatorModel>(model));
        part.set_polyphony(1);
        rings::Patch patch = {tc.structure, tc.brightness, tc.damping, tc.position};
        rings::PerformanceState ps = {};
        ps.internal_exciter = !tc.loud;
        ps.internal_strum = true;
        ps.internal_note = true;
        ps.tonic = 0.0f;
        ps.note = static_cast<float>(kNotes[ni]);
        ps.fm = 0.0f;
        ps.chord = 0;
        stmlib::Random::Seed(0x51A7C0DEu + model * 101u + ni * 17u + ci);
        const uint64_t frames = static_cast<uint64_t>(tc.seconds * kRate);
        fprintf(meta, "%llu,%llu,%d,%d,%s,%.6f\n",
          static_cast<unsigned long long>(cursor),
          static_cast<unsigned long long>(frames), model, kNotes[ni], tc.name, tc.damping);
        for (uint64_t offset = 0; offset < frames; offset += kBlock) {
          float in[kBlock] = {}, out[kBlock] = {}, aux[kBlock] = {};
          size_t n = static_cast<size_t>(std::min<uint64_t>(kBlock, frames - offset));
          if (tc.loud) {
            for (size_t i = 0; i < n; ++i) {
              double t = static_cast<double>(cursor + offset + i) / kRate;
              in[i] = 0.92f * sinf(static_cast<float>(2.0 * M_PI * 173.0 * t));
            }
          }
          ps.strum = (offset == 0);
          part.Process(ps, patch, in, out, aux, n);
          for (size_t i = 0; i < n; ++i) {
            float pair[2] = {out[i], aux[i]};
            if (fwrite(pair, sizeof(float), 2, audio) != 2) return 4;
          }
        }
        cursor += frames;
      }
    }
  }
  fclose(audio);
  fclose(meta);
  FILE *stats = fopen("delay_stats.txt", "w");
  if (stats) {
    fprintf(stats, "part_size_bytes=%zu\nstring_size_bytes=%zu\nq15_saturation_count=%llu\nq15_max_abs=%.9g\n",
      sizeof(rings::Part), sizeof(rings::String),
      static_cast<unsigned long long>(rings::q15_saturation_count), rings::q15_max_abs);
    fclose(stats);
  }
  return 0;
}
