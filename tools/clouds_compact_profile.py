#!/usr/bin/env python3
"""Apply an isolated compact-buffer Clouds source overlay to pinned upstream files."""
from pathlib import Path

LARGE = 86144
SMALL = 32768
MONO_RECORD = 32768
WORKSPACE = 53376
REVERB_BYTES = 32768
DIFFUSER_BYTES = 8192
CORRELATOR_BYTES = ((2048 // 32) + 2) * 3 * 4
NON_SPECTRAL_WORKSPACE = DIFFUSER_BYTES + REVERB_BYTES + CORRELATOR_BYTES


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one source match, found {count}")
    return text.replace(old, new, 1)


def apply_compact_profile(root, patch_root):
    root = Path(root)
    patch_root = Path(patch_root)
    eur = root / "third_party/eurorack"
    clouds = eur / "clouds/dsp"
    out = patch_root / "clouds/dsp"
    out.mkdir(parents=True, exist_ok=True)

    # Remove the hardware-only debug pin include; no DSP behavior changes.
    gp = (clouds / "granular_processor.cc").read_text()
    gp = replace_once(gp, '#include "clouds/drivers/debug_pin.h"\n', "",
                      "debug pin include")

    # Header: expose readiness for host tests and prevent processing after a failed prepare.
    gh = (clouds / "granular_processor.h").read_text()
    gh = replace_once(
        gh, "  void Prepare();\n",
        "  void Prepare();\n  bool buffers_ready() const { return buffers_ready_; }\n",
        "Prepare declaration")
    gh = replace_once(
        gh, "  bool reset_buffers_;\n",
        "  bool reset_buffers_;\n  bool buffers_ready_;\n",
        "readiness state")

    # The phase vocoder must reject profiles before any STFT or texture pointer is used.
    ph = (clouds / "pvoc/phase_vocoder.h").read_text()
    ph = replace_once(ph, "  void Init(\n", "  bool Init(\n", "phase vocoder Init return")
    pc = (clouds / "pvoc/phase_vocoder.cc").read_text()
    pc = replace_once(pc, "void PhaseVocoder::Init(\n", "bool PhaseVocoder::Init(\n",
                      "phase vocoder definition")
    pc = replace_once(
        pc,
        "  num_channels_ = num_channels;\n\n  size_t fft_size = largest_fft_size;",
        """  if ((num_channels != 1 && num_channels != 2) ||
      (largest_fft_size != 2048 && largest_fft_size != 4096)) {
    return false;
  }
  const size_t preflight_texture_size = (largest_fft_size >> 1) - kHighFrequencyTruncation;
  const size_t base_bytes = (num_channels == 1 ? 14u : 10u) * largest_fft_size;
  const size_t required_bytes =
      base_bytes + 3u * preflight_texture_size * sizeof(float);
  for (int32_t i = 0; i < num_channels; ++i) {
    if (buffer[i] == NULL || buffer_size[i] < required_bytes) {
      return false;
    }
  }

  num_channels_ = num_channels;
  size_t fft_size = largest_fft_size;""",
        "phase vocoder preflight")
    pc = replace_once(
        pc,
        "  float* ifft_buffer = allocator[num_channels_ - 1]->Allocate<float>(fft_size);\n",
        """  float* ifft_buffer = allocator[num_channels_ - 1]->Allocate<float>(fft_size);
  if (fft_buffer == NULL || ifft_buffer == NULL) {
    return false;
  }
""",
        "FFT allocations")
    pc = replace_once(
        pc,
        "    short* ana_syn_buffer = allocator[i]->Allocate<short>(\n        (fft_size + (fft_size >> 1)) * 2);\n",
        """    short* ana_syn_buffer = allocator[i]->Allocate<short>(
        (fft_size + (fft_size >> 1)) * 2);
    if (ana_syn_buffer == NULL) {
      return false;
    }
""",
        "analysis synthesis allocation")
    pc = replace_once(
        pc,
        "  for (int32_t i = 0; i < num_channels_; ++i) {\n    float* texture_buffer = allocator[i]->Allocate<float>(\n        num_textures * texture_size);\n    frame_transformation_[i].Init(texture_buffer, fft_size, num_textures);\n  }\n}",
        """  // FrameTransformation reserves the final texture for phase and phase-delta
  // storage. Three allocations therefore mean exactly two usable magnitude
  // textures plus phase storage; fewer would make textures_[num_textures - 1]
  // invalid and position interpolation unsafe.
  if (num_textures < 3) {
    return false;
  }
  for (int32_t i = 0; i < num_channels_; ++i) {
    float* texture_buffer = allocator[i]->Allocate<float>(
        num_textures * texture_size);
    if (texture_buffer == NULL) {
      return false;
    }
    frame_transformation_[i].Init(texture_buffer, fft_size, num_textures);
  }
  return true;
}""",
        "texture allocation and minimum")
    (out / "granular_processor.cc").write_text(gp)
    (out / "granular_processor.h").write_text(gh)
    (out / "pvoc/phase_vocoder.cc").parent.mkdir(parents=True, exist_ok=True)
    (out / "pvoc/phase_vocoder.cc").write_text(pc)
    (out / "pvoc/phase_vocoder.h").write_text(ph)

    # The pinned correlator shifts by (32 - offset_bits). At offset_bits == 0
    # this is a shift by the type width, which is undefined in C/C++. Preserve
    # the intended word-aligned result without changing the nonzero-bit path.
    correlator = (clouds / "correlator.cc").read_text()
    correlator = replace_once(
        correlator,
        "    destination_bits |= destination[i] << offset_bits;\n"
        "    destination_bits |= destination[i + 1] >> (32 - offset_bits);",
        """    if (offset_bits == 0) {
      destination_bits = destination[i];
    } else {
      destination_bits |= destination[i] << offset_bits;
      destination_bits |= destination[i + 1] >> (32 - offset_bits);
    }""",
        "word-aligned correlator shift")
    (out / "correlator.cc").write_text(correlator)

    # Replace Prepare() with an explicitly partitioned, preflighted profile.
    start = gp.index("void GranularProcessor::Prepare() {")
    end = gp.rfind("\n}  // namespace clouds")
    if end < start:
        raise RuntimeError("Could not locate end of GranularProcessor::Prepare")
    prepare = r'''void GranularProcessor::Prepare() {
  const bool playback_mode_changed =
      previous_playback_mode_ != playback_mode_;
  const bool benign_change =
      previous_playback_mode_ != PLAYBACK_MODE_SPECTRAL &&
      playback_mode_ != PLAYBACK_MODE_SPECTRAL &&
      previous_playback_mode_ != PLAYBACK_MODE_LAST;

  if (!reset_buffers_ && playback_mode_changed && benign_change) {
    ResetFilters();
    pitch_shifter_.Clear();
    previous_playback_mode_ = playback_mode_;
  }

  if ((playback_mode_changed && !benign_change) || reset_buffers_) {
    parameters_.freeze = false;
  }

  if (reset_buffers_ || (playback_mode_changed && !benign_change)) {
    buffers_ready_ = false;
    if ((num_channels_ != 1 && num_channels_ != 2) ||
        playback_mode_ < PLAYBACK_MODE_GRANULAR ||
        playback_mode_ >= PLAYBACK_MODE_LAST ||
        buffer_[0] == NULL || buffer_[1] == NULL ||
        buffer_size_[0] < 86144 || buffer_size_[1] < 32768) {
      return;
    }

    void* buffer[2] = { NULL, NULL };
    size_t buffer_size[2] = { 0, 0 };
    void* workspace = NULL;
    size_t workspace_size = 0;
    const bool spectral = playback_mode_ == PLAYBACK_MODE_SPECTRAL;

    if (num_channels_ == 1) {
      buffer[0] = buffer_[0];
      if (spectral) {
        // Mono Spectral keeps the stock 4096 FFT. The large allocation is
        // entirely its vocoder arena; the small allocation is reverb-only.
        buffer_size[0] = buffer_size_[0];
        workspace = buffer_[1];
        workspace_size = buffer_size_[1];
      } else {
        // Mono non-Spectral: 32 KiB recording followed by the full 53,376 B
        // FX workspace inside the 86,144 B large POOL allocation.
        buffer_size[0] = 32768;
        workspace = static_cast<uint8_t*>(buffer_[0]) + 32768;
        workspace_size = buffer_size_[0] - 32768;
      }
    } else {
      // Stereo: 32 KiB per channel; preserve the 53,376 B workspace tail.
      buffer[0] = buffer_[0];
      buffer[1] = buffer_[1];
      buffer_size[0] = buffer_size[1] = buffer_size_[1];
      workspace = static_cast<uint8_t*>(buffer_[0]) + buffer_size[0];
      workspace_size = buffer_size_[0] - buffer_size[0];
    }

    const size_t required_workspace =
        spectral ? 32768u : 41752u;
    if (workspace == NULL || workspace_size < required_workspace ||
        buffer[0] == NULL ||
        (num_channels_ == 2 && buffer[1] == NULL)) {
      return;
    }

    BufferAllocator allocator(workspace, workspace_size);
    float* diffuser_buffer = NULL;
    uint16_t* reverb_buffer = NULL;
    uint32_t* correlator_data = NULL;
    size_t correlator_block_size = (kMaxWSOLASize / 32) + 2;

    if (!spectral) {
      diffuser_buffer = allocator.Allocate<float>(2048);
    }
    reverb_buffer = allocator.Allocate<uint16_t>(16384);
    if (!spectral) {
      correlator_data = allocator.Allocate<uint32_t>(
          correlator_block_size * 3);
    }

    // Arithmetic preflight above is intentional: the allocator itself has
    // no alignment or bounds diagnostics. Keep explicit pointer checks too.
    if (reverb_buffer == NULL ||
        (!spectral && (diffuser_buffer == NULL || correlator_data == NULL))) {
      return;
    }

    reverb_.Init(reverb_buffer);
    if (!spectral) {
      diffuser_.Init(diffuser_buffer);
      correlator_.Init(
          &correlator_data[0],
          &correlator_data[correlator_block_size]);
      pitch_shifter_.Init((uint16_t*)correlator_data);
    }

    const float sr = sample_rate();
    if (spectral) {
      const size_t fft_size = num_channels_ == 1 ? 4096 : 2048;
      if (!phase_vocoder_.Init(
              buffer, buffer_size,
              lut_sine_window_4096, fft_size,
              num_channels_, resolution(), sr)) {
        return;
      }
    } else {
      for (int32_t i = 0; i < num_channels_; ++i) {
        if (resolution() == 8) {
          buffer_8_[i].Init(buffer[i], buffer_size[i], tail_buffer_[i]);
        } else {
          buffer_16_[i].Init(
              buffer[i], buffer_size[i] >> 1, tail_buffer_[i]);
        }
      }
      const int32_t num_grains =
          (num_channels_ == 1 ? 40 : 32) *
          (low_fidelity_ ? 23 : 16) >> 4;
      player_.Init(num_channels_, num_grains);
      ws_player_.Init(&correlator_, num_channels_);
      looper_.Init(num_channels_);
    }

    reset_buffers_ = false;
    previous_playback_mode_ = playback_mode_;
    buffers_ready_ = true;
  }

  if (!buffers_ready_) {
    return;
  }
  if (playback_mode_ == PLAYBACK_MODE_SPECTRAL) {
    phase_vocoder_.Buffer();
  } else if (playback_mode_ == PLAYBACK_MODE_STRETCH) {
    if (resolution() == 8) {
      ws_player_.LoadCorrelator(buffer_8_);
    } else {
      ws_player_.LoadCorrelator(buffer_16_);
    }
    correlator_.EvaluateSomeCandidates();
  }
}'''
    gp2 = gp[:start] + prepare + gp[end:]
    # Set all lifecycle flags deterministically before any DSP call.
    gp2 = replace_once(
        gp2,
        "  bypass_ = false;\n",
        "  bypass_ = false;\n  silence_ = false;\n  freeze_lp_ = 0.0f;\n  buffers_ready_ = false;\n",
        "processor init state")
    # Never run a processor whose current configuration has not passed Prepare().
    gp2 = replace_once(
        gp2,
        "  // TIC\n  if (bypass_) {",
        """  // Reject oversized blocks and any configuration that has not passed
  // the complete buffer-layout and FFT/texture preflight.
  if (size > kMaxBlockSize) {
    return;
  }
  if (!buffers_ready_ || reset_buffers_ ||
      previous_playback_mode_ != playback_mode_) {
    short* output_samples = &output[0].l;
    fill(&output_samples[0], &output_samples[size << 1], 0);
    return;
  }

  // TIC
  if (bypass_) {""",
        "process readiness gate")
    # Persistent data must not include mono FX workspace as though it were recording.
    gp2 = replace_once(
        gp2,
        "    block->size = buffer_size_[num_channels_ - 1];",
        """    block->size = (num_channels_ == 1 &&
        playback_mode_ != PLAYBACK_MODE_SPECTRAL)
        ? 32768 : buffer_size_[num_channels_ - 1];""",
        "persistent buffer size")
    gp2 = replace_once(
        gp2,
        "      Prepare();\n      GetPersistentData(block, &num_blocks);",
        """      Prepare();
      if (!buffers_ready_) {
        silence_ = false;
        return false;
      }
      GetPersistentData(block, &num_blocks);""",
        "persistent load prepare guard")
    (out / "granular_processor.cc").write_text(gp2)

    return {
        "workspace_non_spectral": NON_SPECTRAL_WORKSPACE,
        "stereo_spectral_2048_per_channel": 10 * 2048 + 3 * (1024 - 16) * 4,
        "mono_spectral_4096": 14 * 4096 + 3 * (2048 - 16) * 4,
    }
