"""Audio normalization service (EBU R128 loudnorm) for Tools module."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from django.conf import settings

from tools.models import AudioNormalizeJob, ToolsConfig

logger = logging.getLogger('django')


class PresetError(ValueError):
    """Raised when presets JSON is invalid or missing required fields."""


class AudioNormalizerError(RuntimeError):
    """Raised when ffprobe/ffmpeg pipeline fails."""


def load_audio_presets() -> Dict[str, Any]:
    """Load audio presets JSON bundled with the tools module."""
    presets_path = Path(__file__).resolve().parent / "audio_presets.json"
    try:
        return json.loads(presets_path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise PresetError(f"Presets file not found: {presets_path}") from e
    except json.JSONDecodeError as e:
        raise PresetError(f"Invalid presets JSON: {presets_path}: {e}") from e


def _get(d: Dict[str, Any], path: str, default: Any = None) -> Any:
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _require(d: Dict[str, Any], path: str) -> Any:
    v = _get(d, path, None)
    if v is None:
        raise PresetError(f"Missing required field: '{path}'")
    return v


def _fmt_float(x: Any) -> str:
    try:
        return f"{float(x):.3f}".rstrip("0").rstrip(".")
    except Exception as e:
        raise PresetError(f"Invalid float value: {x!r}") from e


def _fmt_int(x: Any) -> str:
    try:
        return str(int(x))
    except Exception as e:
        raise PresetError(f"Invalid int value: {x!r}") from e


def get_preset(presets_json: Dict[str, Any], preset_id: str) -> Dict[str, Any]:
    presets = presets_json.get("presets", [])
    for p in presets:
        if p.get("id") == preset_id:
            return p
    raise PresetError(f"Preset not found: {preset_id}")


def resolve_loudnorm_target(
    presets_json: Dict[str, Any],
    preset: Dict[str, Any],
    target: str,
) -> Dict[str, Any]:
    """
    Returns dict with keys: I, TP, LRA, linear
    Priority: preset.filters.loudnorm overrides presets_json.defaults.<target>
    """
    if target not in ("tv", "web"):
        raise PresetError(f"Unknown target: {target}")

    defaults = _get(presets_json, f"defaults.{target}", {}) or {}
    ln = _get(preset, "filters.loudnorm", None)
    if ln is None:
        ln = defaults

    I = _require({"ln": ln}, "ln.I")
    TP = _require({"ln": ln}, "ln.TP")
    LRA = _require({"ln": ln}, "ln.LRA")
    linear = ln.get("linear", True)

    return {"I": I, "TP": TP, "LRA": LRA, "linear": bool(linear)}


def build_loudnorm_analyze_chain(
    presets_json: Dict[str, Any],
    preset: Dict[str, Any],
    target: str = "tv",
) -> str:
    """Build -af chain for loudnorm analysis pass (raw input analysis)."""
    ln = resolve_loudnorm_target(presets_json, preset, target=target)
    return (
        "loudnorm="
        f"I={_fmt_float(ln['I'])}:"
        f"TP={_fmt_float(ln['TP'])}:"
        f"LRA={_fmt_float(ln['LRA'])}:"
        f"linear={'true' if ln['linear'] else 'false'}:"
        "print_format=json"
    )


def build_process_chain(
    presets_json: Dict[str, Any],
    preset: Dict[str, Any],
    target: str = "tv",
    measured: Optional[Dict[str, Any]] = None,
    print_format: str = "summary",
) -> str:
    """Build -af chain for processing pass."""
    if target not in ("tv", "web"):
        raise PresetError(f"Unknown target: {target}")
    if print_format not in ("summary", "json"):
        raise PresetError("print_format must be 'summary' or 'json'")

    parts: list[str] = []

    hp = _get(preset, "filters.highpass_hz", None)
    if hp is not None:
        parts.append(f"highpass=f={_fmt_int(hp)}")

    nf = _get(preset, "filters.denoise_nf_db", None)
    if nf is not None:
        parts.append(f"afftdn=nf={_fmt_float(nf)}")

    comp = _get(preset, "filters.compressor", None)
    if isinstance(comp, dict):
        thr = _require({"c": comp}, "c.threshold_db")
        ratio = _require({"c": comp}, "c.ratio")
        attack = _require({"c": comp}, "c.attack_ms")
        release = _require({"c": comp}, "c.release_ms")
        parts.append(
            "acompressor="
            f"threshold={_fmt_float(thr)}dB:"
            f"ratio={_fmt_float(ratio)}:"
            f"attack={_fmt_float(attack)}:"
            f"release={_fmt_float(release)}"
        )

    lim = _get(preset, "filters.limiter_db", None)
    if lim is not None:
        parts.append(f"alimiter=limit={_fmt_float(lim)}dB")

    ln = resolve_loudnorm_target(presets_json, preset, target=target)
    ln_args = (
        f"I={_fmt_float(ln['I'])}:"
        f"TP={_fmt_float(ln['TP'])}:"
        f"LRA={_fmt_float(ln['LRA'])}:"
        f"linear={'true' if ln['linear'] else 'false'}:"
        f"print_format={print_format}"
    )

    if measured:
        mI = measured.get("measured_I", measured.get("input_i"))
        mTP = measured.get("measured_TP", measured.get("input_tp"))
        mLRA = measured.get("measured_LRA", measured.get("input_lra"))
        mTH = measured.get("measured_thresh", measured.get("input_thresh"))
        off = measured.get("offset", measured.get("target_offset"))

        if any(v is None for v in (mI, mTP, mLRA, mTH, off)):
            missing = [k for k, v in {
                "measured_I/input_i": mI,
                "measured_TP/input_tp": mTP,
                "measured_LRA/input_lra": mLRA,
                "measured_thresh/input_thresh": mTH,
                "offset/target_offset": off,
            }.items() if v is None]
            raise PresetError(f"Measured dict missing fields: {', '.join(missing)}")

        ln_args += (
            f":measured_I={_fmt_float(mI)}"
            f":measured_TP={_fmt_float(mTP)}"
            f":measured_LRA={_fmt_float(mLRA)}"
            f":measured_thresh={_fmt_float(mTH)}"
            f":offset={_fmt_float(off)}"
        )

    parts.append(f"loudnorm={ln_args}")
    return ",".join(parts)


def parse_loudnorm_json_from_stderr(stderr_text: str) -> Dict[str, Any]:
    """
    Extract the last loudnorm JSON object from FFmpeg stderr.
    loudnorm print_format=json prints a JSON object to stderr.
    """
    # Fast path: try to find JSON blocks with a strict-ish regex.
    # We accept nested braces poorly, but loudnorm JSON is flat.
    candidates = re.findall(r"\{(?:[^{}]|\\\{|\\\})*\}", stderr_text, flags=re.MULTILINE)
    for raw in reversed(candidates):
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        if isinstance(obj, dict) and ("input_i" in obj or "measured_I" in obj):
            return obj

    # Fallback: scan backwards from last '{' to last '}'.
    last_start = stderr_text.rfind("{")
    last_end = stderr_text.rfind("}")
    if last_start != -1 and last_end != -1 and last_end > last_start:
        window = stderr_text[last_start:last_end + 1]
        try:
            obj = json.loads(window)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    raise AudioNormalizerError("Could not find loudnorm JSON in FFmpeg stderr.")


@dataclass(frozen=True)
class ProbeInfo:
    duration_sec: float
    has_video: bool
    has_audio: bool


class AudioNormalizerService:
    """End-to-end ffprobe + ffmpeg pipeline for AudioNormalizeJob."""

    def __init__(self, job: AudioNormalizeJob):
        self.job = job
        self.config = ToolsConfig.get_config()
        self.ffmpeg = getattr(settings, "TOOLS_FFMPEG_PATH", self.config.ffmpeg_path)
        self.ffprobe = getattr(settings, "TOOLS_FFPROBE_PATH", self.config.ffprobe_path)
        self.presets_json = load_audio_presets()

    def _media_root_abs(self) -> Path:
        """
        Return MEDIA_ROOT as an absolute path.

        In this project MEDIA_ROOT may be relative (e.g. 'media/'), which breaks
        Path.relative_to() when our output path is absolute (e.g. '/app/media/...').
        """
        media_root = Path(getattr(settings, "MEDIA_ROOT", "media/"))
        if media_root.is_absolute():
            return media_root.resolve()
        base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
        return (base_dir / media_root).resolve()

    def _run(self, cmd: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        logger.debug("Running command: %s", " ".join(cmd[:10]) + (" ..." if len(cmd) > 10 else ""))
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        except FileNotFoundError as e:
            raise AudioNormalizerError(f"Executable not found: {cmd[0]}") from e
        except subprocess.TimeoutExpired as e:
            raise AudioNormalizerError(f"Command timed out after {timeout}s") from e

    def probe(self, input_path: Path) -> tuple[Dict[str, Any], ProbeInfo]:
        cmd = [
            self.ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(input_path),
        ]
        p = self._run(cmd, timeout=60)
        if p.returncode != 0:
            raise AudioNormalizerError(f"ffprobe failed: {p.stderr.strip()[:2000]}")

        data = json.loads(p.stdout or "{}")
        has_video = False
        has_audio = False
        duration_sec = 0.0

        fmt = data.get("format") or {}
        try:
            duration_sec = float(fmt.get("duration") or 0.0)
        except Exception:
            duration_sec = 0.0

        for s in (data.get("streams") or []):
            if s.get("codec_type") == "video":
                has_video = True
            if s.get("codec_type") == "audio":
                has_audio = True
                if not duration_sec:
                    try:
                        duration_sec = max(duration_sec, float(s.get("duration") or 0.0))
                    except Exception:
                        pass

        return data, ProbeInfo(duration_sec=duration_sec or 0.0, has_video=has_video, has_audio=has_audio)

    def analyze_loudnorm(self, input_path: Path) -> Dict[str, Any]:
        preset = get_preset(self.presets_json, self.job.preset_id)
        af = build_loudnorm_analyze_chain(self.presets_json, preset, target=self.job.target)

        cmd = [
            self.ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(input_path),
            "-vn",
            "-sn",
            "-dn",
            "-af",
            af,
            "-f",
            "null",
            "-",
        ]
        p = self._run(cmd, timeout=60 * 20)
        # loudnorm prints json to stderr even on success
        if p.returncode != 0:
            raise AudioNormalizerError(f"ffmpeg analyze failed: {p.stderr.strip()[:2000]}")
        return parse_loudnorm_json_from_stderr(p.stderr or "")

    def _build_output_filename(self, input_path: Path) -> str:
        if self.job.output_filename:
            name = self.job.output_filename.strip()
            return name
        # If input was stored with a version suffix (e.g. foo_v1.mp4), don't carry it into the output name.
        stem = input_path.stem
        m = re.match(r"^(?P<base>.+)_v\d+$", stem)
        base_stem = m.group("base") if m else stem
        return f"{base_stem}_R128.mp4"

    def _resolve_output_dir(self, input_path: Path) -> Path:
        """
        Resolve output directory.

        - If ToolsConfig.audio_normalize_output_storage is set: use storage.path (mounted disk, can be outside MEDIA_ROOT).
        - Else if ToolsConfig.audio_normalize_output_path is set: use it (relative to MEDIA_ROOT if not absolute).
        - Otherwise: store output next to the input file.

        When output is outside MEDIA_ROOT, run_full_pipeline returns output_path_external and the
        task stores it on the job; output_file is left empty.
        """
        storage = getattr(self.config, "audio_normalize_output_storage", None)
        if storage and getattr(storage, "path", None):
            p = Path(storage.path).resolve()
            p.mkdir(parents=True, exist_ok=True)
            return p

        configured = (self.config.audio_normalize_output_path or "").strip()
        if configured:
            p = Path(configured)
            if not p.is_absolute():
                p = Path(settings.MEDIA_ROOT) / configured.lstrip("/\\")
            p = p.resolve()
            p.mkdir(parents=True, exist_ok=True)
            return p

        p = input_path.parent.resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _pick_output_path(self, input_path: Path) -> Path:
        out_dir = self._resolve_output_dir(input_path)
        base_name = self._build_output_filename(input_path)

        # Ensure extension is mp4 by default (keeps video copy compatible)
        out_path = out_dir / base_name
        if out_path.suffix.lower() != ".mp4":
            out_path = out_path.with_suffix(".mp4")

        # Avoid overwriting existing outputs
        if not out_path.exists():
            return out_path

        stem = out_path.stem
        for i in range(1, 100):
            candidate = out_path.with_name(f"{stem}_v{i}{out_path.suffix}")
            if not candidate.exists():
                return candidate

        raise AudioNormalizerError("Could not allocate a unique output filename.")

    def get_recommendations(self, analysis_before: Dict[str, Any]) -> list[Dict[str, Any]]:
        recs: list[Dict[str, Any]] = []
        try:
            input_lra = float(analysis_before.get("input_lra") or analysis_before.get("measured_LRA") or 0.0)
        except Exception:
            input_lra = 0.0
        try:
            input_tp = float(analysis_before.get("input_tp") or analysis_before.get("measured_TP") or 0.0)
        except Exception:
            input_tp = 0.0

        if input_lra > 14:
            recs.append({
                "preset_id": "tv_strong",
                "reason": "High dynamics (LRA > 14). Consider stronger processing.",
            })
        if input_tp > -1.0:
            recs.append({
                "preset_id": "tv_strong",
                "reason": "TruePeak above target. Strong preset + limiter may reduce clipping risk.",
            })
        return recs

    def normalize(
        self,
        input_path: Path,
        output_path: Path,
        measured: Optional[Dict[str, Any]],
        probe: ProbeInfo,
        on_progress: Optional[callable] = None,
    ) -> str:
        """
        Run process pass. Returns full FFmpeg stderr log text.
        """
        preset = get_preset(self.presets_json, self.job.preset_id)

        # For fast_auto (linear=false) it's fine to run without measured params.
        ln = _get(preset, "filters.loudnorm", {}) or {}
        linear = bool(ln.get("linear", True))
        if linear and measured is None:
            raise AudioNormalizerError("2-pass loudnorm requires measured values, but none were provided.")

        af = build_process_chain(
            self.presets_json,
            preset,
            target=self.job.target,
            measured=measured if linear else None,
            print_format="summary",
        )

        # Map only video+audio to keep the output stable across containers.
        cmd = [
            self.ffmpeg,
            "-hide_banner",
            "-y",
            "-i",
            str(input_path),
            "-map",
            "0:v?",
            "-map",
            "0:a?",
        ]

        if probe.has_video:
            cmd += ["-c:v", "copy"]

        # Audio settings
        cmd += ["-c:a", "aac", "-b:a", self.job.audio_bitrate, "-ar", str(self.job.sample_rate)]
        if self.job.force_stereo:
            cmd += ["-ac", "2"]

        cmd += ["-af", af]

        # MP4 hints
        if output_path.suffix.lower() == ".mp4":
            cmd += ["-movflags", "+faststart"]

        # Progress to stdout
        cmd += ["-progress", "pipe:1", "-nostats", str(output_path)]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        stderr_lines: list[str] = []
        duration_ms = max(int(probe.duration_sec * 1000), 1)
        last_percent = -1

        def update_percent(out_time_ms: int):
            nonlocal last_percent
            percent = int(min(100, max(0, (out_time_ms / duration_ms) * 100)))
            if percent != last_percent:
                last_percent = percent
                if on_progress:
                    on_progress(percent)

        # Parse progress stream (stdout) and collect stderr
        try:
            assert process.stdout is not None
            assert process.stderr is not None

            # Read stdout (progress) in real-time
            for line in process.stdout:
                line = line.strip()
                if not line or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key == "out_time_ms":
                    try:
                        update_percent(int(value))
                    except Exception:
                        pass
                elif key == "progress" and value == "end":
                    update_percent(duration_ms)

            # Drain stderr at end (or while running if it fills up, but typical ffmpeg output is fine)
            stderr_text = process.stderr.read()
            if stderr_text:
                stderr_lines.extend(stderr_text.splitlines())
        finally:
            rc = process.wait()

        if rc != 0:
            tail = "\n".join(stderr_lines[-200:])
            raise AudioNormalizerError(f"ffmpeg process failed (code {rc}):\n{tail}")

        return "\n".join(stderr_lines)

    def run_full_pipeline(self) -> Dict[str, Any]:
        """
        High-level helper for Celery: probe -> analyze -> process -> verify.
        Updates job fields but does not save files to FileField (done by task).
        Input can be job.input_file (under MEDIA_ROOT) or job.input_path_external (e.g. storage).
        """
        ext = (getattr(self.job, 'input_path_external', '') or '').strip()
        if ext:
            input_path = Path(ext)
        elif self.job.input_file:
            input_path = Path(self.job.input_file.path)
        else:
            raise AudioNormalizerError("Job has no input file.")

        if not input_path.exists():
            raise AudioNormalizerError(f"Input file not found: {input_path}")

        meta, probe_info = self.probe(input_path)
        before = self.analyze_loudnorm(input_path)

        out_path = self._pick_output_path(input_path)

        def on_progress(percent: int):
            AudioNormalizeJob.objects.filter(id=self.job.id).update(progress=percent)

        ffmpeg_log = self.normalize(
            input_path=input_path,
            output_path=out_path,
            measured=before,
            probe=probe_info,
            on_progress=on_progress,
        )

        after = self.analyze_loudnorm(out_path)

        media_root = self._media_root_abs()
        resolved = out_path.resolve()
        output_relpath = None
        output_path_external = None
        try:
            output_relpath = str(resolved.relative_to(media_root)).replace("\\", "/")
        except ValueError:
            output_path_external = str(resolved)

        return {
            "input_metadata": meta,
            "analysis_before": before,
            "analysis_after": after,
            "output_path": str(out_path),
            "output_relpath": output_relpath,
            "output_path_external": output_path_external,
            "ffmpeg_log": ffmpeg_log,
            "probe": {"duration_sec": probe_info.duration_sec, "has_video": probe_info.has_video, "has_audio": probe_info.has_audio},
            "recommendations": self.get_recommendations(before),
        }

