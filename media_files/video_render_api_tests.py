"""Tests for video render API helpers."""

from pathlib import Path

import pytest
from django.test import override_settings

from tools.api import _resolve_intro_outro_paths


@pytest.mark.django_db
def test_resolve_intro_outro_paths_uses_media_root(tmp_path):
    media_root = tmp_path / "media"
    intro_outro_dir = media_root / "intro_outro"
    intro_outro_dir.mkdir(parents=True)
    intro = intro_outro_dir / "intro.mp4"
    outro = intro_outro_dir / "outro.mp4"
    intro.write_bytes(b"intro")
    outro.write_bytes(b"outro")

    with override_settings(MEDIA_ROOT=str(media_root), BASE_DIR=str(tmp_path)):
        intro_path, outro_path = _resolve_intro_outro_paths()

    assert intro_path == str(intro.resolve())
    assert outro_path == str(outro.resolve())


@pytest.mark.django_db
def test_resolve_intro_outro_paths_returns_none_when_missing(tmp_path):
    media_root = tmp_path / "media"
    media_root.mkdir(parents=True)

    with override_settings(MEDIA_ROOT=str(media_root), BASE_DIR=str(tmp_path)):
        intro_path, outro_path = _resolve_intro_outro_paths()

    if intro_path is not None:
        assert Path(intro_path).exists()
    if outro_path is not None:
        assert Path(outro_path).exists()
