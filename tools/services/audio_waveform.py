"""Waveform generation helpers for audio normalization UI."""

from __future__ import annotations

import array
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from django.conf import settings

from tools.models import AudioNormalizeJob, ToolsConfig


class WaveformError(RuntimeError):
    """Raised when waveform generation fails."""


@dataclass(frozen=True)
class WaveformResult:
    peaks: list[float]
    sample_rate: int
    duration_sec: float
    points: int


def _get_ffmpeg_path() -> str:
    config = ToolsConfig.get_config()
    return getattr(settings, "TOOLS_FFMPEG_PATH", config.ffmpeg_path)


def get_waveform_cache_path(job_id: int, kind: str) -> Path:
    kind_key = "before" if kind == "before" else "after"
    base = Path(settings.MEDIA_ROOT) / f"tools/audio_normalize/{job_id}/waveform"
    return base / f"{kind_key}.json"


def _run_ffmpeg_to_pcm(input_path: Path, sample_rate: int) -> bytes:
    cmd = [
        _get_ffmpeg_path(),
        "-hide_banner",
        "-v",
        "error",
        "-i",
        str(input_path),
        "-vn",
        "-sn",
        "-dn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "s16le",
        "pipe:1",
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, check=False)
    except FileNotFoundError as e:
        raise WaveformError(f"FFmpeg not found: {cmd[0]}") from e

    if p.returncode != 0:
        raise WaveformError((p.stderr or b"").decode("utf-8", errors="ignore")[:2000])
    return p.stdout or b""


def _samples_to_peaks(samples: array.array, points: int) -> list[float]:
    if not samples or points <= 0:
        return []

    total = len(samples)
    if total == 0:
        return []

    if total <= points:
        return [abs(s) / 32768.0 for s in samples]

    step = total / points
    peaks: list[float] = []
    idx = 0.0
    for _ in range(points):
        start = int(idx)
        end = int(idx + step)
        end = min(end, total)
        if end <= start:
            end = min(start + 1, total)
        chunk = samples[start:end]
        peak = max(abs(s) for s in chunk) if chunk else 0
        peaks.append(peak / 32768.0)
        idx += step
    return peaks


def generate_waveform(
    input_path: Path,
    duration_sec: float,
    target_points: int = 1000,
) -> WaveformResult:
    if not input_path.exists():
        raise WaveformError(f"Input file not found: {input_path}")

    duration_sec = max(duration_sec, 0.1)
    target_points = max(200, min(4000, target_points))
    sample_rate = max(50, min(2000, int(target_points / duration_sec)))

    raw = _run_ffmpeg_to_pcm(input_path, sample_rate=sample_rate)
    samples = array.array("h")
    samples.frombytes(raw)

    peaks = _samples_to_peaks(samples, target_points)
    return WaveformResult(
        peaks=peaks,
        sample_rate=sample_rate,
        duration_sec=duration_sec,
        points=len(peaks),
    )


def load_or_generate_waveform(
    job: AudioNormalizeJob,
    kind: str,
    input_path: Path,
    duration_sec: float,
) -> Dict[str, Any]:
    cache_path = get_waveform_cache_path(job.id, kind)
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    result = generate_waveform(input_path, duration_sec=duration_sec)
    payload = {
        "peaks": result.peaks,
        "sample_rate": result.sample_rate,
        "duration_sec": result.duration_sec,
        "points": result.points,
    }
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    return payload
