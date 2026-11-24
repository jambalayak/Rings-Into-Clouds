// SPDX-License-Identifier: GPL-3.0-only
// Prototype only: Q-format storage adapter for the pinned stmlib DelayLine API.
// The interpolation and update order mirror the upstream implementation.
#ifndef RINGS_INTO_CLOUDS_COMPACT_DELAY_LINE_H_
#define RINGS_INTO_CLOUDS_COMPACT_DELAY_LINE_H_

#include <stdint.h>
#include "stmlib/dsp/dsp.h"

template<size_t max_delay, int32_t scale>
class CompactDelayLine {
 public:
  CompactDelayLine() : write_ptr_(0), delay_(1), saturation_count_(0) { }
  ~CompactDelayLine() { }

  void Init() { Reset(); }

  void Reset() {
    for (size_t i = 0; i < max_delay; ++i) line_[i] = 0;
    delay_ = 1;
    write_ptr_ = 0;
    saturation_count_ = 0;
  }

  inline void set_delay(size_t delay) { delay_ = delay; }

  inline void Write(float sample) {
    float scaled = sample * static_cast<float>(scale);
    if (scaled != scaled) scaled = 0.0f;
    int32_t q;
    if (scaled > 32767.0f) {
      q = 32767;
      ++saturation_count_;
    } else if (scaled < -32768.0f) {
      q = -32768;
      ++saturation_count_;
    } else {
      q = scaled >= 0.0f ? static_cast<int32_t>(scaled + 0.5f)
                         : static_cast<int32_t>(scaled - 0.5f);
    }
    line_[write_ptr_] = static_cast<int16_t>(q);
    write_ptr_ = (write_ptr_ - 1 + max_delay) % max_delay;
  }

  inline float Allpass(float sample, size_t delay, float coefficient) {
    float read = Decode(line_[(write_ptr_ + delay) % max_delay]);
    float write = sample + coefficient * read;
    Write(write);
    return -write * coefficient + read;
  }

  inline float WriteRead(float sample, float delay) {
    Write(sample);
    return Read(delay);
  }

  inline float Read() const {
    return Decode(line_[(write_ptr_ + delay_) % max_delay]);
  }

  inline float Read(size_t delay) const {
    return Decode(line_[(write_ptr_ + delay) % max_delay]);
  }

  inline float Read(float delay) const {
    MAKE_INTEGRAL_FRACTIONAL(delay)
    const float a = Decode(line_[(write_ptr_ + delay_integral) % max_delay]);
    const float b = Decode(line_[(write_ptr_ + delay_integral + 1) % max_delay]);
    return a + (b - a) * delay_fractional;
  }

  inline float ReadHermite(float delay) const {
    MAKE_INTEGRAL_FRACTIONAL(delay)
    int32_t t = static_cast<int32_t>(write_ptr_ + delay_integral + max_delay);
    const float xm1 = Decode(line_[(t - 1) % max_delay]);
    const float x0 = Decode(line_[t % max_delay]);
    const float x1 = Decode(line_[(t + 1) % max_delay]);
    const float x2 = Decode(line_[(t + 2) % max_delay]);
    const float c = (x1 - xm1) * 0.5f;
    const float v = x0 - x1;
    const float w = c + v;
    const float a = w + v + (x2 - x0) * 0.5f;
    const float b_neg = w + a;
    const float f = delay_fractional;
    return (((a * f) - b_neg) * f + c) * f + x0;
  }

  uint32_t saturation_count() const { return saturation_count_; }

 private:
  static inline float Decode(int16_t sample) {
    return static_cast<float>(sample) / static_cast<float>(scale);
  }

  size_t write_ptr_;
  size_t delay_;
  uint32_t saturation_count_;
  int16_t line_[max_delay];
};
#endif
