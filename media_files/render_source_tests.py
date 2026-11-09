"""Choice of the source video for rendering and short middle segments.

Case 09.11.2026 (license 18567): a preview (10 s) and later the rendered
_v1 lie next to the original. The render picked the newest file, i.e. the
preview, and failed on a 13 ms middle segment.
"""

from media_files.models import StorageLocation
from media_files.models import VideoFile
from media_files.rendering import ffmpeg
from pathlib import Path
from tools.rendering.presets import load_encode_preset
from unittest.mock import patch
import pytest


NUMBER = 18567


@pytest.fixture
def storage(db):
    return StorageLocation.objects.create(
        name='Planung', storage_type='PLAYOUT', path='/tmp/planung/', is_active=True)


def _video(storage, filename, **kwargs):
    defaults = dict(number=NUMBER, storage_location=storage, file_path=filename,
                    is_available=True)
    defaults.update(kwargs)
    return VideoFile.objects.create(filename=filename, **defaults)


def test_render_source__skips_preview(storage):
    original = _video(storage, '18567_Kettel.mp4')
    _video(storage, '18567_Kettel_preview_v1.mp4', is_preview=True)

    assert VideoFile.render_source_for(NUMBER) == original


def test_render_source__skips_rendered_versions(storage):
    original = _video(storage, '18567_Kettel.mp4')
    _video(storage, '18567_Kettel_v1.mp4')
    _video(storage, '18567_Kettel_v2.mp4')
    _video(storage, 'rendered/18567_Kettel_render.mp4')

    assert VideoFile.render_source_for(NUMBER) == original


def test_render_source__manual_primary_first(storage):
    _video(storage, '18567_Kettel.mp4')
    corrected = _video(storage, '18567_Kettel_korrigiert.mp4', is_manual_primary=True)

    assert VideoFile.render_source_for(NUMBER) == corrected


def test_render_source__oldest_original_otherwise(storage):
    first = _video(storage, '18567_Kettel.mp4')
    _video(storage, '18567_Kettel_kopie.mp4')

    assert VideoFile.render_source_for(NUMBER) == first


def test_render_source__no_original(storage):
    preview = _video(storage, '18567_Kettel_preview_v1.mp4', is_preview=True)
    rendered = _video(storage, '18567_Kettel_v1.mp4')

    assert VideoFile.render_source_for(NUMBER) is None
    # a rendered or preview file is not used as fallback either
    assert VideoFile.render_source_for(NUMBER, fallback=rendered) is None
    assert VideoFile.render_source_for(NUMBER, fallback=preview) is None


def test_render_source__unavailable_original_uses_fallback(storage):
    _video(storage, '18567_Kettel.mp4', is_available=False)
    linked = _video(storage, '18567_Kettel_archiv.mp4', number=99999)

    assert VideoFile.render_source_for(NUMBER, fallback=linked) == linked


def _segments(duration, segment=5.0):
    """Run render_with_overlays_on_main_edges with ffmpeg mocked; return the
    (ss, t) of the edge segments and whether a middle part was rendered."""
    calls = []
    middle = []

    def fake_segment(main_video, out_ts, *args, ss, t, **kwargs):
        calls.append((round(ss, 3), round(t, 3)))
        Path(out_ts).write_bytes(b'x')

    with patch.object(ffmpeg, '_duration_seconds', return_value=duration), \
            patch.object(ffmpeg, '_source_fps', return_value=25.0), \
            patch.object(ffmpeg, '_source_is_vfr', return_value=False), \
            patch.object(ffmpeg, '_has_audio', return_value=True), \
            patch.object(ffmpeg, '_render_segment_to_ts', side_effect=fake_segment), \
            patch.object(ffmpeg, '_run', side_effect=lambda cmd, **kw: middle.append(cmd)), \
            patch.object(ffmpeg, '_concat_ts_to_mp4'):
        ffmpeg.render_with_overlays_on_main_edges(
            main_video='in.mp4', output_mp4='/tmp/oktools_test_out/out.mp4',
            encode=load_encode_preset('1080p25_9000k'),
            intro_layers=[], outro_layers=[], ctx=None,
            segment_duration=segment)
    return calls, bool(middle)


def test_short_middle_is_not_rendered_on_its_own():
    """10.013 s (the 09.11 preview): a 13 ms middle part made ffmpeg fail."""
    calls, rendered_middle = _segments(10.013)

    assert not rendered_middle
    # first 5 s, then the rest in one segment: nothing lost, nothing twice
    assert calls == [(0.0, 5.0), (5.0, 5.013)]


@pytest.mark.parametrize('duration', [10.02, 10.04, 10.49])
def test_middle_below_half_a_second_goes_to_the_last_segment(duration):
    calls, rendered_middle = _segments(duration)

    assert not rendered_middle
    assert calls[-1] == (5.0, round(duration - 5.0, 3))


def test_long_video_keeps_its_middle_segment():
    calls, rendered_middle = _segments(48 * 60 + 26)

    assert rendered_middle
    assert calls == [(0.0, 5.0), (2901.0, 5.0)]


@pytest.mark.skipif(not __import__('shutil').which('ffmpeg'), reason='ffmpeg not installed')
def test_render_10_02_seconds_with_real_ffmpeg(tmp_path):
    """The failing case end to end: 10.02 s with sound, 25 fps."""
    import subprocess

    source = tmp_path / 'in.mp4'
    subprocess.run([
        'ffmpeg', '-y', '-v', 'error',
        '-f', 'lavfi', '-i', 'testsrc2=size=1280x720:rate=25',
        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000',
        '-t', '10.02', '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac',
        str(source)], check=True)
    out = tmp_path / 'out.mp4'

    ffmpeg.render_with_overlays_on_main_edges(
        main_video=str(source), output_mp4=str(out),
        encode=load_encode_preset('1080p25_9000k'),
        intro_layers=[], outro_layers=[], ctx=None, segment_duration=5.0)

    assert out.exists()
    assert abs(ffmpeg._duration_seconds(str(out)) - 10.02) < 0.1


@pytest.mark.django_db
def test_render_page_shows_the_original_as_source(client, admin_user, license, storage):
    """Opened from the preview, the page names the original it will render."""
    from django.test import override_settings
    from django.urls import reverse

    original = _video(storage, f'{license.number}_Kettel.mp4', number=license.number)
    preview = _video(storage, f'{license.number}_Kettel_preview_v1.mp4',
                     number=license.number, is_preview=True)
    client.force_login(admin_user)
    with override_settings(TOOLS_ENABLED=True, MEDIA_FILES_ENABLED=True):
        response = client.get(reverse('tools:video_render', args=[preview.id]))

    assert response.status_code == 200
    assert response.context['render_source'] == original
    assert original.filename in response.content.decode()
