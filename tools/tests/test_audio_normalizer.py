"""Tests for audio normalizer helpers and filter-chain behavior."""

from __future__ import annotations

from django.test import SimpleTestCase

from tools.services.audio_normalizer import (
    build_process_chain,
    load_audio_presets,
    parse_loudnorm_normalization_type,
)


class AudioNormalizerHelpersTest(SimpleTestCase):
    """Unit tests for loudnorm guardrail behavior."""

    def setUp(self):
        self.presets = load_audio_presets()
        self.preset_tv_natural = next(p for p in self.presets["presets"] if p.get("id") == "tv_natural")

    def test_build_process_chain_clamps_lra_to_measured_for_linear_mode(self):
        measured = {
            "input_i": -26.8,
            "input_tp": -8.2,
            "input_lra": 14.3,
            "input_thresh": -37.4,
            "target_offset": -0.4,
        }

        chain = build_process_chain(
            self.presets,
            self.preset_tv_natural,
            target="tv",
            measured=measured,
            print_format="summary",
            rnn_model_path=None,
        )

        self.assertIn("loudnorm=", chain)
        self.assertIn("linear=true", chain)
        self.assertIn("LRA=14.3", chain)
        self.assertNotIn("LRA=11", chain)

    def test_build_process_chain_includes_compressor_linking(self):
        measured = {
            "input_i": -23.5,
            "input_tp": -6.1,
            "input_lra": 10.0,
            "input_thresh": -33.0,
            "target_offset": 0.0,
        }
        chain = build_process_chain(
            self.presets,
            self.preset_tv_natural,
            target="tv",
            measured=measured,
            print_format="summary",
            rnn_model_path=None,
        )
        self.assertIn("acompressor=", chain)
        self.assertIn("link=average", chain)

    def test_parse_loudnorm_normalization_type(self):
        stderr_dynamic = """
        [Parsed_loudnorm_0 @ 0x1] Input Integrated: -26.8 LUFS
        Normalization Type: Dynamic
        Target Offset: -0.4 LU
        """
        stderr_linear = "Normalization Type: Linear"
        stderr_unknown = "No normalization block"

        self.assertEqual(parse_loudnorm_normalization_type(stderr_dynamic), "dynamic")
        self.assertEqual(parse_loudnorm_normalization_type(stderr_linear), "linear")
        self.assertIsNone(parse_loudnorm_normalization_type(stderr_unknown))

