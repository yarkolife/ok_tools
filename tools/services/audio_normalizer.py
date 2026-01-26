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
from django.utils.translation import gettext_lazy as _

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
    rnn_model_path: Optional[str] = None,
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

    lp = _get(preset, "filters.lowpass_hz", None)
    if lp is not None:
        parts.append(f"lowpass=f={_fmt_int(lp)}")

    # Neural network denoiser (arnndn) - preferred for speech if model available
    arnndn_model = _get(preset, "filters.arnndn_model", None)
    arnndn_mix = _get(preset, "filters.arnndn_mix", 0.8)
    if arnndn_model or rnn_model_path:
        model_path = arnndn_model or rnn_model_path
        if model_path:
            parts.append(f"arnndn=m={model_path}:mix={_fmt_float(arnndn_mix)}")
    else:
        # Fallback to FFT-based denoiser (afftdn)
        nf = _get(preset, "filters.denoise_nf_db", None)
        if nf is not None:
            parts.append(f"afftdn=nf={_fmt_float(nf)}")

    # Dialogue enhance (FFmpeg 5+) - improves speech clarity in stereo
    de = _get(preset, "filters.dialoguenhance", None)
    if de is not None:
        if isinstance(de, dict):
            original = _fmt_float(de.get("original", 1.0))
            enhance = _fmt_float(de.get("enhance", 1.0))
            voice = _fmt_float(de.get("voice", 1.0))
            parts.append(f"dialoguenhance=original={original}:enhance={enhance}:voice={voice}")
        elif de is True:
            parts.append("dialoguenhance")

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
        # RNN model path for arnndn (can be set in settings or config)
        # Default to std.rnnn in tools/rnn_models/ if available
        self.rnn_model_path = getattr(settings, "TOOLS_ARNNDN_MODEL_PATH", None) or getattr(
            self.config, "arnndn_model_path", None
        )
        if not self.rnn_model_path:
            # Try default location: tools/rnn_models/std.rnnn
            default_model = Path(__file__).resolve().parent.parent / "rnn_models" / "std.rnnn"
            if default_model.exists():
                self.rnn_model_path = str(default_model)
        
        # Cache for available models directory
        self._models_dir = Path(__file__).resolve().parent.parent / "rnn_models"

    def get_available_models(self) -> Dict[str, Path]:
        """
        Get dictionary of available RNN models in the models directory.
        Returns dict with keys: 'std', 'bd', 'lq' and values as Path objects.
        """
        models = {}
        model_files = {
            "std": self._models_dir / "std.rnnn",
            "bd": self._models_dir / "bd.rnnn",
            "lq": self._models_dir / "lq.rnnn",
        }
        for key, path in model_files.items():
            if path.exists():
                models[key] = path
        return models
    
    def get_model_path(self, model_id: Optional[str] = None) -> Optional[str]:
        """
        Get path to RNN model. If model_id is provided and model exists, return that.
        Otherwise return default rnn_model_path.
        
        Args:
            model_id: One of 'std', 'bd', 'lq', or None for default
            
        Returns:
            Path to model file as string, or None if not available
        """
        if model_id:
            available = self.get_available_models()
            if model_id in available:
                return str(available[model_id])
        
        # Fallback to configured/default path
        return self.rnn_model_path

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

    def analyze_noise(self, input_path: Path) -> Dict[str, Any]:
        """
        Analyze noise characteristics using silencedetect and astats.
        Returns dict with noise_level, silence_ratio, peak_level, noise_type, recommended_model, etc.
        """
        results: Dict[str, Any] = {
            "silence_ratio": 0.0,
            "noise_level_db": None,
            "peak_level_db": None,
            "mean_level_db": None,
            "noise_type": None,  # "wind", "low_quality", "general", "minimal"
            "recommended_model": None,  # "std", "bd", "lq", None
        }

        # Analyze silence detection
        cmd_silence = [
            self.ffmpeg,
            "-hide_banner",
            "-i",
            str(input_path),
            "-af",
            "silencedetect=n=-35dB:d=0.3",
            "-f",
            "null",
            "-",
        ]
        p_silence = self._run(cmd_silence, timeout=60 * 5)
        if p_silence.returncode == 0:
            stderr = p_silence.stderr or ""
            # Count silence detections
            silence_count = len(re.findall(r"silence_start:", stderr))
            silence_duration = 0.0
            for match in re.finditer(r"silence_duration: ([\d.]+)", stderr):
                silence_duration += float(match.group(1))
            # Get duration from probe
            try:
                meta, probe_info = self.probe(input_path)
                duration = probe_info.duration_sec
                if duration > 0:
                    results["silence_ratio"] = min(1.0, silence_duration / duration)
            except Exception:
                pass

        # Analyze audio statistics
        cmd_stats = [
            self.ffmpeg,
            "-hide_banner",
            "-i",
            str(input_path),
            "-af",
            "astats=metadata=1:reset=1",
            "-f",
            "null",
            "-",
        ]
        p_stats = self._run(cmd_stats, timeout=60 * 5)
        if p_stats.returncode == 0:
            stderr = p_stats.stderr or ""
            # Extract peak and mean levels
            peak_match = re.search(r"Peak level: ([\d.-]+) dB", stderr)
            if peak_match:
                results["peak_level_db"] = float(peak_match.group(1))
            mean_match = re.search(r"Mean level: ([\d.-]+) dB", stderr)
            if mean_match:
                results["mean_level_db"] = float(mean_match.group(1))
                # Estimate noise level (rough approximation)
                if results["mean_level_db"] is not None:
                    results["noise_level_db"] = results["mean_level_db"] - 10.0

        # Analyze frequency spectrum to detect noise type
        # Use ahighpass filter to check low-frequency content (wind noise indicator)
        cmd_freq = [
            self.ffmpeg,
            "-hide_banner",
            "-i",
            str(input_path),
            "-af",
            "highpass=f=100,astats=metadata=1:reset=1",
            "-f",
            "null",
            "-",
        ]
        p_freq = self._run(cmd_freq, timeout=60 * 5)
        low_freq_level = None
        if p_freq.returncode == 0:
            stderr = p_freq.stderr or ""
            mean_match = re.search(r"Mean level: ([\d.-]+) dB", stderr)
            if mean_match:
                low_freq_level = float(mean_match.group(1))

        # Determine noise type and recommend model
        noise_level = results.get("noise_level_db")
        silence_ratio = results.get("silence_ratio", 0.0)
        mean_level = results.get("mean_level_db")
        peak_level = results.get("peak_level_db")

        # Check for low quality audio indicators
        # Low quality: very low mean level, high peak-to-mean ratio, low silence ratio
        if mean_level is not None and peak_level is not None:
            peak_to_mean_ratio = peak_level - mean_level if mean_level < peak_level else 0
            # Low quality audio often has high dynamic range (compression artifacts)
            if mean_level < -50 and peak_to_mean_ratio > 25 and silence_ratio < 0.2:
                results["noise_type"] = "low_quality"
                results["recommended_model"] = "lq"
            # Wind noise: low frequency content, continuous noise, low silence ratio
            elif low_freq_level is not None and low_freq_level > -45 and silence_ratio < 0.15:
                results["noise_type"] = "wind"
                results["recommended_model"] = "bd"
            # General noise: moderate levels, some silence
            elif noise_level is not None and noise_level > -40:
                results["noise_type"] = "general"
                results["recommended_model"] = "std"
            # Minimal noise: low noise level, high silence ratio
            elif noise_level is not None and noise_level <= -40 and silence_ratio > 0.3:
                results["noise_type"] = "minimal"
                results["recommended_model"] = None  # No denoising needed
            else:
                results["noise_type"] = "general"
                results["recommended_model"] = "std"

        return results

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

    def get_recommendations(
        self, analysis_before: Dict[str, Any], noise_analysis: Optional[Dict[str, Any]] = None
    ) -> list[Dict[str, Any]]:
        """
        Generate recommendations based on loudness analysis and optional noise analysis.
        """
        recs: list[Dict[str, Any]] = []
        try:
            input_lra = float(analysis_before.get("input_lra") or analysis_before.get("measured_LRA") or 0.0)
        except Exception:
            input_lra = 0.0
        try:
            input_tp = float(analysis_before.get("input_tp") or analysis_before.get("measured_TP") or 0.0)
        except Exception:
            input_tp = 0.0
        try:
            input_i = float(analysis_before.get("input_i") or analysis_before.get("measured_I") or 0.0)
        except Exception:
            input_i = 0.0

        # Determine target preset prefix based on job target
        target_prefix = "web" if self.job.target == "web" else "tv"
        ai_preset_speech = f"{target_prefix}_ai_speech"
        ai_preset_strong = f"{target_prefix}_ai_strong" if target_prefix == "tv" else "tv_ai_strong"

        # Get target values from defaults
        target_i = self.presets_json.get("defaults", {}).get(target_prefix, {}).get("I", -23 if target_prefix == "tv" else -16)
        target_lra = self.presets_json.get("defaults", {}).get(target_prefix, {}).get("LRA", 11)
        target_tp = self.presets_json.get("defaults", {}).get(target_prefix, {}).get("TP", -1.0)

        # Extract noise analysis data
        silence_ratio = None
        noise_level = None
        peak_level = None
        noise_type = None
        recommended_model = None
        
        if noise_analysis:
            silence_ratio = noise_analysis.get("silence_ratio")
            noise_level = noise_analysis.get("noise_level_db")
            peak_level = noise_analysis.get("peak_level_db")
            noise_type = noise_analysis.get("noise_type")
            recommended_model = noise_analysis.get("recommended_model")

        # Detect all issues
        # LUFS too high (too loud) - input_i is more positive (less negative) than target
        has_too_loud = input_i > target_i
        # LRA too high (high dynamics) - above target LRA
        has_high_lra = input_lra > target_lra
        # Very high dynamics (LRA > 14) - extreme case
        has_very_high_dynamics = input_lra > 14
        has_high_tp = input_tp > target_tp
        has_very_high_peaks = peak_level is not None and peak_level > -3.0
        has_high_peaks = has_high_tp or has_very_high_peaks
        has_continuous_noise = silence_ratio is not None and silence_ratio < 0.1
        has_high_noise = noise_level is not None and noise_level > -40
        has_very_high_noise = noise_level is not None and noise_level > -35
        has_ai_available = self.rnn_model_path is not None

        # Count issues to determine severity
        issue_count = sum([
            has_too_loud,
            has_high_lra,
            has_high_peaks,
            has_continuous_noise,
            has_high_noise,
        ])

        # Combined recommendations for multiple issues
        if issue_count >= 2:
            issues_list = []
            if has_too_loud:
                issues_list.append(str(_("LUFS too high ({input_i:.1f} LUFS, target {target_i:.1f})").format(input_i=input_i, target_i=target_i)))
            if has_high_lra:
                issues_list.append(str(_("high LRA ({input_lra:.1f} LU, target ≤{target_lra})").format(input_lra=input_lra, target_lra=target_lra)))
            if has_high_peaks:
                issues_list.append(str(_("high peak levels")))
            if has_continuous_noise:
                issues_list.append(str(_("continuous background noise")))
            if has_high_noise:
                issues_list.append(str(_("high background noise ({noise_level:.1f} dB)").format(noise_level=noise_level)))

            if len(issues_list) > 1:
                issues_text = ", ".join(issues_list[:-1]) + " " + str(_(" and ")) + " " + issues_list[-1]
            else:
                issues_text = issues_list[0]

            # Determine best preset based on severity and AI availability
            if has_ai_available:
                if has_very_high_noise or (has_high_peaks and has_high_noise) or issue_count >= 3:
                    # Multiple severe issues: recommend strong AI preset
                    recs.append({
                        "preset_id": ai_preset_strong if target_prefix == "tv" else "tv_ai_strong",
                        "reason": _("Multiple issues detected: {issues}. Recommended: {preset} combines aggressive processing, AI denoising, and speech optimization to address all problems. For a softer option, use {speech_preset}.").format(
                            issues=issues_text,
                            preset=ai_preset_strong if target_prefix == "tv" else "tv_ai_strong",
                            speech_preset=ai_preset_speech
                        ),
                    })
                elif has_high_peaks and has_continuous_noise:
                    # High peaks + continuous noise: recommend strong AI preset
                    recs.append({
                        "preset_id": ai_preset_strong if target_prefix == "tv" else "tv_ai_strong",
                        "reason": _("High peak levels and continuous background noise detected. Recommended: {preset} combines aggressive peak control, AI denoising for noise removal, and speech optimization. For a softer option, use {speech_preset} and verify limiter is sufficient for peak control.").format(
                            preset=ai_preset_strong if target_prefix == "tv" else "tv_ai_strong",
                            speech_preset=ai_preset_speech
                        ),
                    })
                elif has_high_peaks and has_high_noise:
                    # High peaks + high noise: recommend strong AI preset
                    recs.append({
                        "preset_id": ai_preset_strong if target_prefix == "tv" else "tv_ai_strong",
                        "reason": _("High peak levels ({peak_level:.1f} dB) and high background noise ({noise_level:.1f} dB) detected. Recommended: {preset} combines aggressive peak control with AI denoising for optimal results.").format(
                            peak_level=peak_level if peak_level is not None else input_tp,
                            noise_level=noise_level,
                            preset=ai_preset_strong if target_prefix == "tv" else "tv_ai_strong"
                        ),
                    })
                elif has_continuous_noise and has_high_noise:
                    # Continuous noise + high noise: recommend AI preset (speech or strong based on noise level)
                    if has_very_high_noise:
                        recs.append({
                            "preset_id": ai_preset_strong if target_prefix == "tv" else "tv_ai_strong",
                            "reason": _("Continuous and very high background noise ({noise_level:.1f} dB) detected. Recommended: {preset} for aggressive AI denoising and speech clarity.").format(
                                noise_level=noise_level,
                                preset=ai_preset_strong if target_prefix == "tv" else "tv_ai_strong"
                            ),
                        })
                    else:
                        recs.append({
                            "preset_id": ai_preset_speech,
                            "reason": _("Continuous background noise and high noise level ({noise_level:.1f} dB) detected. Recommended: {preset} with AI denoising for speech clarity.").format(
                                noise_level=noise_level,
                                preset=ai_preset_speech
                            ),
                        })
                else:
                    # Other combinations: use AI speech preset
                    recs.append({
                        "preset_id": ai_preset_speech,
                        "reason": _("Multiple issues detected: {issues}. Recommended: {preset} with AI denoising to address these problems.").format(
                            issues=issues_text,
                            preset=ai_preset_speech
                        ),
                    })
            else:
                # Multiple issues but AI not available: recommend strong preset
                recs.append({
                    "preset_id": "tv_strong",
                    "reason": _("Multiple issues detected: {issues}. Strong preset recommended. Consider installing RNN model for AI denoising to get better results.").format(
                        issues=issues_text
                    ),
                })
        else:
            # Individual recommendations for single issues or when AI not available
            # LUFS too high (too loud)
            if has_too_loud and issue_count <= 1:
                recs.append({
                    "preset_id": "tv_strong",
                    "reason": _("LUFS too high ({input_i:.1f} LUFS, target {target_i:.1f}). Strong preset recommended to reduce loudness.").format(
                        input_i=input_i, target_i=target_i
                    ),
                })

            # LRA too high (high dynamics)
            if has_high_lra and issue_count <= 1:
                if has_very_high_dynamics:
                    recs.append({
                        "preset_id": "tv_strong",
                        "reason": _("Very high dynamics (LRA {input_lra:.1f} LU, target ≤{target_lra}). Strong preset recommended.").format(
                            input_lra=input_lra, target_lra=target_lra
                        ),
                    })
                else:
                    recs.append({
                        "preset_id": "tv_strong",
                        "reason": _("High dynamics (LRA {input_lra:.1f} LU, target ≤{target_lra}). Strong preset recommended.").format(
                            input_lra=input_lra, target_lra=target_lra
                        ),
                    })

            # True Peak recommendation (if not already covered by combined recommendation)
            if has_high_tp and issue_count <= 1:
                recs.append({
                    "preset_id": "tv_strong",
                    "reason": "TruePeak above target. Strong preset + limiter may reduce clipping risk.",
                })

            # Noise-based recommendations with model-specific suggestions
            if noise_analysis:
                # Model-specific recommendations based on noise type
                if recommended_model:
                    available_models = self.get_available_models()
                    model_available = recommended_model in available_models

                    if model_available:
                        model_name_map = {
                            "std": _("standard (std.rnnn)"),
                            "bd": _("balloon/directional (bd.rnnn) - optimized for wind noise"),
                            "lq": _("low quality (lq.rnnn) - optimized for degraded audio"),
                        }
                        model_name = model_name_map.get(recommended_model, recommended_model)

                        if noise_type == "wind":
                            recs.append({
                                "preset_id": ai_preset_speech if has_ai_available else "tv_strong",
                                "reason": _("Wind noise detected. Recommended model: {model_name}. Configure ARNNDN Model Path in Tools Config to use this model.").format(model_name=model_name) if has_ai_available else _("Wind noise detected. Strong denoising recommended. Consider installing RNN model for AI denoising."),
                                "recommended_model": recommended_model,
                            })
                        elif noise_type == "low_quality":
                            recs.append({
                                "preset_id": ai_preset_speech if has_ai_available else "tv_strong",
                                "reason": _("Low quality audio detected (compression artifacts, degradation). Recommended model: {model_name}. Configure ARNNDN Model Path in Tools Config to use this model.").format(model_name=model_name) if has_ai_available else _("Low quality audio detected. Strong denoising recommended. Consider installing RNN model for AI denoising."),
                                "recommended_model": recommended_model,
                            })
                        elif noise_type == "general":
                            recs.append({
                                "preset_id": ai_preset_speech if has_ai_available else "tv_strong",
                                "reason": _("Background noise detected ({noise_level:.1f} dB). Recommended model: {model_name} for best results.").format(noise_level=noise_level, model_name=model_name) if has_ai_available else _("Background noise detected ({noise_level:.1f} dB). Strong denoising recommended. Consider installing RNN model for AI denoising.").format(noise_level=noise_level),
                                "recommended_model": recommended_model,
                            })
                    else:
                        # Model not available, but recommend it
                        if recommended_model == "bd":
                            recs.append({
                                "preset_id": ai_preset_speech if has_ai_available else "tv_strong",
                                "reason": _("Wind noise detected. Consider downloading bd.rnnn model for better wind noise reduction. Currently using std.rnnn.") if has_ai_available else _("Wind noise detected. Strong denoising recommended. Consider installing RNN model for AI denoising."),
                                "recommended_model": "bd",
                            })
                        elif recommended_model == "lq":
                            recs.append({
                                "preset_id": ai_preset_speech if has_ai_available else "tv_strong",
                                "reason": _("Low quality audio detected. Consider downloading lq.rnnn model for better results with degraded audio. Currently using std.rnnn.") if has_ai_available else _("Low quality audio detected. Strong denoising recommended. Consider installing RNN model for AI denoising."),
                                "recommended_model": "lq",
                            })

                # High background noise detected (single issue)
                if has_high_noise and issue_count <= 1:
                    if has_ai_available:
                        if has_very_high_noise:
                            recs.append({
                                "preset_id": ai_preset_strong if target_prefix == "tv" else "tv_ai_strong",
                                "reason": _("Very high background noise ({noise_level:.1f} dB). Consider aggressive AI denoising.").format(noise_level=noise_level),
                            })
                        else:
                            recs.append({
                                "preset_id": ai_preset_speech,
                                "reason": _("High background noise detected ({noise_level:.1f} dB). AI denoiser (arnndn) recommended for better speech clarity.").format(noise_level=noise_level),
                            })
                    else:
                        recs.append({
                            "preset_id": "tv_strong",
                            "reason": _("High background noise detected ({noise_level:.1f} dB). Strong denoising recommended. Consider installing RNN model for AI denoising.").format(noise_level=noise_level),
                        })

                # Low silence ratio suggests continuous noise (single issue)
                if has_continuous_noise and issue_count <= 1:
                    if has_ai_available:
                        recs.append({
                            "preset_id": ai_preset_speech,
                            "reason": _("Continuous background noise detected. AI denoiser recommended for speech clarity."),
                        })
                    else:
                        recs.append({
                            "preset_id": "tv_strong",
                            "reason": _("Continuous background noise detected. Denoising recommended."),
                        })

                # Very high peak levels (single issue)
                if has_very_high_peaks and issue_count <= 1:
                    recs.append({
                        "preset_id": "tv_strong",
                        "reason": _("Very high peak levels ({peak_level:.1f} dB). Strong limiter recommended.").format(peak_level=peak_level),
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

        # Determine which RNN model to use
        # Priority: 1) recommended_model from noise_analysis, 2) preset arnndn_model, 3) config path
        model_to_use = self.rnn_model_path
        if self.job.input_metadata and isinstance(self.job.input_metadata, dict):
            noise_analysis = self.job.input_metadata.get("noise_analysis")
            if noise_analysis and isinstance(noise_analysis, dict):
                recommended_model = noise_analysis.get("recommended_model")
                if recommended_model:
                    # Try to use recommended model if available
                    recommended_path = self.get_model_path(recommended_model)
                    if recommended_path:
                        model_to_use = recommended_path
                        logger.info("Using recommended model %s (%s) for job %s", recommended_model, recommended_path, self.job.id)
        
        # Check if preset specifies a specific model
        preset_model = _get(preset, "filters.arnndn_model", None)
        if preset_model:
            model_to_use = preset_model

        af = build_process_chain(
            self.presets_json,
            preset,
            target=self.job.target,
            measured=measured if linear else None,
            print_format="summary",
            rnn_model_path=model_to_use,
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
        
        # Optional noise analysis for better recommendations
        noise_analysis = None
        try:
            noise_analysis = self.analyze_noise(input_path)
        except Exception as e:
            logger.warning("Noise analysis failed (non-critical): %s", e)

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
            "noise_analysis": noise_analysis,
            "output_path": str(out_path),
            "output_relpath": output_relpath,
            "output_path_external": output_path_external,
            "ffmpeg_log": ffmpeg_log,
            "probe": {"duration_sec": probe_info.duration_sec, "has_video": probe_info.has_video, "has_audio": probe_info.has_audio},
            "recommendations": self.get_recommendations(before, noise_analysis),
        }

