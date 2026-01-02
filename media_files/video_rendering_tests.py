"""Tests for video rendering presets and helpers."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from media_files.rendering.presets import load_encode_preset, load_style_preset
from media_files.rendering.templates import build_template_context, render_text_template


@pytest.mark.django_db
def test_render_text_template_license_fields(license):
    ctx = build_template_context(license)
    out = render_text_template("{license.number} {license.title} {license.subtitle}", ctx)
    assert str(license.number) in out
    assert (license.title or "") in out


@pytest.mark.django_db
def test_load_presets_smoke():
    style = load_style_preset("lower_third_v1")
    encode = load_encode_preset("1080p25_9000k")

    assert style.name == "lower_third_v1"
    assert style.intro_clip
    assert style.outro_clip
    assert encode.width == 1920
    assert encode.height == 1080
    assert encode.fps == 25

    style2 = load_style_preset("overlay_only_center_left_v1")
    assert style2.intro_clip is None
    assert style2.outro_clip is None


@pytest.mark.django_db
@override_settings(VIDEO_OVERLAY_RENDERING_ENABLED=False)
def test_management_command_refuses_when_disabled():
    with pytest.raises(CommandError):
        call_command(
            "render_video_preset",
            "--license-number",
            "12345",
            "--style",
            "lower_third_v1",
            "--encode",
            "1080p25_9000k",
            "--dry-run",
        )


