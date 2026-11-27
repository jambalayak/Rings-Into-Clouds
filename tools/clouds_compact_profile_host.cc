// SPDX-License-Identifier: GPL-3.0-only
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdio.h>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <limits>
#include <cmath>
#include <new>
#include <stdexcept>

#include "clouds/dsp/granular_processor.h"
#include "clouds/dsp/parameters.h"
#include "clouds/dsp/frame.h"

using clouds::GranularProcessor;
using clouds::PlaybackMode;
using clouds::Parameters;
using clouds::ShortFrame;

class GuardedBuffer {
 public:
  explicit GuardedBuffer(size_t size) : size_(size), raw_(NULL), data_(NULL) {
    if (posix_memalign(&raw_, 16, size_ + 128) != 0) {
      throw std::bad_alloc();
    }
    data_ = static_cast<uint8_t*>(raw_) + 64;
    memset(raw_, 0xA7, 64);
    memset(data_, 0, size_);
    memset(data_ + size_, 0x5C, 64);
  }
  ~GuardedBuffer() { free(raw_); }
  void* data() { return data_; }
  bool intact() const {
    const uint8_t* p = static_cast<const uint8_t*>(raw_);
    for (size_t i = 0; i < 64; ++i) if (p[i] != 0xA7) return false;
    for (size_t i = 0; i < 64; ++i) if (data_[size_ + i] != 0x5C) return false;
    return true;
  }
 private:
  size_t size_;
  void* raw_;
  uint8_t* data_;
  GuardedBuffer(const GuardedBuffer&);
  GuardedBuffer& operator=(const GuardedBuffer&);
};

static void SetParameters(Parameters* p) {
  memset(p, 0, sizeof(*p));
  p->position = 0.5f;
  p->size = 0.5f;
  p->pitch = 0.0f;
  p->density = 0.5f;
  p->texture = 0.5f;
  p->dry_wet = 1.0f;
  p->stereo_spread = 0.5f;
  p->feedback = 0.15f;
  p->reverb = 0.2f;
  p->freeze = false;
  p->trigger = false;
  p->gate = false;
  p->granular.overlap = 0.0f;
  p->granular.window_shape = 0.5f;
  p->granular.stereo_spread = 0.5f;
  p->granular.use_deterministic_seed = true;
  p->spectral.quantization = 0.5f;
  p->spectral.refresh_rate = 0.5f;
  p->spectral.phase_randomization = 0.0f;
  p->spectral.warp = 0.5f;
}

static void FillInput(ShortFrame* in, size_t count, uint64_t offset) {
  const double pi = 3.14159265358979323846;
  for (size_t i = 0; i < count; ++i) {
    const double t = static_cast<double>(offset + i) / 32000.0;
    in[i].l = static_cast<int16_t>(12000.0 * sin(2.0 * pi * 173.0 * t));
    in[i].r = static_cast<int16_t>(9000.0 * sin(2.0 * pi * 311.0 * t + 0.31));
  }
}

static bool ProcessBlocks(GranularProcessor* p, int blocks, bool exercise_limits) {
  ShortFrame in[clouds::kMaxBlockSize];
  ShortFrame out[clouds::kMaxBlockSize];
  uint64_t offset = 0;
  for (int b = 0; b < blocks; ++b) {
    Parameters* params = p->mutable_parameters();
    if (exercise_limits) {
      params->position = (b & 1) ? 0.0f : 1.0f;
      params->size = (b & 2) ? 0.0f : 1.0f;
    }
    if ((b % 17) == 0) p->set_freeze(true);
    if ((b % 17) == 8) p->set_freeze(false);
    FillInput(in, clouds::kMaxBlockSize, offset);
    p->Process(in, out, clouds::kMaxBlockSize);
    for (size_t i = 0; i < clouds::kMaxBlockSize; ++i) {
      if (!std::isfinite(static_cast<float>(out[i].l)) ||
          !std::isfinite(static_cast<float>(out[i].r))) return false;
    }
    offset += clouds::kMaxBlockSize;
    p->Prepare();
  }
  return true;
}

static bool RunCompactMatrix() {
#ifndef RIC_COMPACT_PROFILE
  std::cerr << "matrix must run against compact profile build\n";
  return false;
#else
  const PlaybackMode modes[] = {
    clouds::PLAYBACK_MODE_GRANULAR,
    clouds::PLAYBACK_MODE_STRETCH,
    clouds::PLAYBACK_MODE_LOOPING_DELAY,
    clouds::PLAYBACK_MODE_SPECTRAL
  };
  for (int quality = 0; quality < 4; ++quality) {
    for (int mode = 0; mode < 4; ++mode) {
      GuardedBuffer large(86144);
      GuardedBuffer small(32768);
      alignas(16) uint8_t storage[sizeof(GranularProcessor)];
      memset(storage, 0, sizeof(storage));
      GranularProcessor* p = new (storage) GranularProcessor();
      p->Init(large.data(), 86144, small.data(), 32768);
      p->set_quality(quality);
      p->set_playback_mode(modes[mode]);
      SetParameters(p->mutable_parameters());
      p->Prepare();
      if (!p->buffers_ready()) {
        std::cerr << "Prepare rejected supported quality=" << quality
                  << " mode=" << mode << "\n";
        p->~GranularProcessor();
        return false;
      }
      if (!ProcessBlocks(p, 48, true)) {
        std::cerr << "non-finite output quality=" << quality << " mode=" << mode << "\n";
        p->~GranularProcessor();
        return false;
      }
      if (!large.intact() || !small.intact()) {
        std::cerr << "buffer guard damaged quality=" << quality << " mode=" << mode << "\n";
        p->~GranularProcessor();
        return false;
      }
      p->~GranularProcessor();
      std::cout << "PASS matrix quality=" << quality << " mode=" << mode << "\n";
    }
  }

  // Exercise live changes across all modes and both quality bits in one instance.
  {
    GuardedBuffer large(86144);
    GuardedBuffer small(32768);
    alignas(16) uint8_t storage[sizeof(GranularProcessor)];
    memset(storage, 0, sizeof(storage));
    GranularProcessor* p = new (storage) GranularProcessor();
    p->Init(large.data(), 86144, small.data(), 32768);
    SetParameters(p->mutable_parameters());
    for (int q = 0; q < 4; ++q) {
      p->set_quality(q);
      for (int m = 0; m < 4; ++m) {
        p->set_playback_mode(modes[m]);
        p->Prepare();
        if (!p->buffers_ready() || !ProcessBlocks(p, 24, true)) {
          std::cerr << "switch failure quality=" << q << " mode=" << m << "\n";
          p->~GranularProcessor();
          return false;
        }
      }
    }
    if (!large.intact() || !small.intact()) {
      std::cerr << "switch sequence damaged buffer guard\n";
      p->~GranularProcessor();
      return false;
    }
    p->~GranularProcessor();
  }

  // Too-small storage must fail closed and produce silence rather than enter DSP.
  {
    GuardedBuffer large(86143);
    GuardedBuffer small(32768);
    alignas(16) uint8_t storage[sizeof(GranularProcessor)];
    memset(storage, 0, sizeof(storage));
    GranularProcessor* p = new (storage) GranularProcessor();
    p->Init(large.data(), 86143, small.data(), 32768);
    p->set_quality(0);
    p->set_playback_mode(clouds::PLAYBACK_MODE_SPECTRAL);
    SetParameters(p->mutable_parameters());
    p->Prepare();
    if (p->buffers_ready()) {
      std::cerr << "undersized buffer was incorrectly accepted\n";
      p->~GranularProcessor();
      return false;
    }
    ShortFrame in[clouds::kMaxBlockSize], out[clouds::kMaxBlockSize];
    FillInput(in, clouds::kMaxBlockSize, 0);
    for (size_t i = 0; i < clouds::kMaxBlockSize; ++i) out[i].l = out[i].r = 1234;
    p->Process(in, out, clouds::kMaxBlockSize);
    for (size_t i = 0; i < clouds::kMaxBlockSize; ++i) {
      if (out[i].l != 0 || out[i].r != 0) {
        std::cerr << "failed Prepare did not block processing\n";
        p->~GranularProcessor();
        return false;
      }
    }
    if (!large.intact() || !small.intact()) {
      std::cerr << "undersized profile damaged guard\n";
      p->~GranularProcessor();
      return false;
    }
    p->~GranularProcessor();
  }
  std::cout << "PASS compact profile: 16 mode/quality cases, switching, freeze, limits, guards, fail-closed\n";
  return true;
#endif
}

static void WriteU16(std::ofstream& f, uint16_t v) {
  char b[2] = { static_cast<char>(v), static_cast<char>(v >> 8) };
  f.write(b, 2);
}
static void WriteU32(std::ofstream& f, uint32_t v) {
  char b[4] = { static_cast<char>(v), static_cast<char>(v >> 8),
                static_cast<char>(v >> 16), static_cast<char>(v >> 24) };
  f.write(b, 4);
}

static bool RenderWav(const std::string& path) {
#ifdef RIC_COMPACT_PROFILE
  const size_t large_size = 86144, small_size = 32768;
#else
  const size_t large_size = 118784, small_size = 65408;
#endif
  GuardedBuffer large(large_size), small(small_size);
  alignas(16) uint8_t storage[sizeof(GranularProcessor)];
  memset(storage, 0, sizeof(storage));
  GranularProcessor* p = new (storage) GranularProcessor();
  p->Init(large.data(), large_size, small.data(), small_size);
  p->set_quality(0);  // stereo, full 32 kHz / 16-bit quality
  p->set_playback_mode(clouds::PLAYBACK_MODE_SPECTRAL);
  SetParameters(p->mutable_parameters());
  Parameters* params = p->mutable_parameters();
  params->position = 0.5f;
  params->size = 0.5f;
  params->pitch = 0.0f;
  params->density = 0.4949495f;  // refresh_rate=0.5, deterministic phase history
  params->texture = 0.5f;
  params->dry_wet = 1.0f;
  params->feedback = 0.0f;
  params->reverb = 0.0f;
  p->Prepare();
#ifdef RIC_COMPACT_PROFILE
  if (!p->buffers_ready()) {
    std::cerr << "compact stereo Spectral 2048 did not prepare\n";
    p->~GranularProcessor();
    return false;
  }
#endif

  const uint32_t sample_rate = 32000;
  const uint32_t frames = sample_rate * 4;
  std::vector<int16_t> samples(static_cast<size_t>(frames) * 2);
  ShortFrame in[clouds::kMaxBlockSize], out[clouds::kMaxBlockSize];
  uint64_t offset = 0;
  for (uint32_t done = 0; done < frames; done += clouds::kMaxBlockSize) {
    FillInput(in, clouds::kMaxBlockSize, offset);
    p->Process(in, out, clouds::kMaxBlockSize);
    for (size_t i = 0; i < clouds::kMaxBlockSize; ++i) {
      samples[(static_cast<size_t>(done) + i) * 2] = out[i].l;
      samples[(static_cast<size_t>(done) + i) * 2 + 1] = out[i].r;
    }
    offset += clouds::kMaxBlockSize;
    p->Prepare();
  }

  std::ofstream f(path.c_str(), std::ios::binary);
  if (!f) {
    p->~GranularProcessor();
    return false;
  }
  const uint32_t data_bytes = frames * 2 * 2;
  f.write("RIFF", 4); WriteU32(f, 36 + data_bytes); f.write("WAVE", 4);
  f.write("fmt ", 4); WriteU32(f, 16); WriteU16(f, 1); WriteU16(f, 2);
  WriteU32(f, sample_rate); WriteU32(f, sample_rate * 4);
  WriteU16(f, 4); WriteU16(f, 16);
  f.write("data", 4); WriteU32(f, data_bytes);
  for (size_t i = 0; i < samples.size(); ++i) WriteU16(f, static_cast<uint16_t>(samples[i]));
  f.close();
  const bool ok = large.intact() && small.intact();
  p->~GranularProcessor();
  return ok && f.good();
}

int main(int argc, char** argv) {
  if (argc == 3 && std::string(argv[1]) == "--render") {
    if (!RenderWav(argv[2])) return 2;
    std::cout << "WAV written at same fixed gain: " << argv[2] << "\n";
    return 0;
  }
  if (argc == 2 && std::string(argv[1]) == "--self-test") {
    return RunCompactMatrix() ? 0 : 1;
  }
  std::cerr << "usage: clouds_host_test --self-test | --render output.wav\n";
  return 2;
}
