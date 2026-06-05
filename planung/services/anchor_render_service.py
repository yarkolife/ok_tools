"""Create programme preview videos through the external anchor renderer."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from django.apps import apps
from django.conf import settings
from django.utils import timezone
from licenses.models import Category
from licenses.models import License
from pathlib import Path
from planung.models import PlanungConfig
from random import choice
from random import triangular
from registration import organization_config
from registration.models import Profile
from requests import RequestException
from typing import Any
import logging
import posixpath
import requests


logger = logging.getLogger(__name__)


WEEKDAY_NAMES = {
    0: "Montag",
    1: "Dienstag",
    2: "Mittwoch",
    3: "Donnerstag",
    4: "Freitag",
    5: "Samstag",
    6: "Sonntag",
}


@dataclass(frozen=True)
class AnchorRenderResult:
    """Result of one anchor render request."""

    configured: bool
    sent: bool
    license_id: int | None
    license_number: int | None
    output_name: str
    job_id: str
    status: str
    file: str
    error: str
    payload: dict[str, Any] | None = None
    license_created: bool = False
    video_exists: bool = False
    requires_confirmation: bool = False


@dataclass(frozen=True)
class AnchorJobStatus:
    """Status returned by the external anchor renderer for one job."""

    configured: bool
    job_id: str
    status: str
    file: str
    error: str


def _duration_sec(value: Any = None) -> int:
    """Return duration in seconds with the anchor default as fallback."""
    if isinstance(value, (int, float)):
        return max(1, int(value))
    if hasattr(value, "total_seconds"):
        return max(1, int(value.total_seconds()))
    return 20


def _anchor_clip_duration(config: PlanungConfig) -> int:
    """Return the configured preview clip duration for anchor contributions."""
    return _duration_sec(getattr(config, "anchor_contribution_duration_seconds", 20))


def _start_from_seconds(video_file: Any, clip_duration: int) -> int | None:
    """Return a random source start near the middle of the video."""
    source_duration = getattr(video_file, "duration", None)
    if not source_duration or not hasattr(source_duration, "total_seconds"):
        return None

    source_seconds = int(source_duration.total_seconds())
    max_start = source_seconds - clip_duration - 7
    if max_start < 0:
        return None
    if max_start == 0:
        return 0

    center_start = max(0, min(max_start, round((source_seconds / 2) - (clip_duration / 2))))
    if source_seconds <= 180:
        radius = max(3, min(12, max_start * 0.12))
    elif source_seconds <= 600:
        radius = max(8, min(60, max_start * 0.22))
    else:
        radius = max(60, max_start * 0.45)

    low = max(0, center_start - radius)
    high = min(max_start, center_start + radius)
    return int(round(triangular(low, high, center_start)))


def _author_name(license_obj: License | None, plan_item: dict[str, Any]) -> str:
    """Return the best available author/sender label."""
    for key in ("sender_responsible", "author"):
        value = str(plan_item.get(key) or "").strip()
        if value:
            return value
    profile = getattr(license_obj, "profile", None) if license_obj else None
    if not profile:
        return ""
    return f"{profile.first_name or ''} {profile.last_name or ''}".strip()


def _video_path_from_playout(video_file: Any, config: PlanungConfig) -> str:
    """Return NAS-relative playout path for an available playout VideoFile."""
    if not video_file or not getattr(video_file, "is_available", False):
        return ""
    storage = getattr(video_file, "storage_location", None)
    if not storage or getattr(storage, "storage_type", "") != "PLAYOUT":
        return ""
    file_path = str(
        getattr(video_file, "file_path", "")
        or getattr(video_file, "filename", "")
        or ""
    ).strip()
    if not file_path:
        return ""
    prefix = (config.anchor_playout_path_prefix or "playout").strip().strip("/")
    return posixpath.join(prefix, file_path.lstrip("/"))


def _placeholder_video(
    license_obj: License | None,
    plan_item: dict[str, Any],
    config: PlanungConfig,
) -> str:
    """Resolve a placeholder video from configured rules."""
    title = str(
        plan_item.get("title")
        or getattr(license_obj, "title", "")
        or ""
    ).strip()
    is_live = bool(plan_item.get("is_live") or getattr(license_obj, "is_live", False))
    rules = config.anchor_placeholder_rules if isinstance(config.anchor_placeholder_rules, list) else []

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        match = str(rule.get("match") or rule.get("type") or "").strip().lower()
        video = str(rule.get("video") or rule.get("path") or "").strip()
        if not video:
            continue
        if match == "live" and is_live:
            return video
        if match in {"prefix", "title_prefix"}:
            prefix = str(rule.get("prefix") or rule.get("title_prefix") or "").strip()
            if prefix and title.startswith(prefix):
                return video

    return str(config.anchor_default_placeholder_video or "").strip()


def _load_licenses_and_videos(
    plan_items: list[dict[str, Any]],
) -> tuple[dict[int, License], dict[int, Any]]:
    """Load licenses and primary playout videos for plan rows."""
    numbers = [item.get("number") for item in plan_items if item.get("number")]
    licenses_by_number: dict[int, License] = {}
    videos_by_number: dict[int, Any] = {}
    if not numbers:
        return licenses_by_number, videos_by_number

    licenses = License.objects.filter(number__in=numbers).select_related("profile")
    licenses_by_number = {license_obj.number: license_obj for license_obj in licenses}

    try:
        VideoFile = apps.get_model("media_files", "VideoFile")
    except (ImportError, LookupError):
        return licenses_by_number, videos_by_number

    video_files = VideoFile.objects.filter(
        number__in=numbers,
        is_preview=False,
        storage_location__storage_type="PLAYOUT",
    ).select_related("storage_location")
    for video_file in video_files:
        existing = videos_by_number.get(video_file.number)
        if existing and getattr(existing, "is_manual_primary", False):
            continue
        if not existing or getattr(video_file, "is_manual_primary", False):
            videos_by_number[video_file.number] = video_file

    return licenses_by_number, videos_by_number


def build_anchor_payload(
    *,
    plan_date: date,
    plan_items: list[dict[str, Any]],
    output_name: str,
    config: PlanungConfig | None = None,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Build the anchor renderer request payload for one planned day."""
    config = config or PlanungConfig.get_config()
    licenses_by_number, videos_by_number = _load_licenses_and_videos(plan_items)
    rejected: list[dict[str, str]] = []
    contributions: list[dict[str, Any]] = []

    for plan_item in plan_items[:8]:
        number = plan_item.get("number")
        license_obj = licenses_by_number.get(number) if number else None
        video_file = videos_by_number.get(number)
        video = _video_path_from_playout(video_file, config)
        uses_playout_video = bool(video)
        if not video:
            video = _placeholder_video(license_obj, plan_item, config)
        if not video:
            rejected.append(
                {
                    "number": str(number or ""),
                    "title": str(
                        plan_item.get("title")
                        or getattr(license_obj, "title", "")
                        or ""
                    ),
                    "reason": "no_playout_video_or_placeholder",
                }
            )
            continue

        start = str(plan_item.get("start") or "").strip()
        title = str(plan_item.get("title") or getattr(license_obj, "title", "") or "").strip()
        subtitle = str(plan_item.get("subtitle") or getattr(license_obj, "subtitle", "") or "").strip()
        duration_seconds = _anchor_clip_duration(config)
        contribution = {
            "uhrzeit": start[:5] if start else "",
            "sendung": title,
            "untertitel": subtitle,
            "titel": title,
            "autor": _author_name(license_obj, plan_item),
            "hinweis": str(
                plan_item.get("description")
                or getattr(license_obj, "description", "")
                or ""
            ).strip(),
            "video": video,
            "durationInSeconds": duration_seconds,
        }
        start_from = _start_from_seconds(video_file, duration_seconds) if uses_playout_video else None
        if start_from is not None:
            contribution["startFromSeconds"] = start_from
        contributions.append(contribution)

    payload: dict[str, Any] = {
        "wochentag": WEEKDAY_NAMES[plan_date.weekday()],
        "stimme": choice(["m", "w"]),
        "output_name": output_name,
        "beitraege": contributions,
    }
    return payload, rejected


def _output_name(config: PlanungConfig, license_number: int, plan_date: date) -> str:
    """Format the output filename using the configured pattern."""
    pattern = config.anchor_output_filename_pattern or "{number}_Programmvorschau_{date:%y%m%d}.mp4"
    return pattern.format(number=license_number, date=plan_date)


def _license_title(plan_date: date) -> str:
    """Return the stable title used to identify programme preview licenses."""
    return f"Programmvorschau vom {plan_date.strftime('%d.%m.%Y')}"


def _anchor_category() -> Category:
    """Return the category used for programme preview licenses."""
    return Category.objects.get_or_create(name="Sonstiges")[0]


def _anchor_profile(fallback_profile: Any) -> Any:
    """Return the organization profile used for programme preview licenses."""
    names = [
        organization_config.get_organization_name(),
        getattr(settings, "OK_NAME", ""),
        "Offener Kanal Merseburg-Querfurt e.V.",
    ]
    candidates = {str(name).strip().casefold() for name in names if str(name).strip()}
    if not candidates:
        return fallback_profile

    for profile in Profile.objects.only("first_name", "last_name"):
        full_name = f"{profile.first_name or ''} {profile.last_name or ''}".strip()
        first_name = str(profile.first_name or "").strip()
        if full_name.casefold() in candidates or first_name.casefold() in candidates:
            return profile

    return fallback_profile


def _sync_preview_license_fields(license_obj: License, profile: Any, plan_date: date) -> License:
    """Keep anchor preview license metadata aligned with the configured defaults."""
    updates: list[str] = []
    values = {
        "profile": _anchor_profile(profile),
        "category": _anchor_category(),
        "title": _license_title(plan_date),
        "description": "Information für unsere Zuschauer.",
        "duration": timedelta(minutes=1),
        "repetitions_allowed": True,
        "media_authority_exchange_allowed": False,
        "media_authority_exchange_allowed_other_states": False,
        "youth_protection_necessary": False,
        "store_in_ok_media_library": False,
        "confirmed": True,
        "infoblock": True,
    }
    for field, value in values.items():
        if getattr(license_obj, field) != value:
            setattr(license_obj, field, value)
            updates.append(field)
    if updates:
        license_obj.save(update_fields=updates)
    return license_obj


def _get_or_create_preview_license(profile: Any, plan_date: date) -> tuple[License, bool]:
    """Return the existing preview license for the date or create it."""
    existing = License.objects.filter(title=_license_title(plan_date)).order_by("-id").first()
    if existing:
        return _sync_preview_license_fields(existing, profile, plan_date), False

    aware_date = timezone.make_aware(datetime.combine(plan_date, time.min))
    license_obj = License.objects.create(
        profile=_anchor_profile(profile),
        category=_anchor_category(),
        title=_license_title(plan_date),
        subtitle="",
        description="Information für unsere Zuschauer.",
        further_persons="",
        duration=timedelta(minutes=1),
        suggested_date=aware_date,
        repetitions_allowed=True,
        media_authority_exchange_allowed=False,
        media_authority_exchange_allowed_other_states=False,
        youth_protection_necessary=False,
        store_in_ok_media_library=False,
        confirmed=True,
        infoblock=True,
    )
    return license_obj, True


def _anchor_output_video_exists(config: PlanungConfig, license_number: int, output_name: str) -> bool:
    """Return whether the rendered programme preview file is already known or present."""
    try:
        VideoFile = apps.get_model("media_files", "VideoFile")
        if VideoFile.objects.filter(number=license_number, filename=output_name, is_available=True).exists():
            return True
    except (ImportError, LookupError):
        pass

    try:
        StorageLocation = apps.get_model("media_files", "StorageLocation")
    except (ImportError, LookupError):
        return False

    rel_dir = str(config.anchor_output_playout_directory or "003_Programmvorschau").strip().strip("/")
    for storage in StorageLocation.objects.filter(storage_type="PLAYOUT", is_active=True):
        path = Path(storage.path) / rel_dir / output_name
        try:
            if path.exists():
                return True
        except OSError as exc:
            logger.warning("Could not check anchor output file %s: %s", path, exc)
    return False


def render_anchor_preview(
    *,
    plan_date: date,
    plan_items: list[dict[str, Any]],
    profile: Any,
    force: bool = False,
) -> AnchorRenderResult:
    """Create a license and send a planned day to the anchor renderer."""
    config = PlanungConfig.get_config()
    if not config.is_anchor_render_configured():
        return AnchorRenderResult(
            False,
            False,
            None,
            None,
            "",
            "",
            "",
            "",
            "not_configured",
        )

    license_obj, license_created = _get_or_create_preview_license(profile, plan_date)
    output_name = _output_name(config, license_obj.number, plan_date)
    video_exists = _anchor_output_video_exists(config, license_obj.number, output_name)
    if video_exists and not force:
        return AnchorRenderResult(
            True,
            False,
            license_obj.id,
            license_obj.number,
            output_name,
            "",
            "",
            output_name,
            "output_video_exists",
            None,
            license_created,
            video_exists,
            True,
        )

    payload, rejected = build_anchor_payload(
        plan_date=plan_date,
        plan_items=plan_items,
        output_name=output_name,
        config=config,
    )
    if rejected:
        return AnchorRenderResult(
            True,
            False,
            license_obj.id,
            license_obj.number,
            output_name,
            "",
            "",
            "",
            "missing_video_or_placeholder",
            payload,
            license_created,
            video_exists,
        )
    if not payload["beitraege"]:
        return AnchorRenderResult(
            True,
            False,
            license_obj.id,
            license_obj.number,
            output_name,
            "",
            "",
            "",
            "no_items",
            payload,
            license_created,
            video_exists,
        )

    try:
        response = requests.post(
            config.anchor_render_url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": config.anchor_render_api_key,
            },
            timeout=config.anchor_render_timeout,
        )
        response.raise_for_status()
        data = response.json()
    except (RequestException, ValueError) as exc:
        logger.exception("Failed to render anchor preview")
        return AnchorRenderResult(
            True,
            True,
            license_obj.id,
            license_obj.number,
            output_name,
            "",
            "",
            "",
            str(exc),
            payload,
            license_created,
            video_exists,
        )

    status = str(data.get("status") or "")
    error = str(data.get("error") or "")
    if status == "error" and not error:
        error = "render_error"
    return AnchorRenderResult(
        True,
        True,
        license_obj.id,
        license_obj.number,
        output_name,
        str(data.get("job_id") or ""),
        status,
        str(data.get("file") or ""),
        error,
        payload,
        license_created,
        video_exists,
    )


def get_anchor_job_status(job_id: str) -> AnchorJobStatus:
    """Return the current status of an anchor renderer job."""
    config = PlanungConfig.get_config()
    if not config.is_anchor_render_configured():
        return AnchorJobStatus(False, job_id, "", "", "not_configured")

    safe_job_id = str(job_id or "").strip()
    if not safe_job_id:
        return AnchorJobStatus(True, "", "", "", "missing_job_id")

    status_url = f"{config.anchor_render_url.rstrip('/')}/{safe_job_id}"
    try:
        response = requests.get(
            status_url,
            headers={
                "X-API-Key": config.anchor_render_api_key,
            },
            timeout=config.anchor_render_timeout,
        )
        response.raise_for_status()
        data = response.json()
    except (RequestException, ValueError) as exc:
        logger.exception("Failed to fetch anchor job status")
        return AnchorJobStatus(True, safe_job_id, "", "", str(exc))

    status = str(data.get("status") or "")
    error = str(data.get("error") or "")
    if status == "error" and not error:
        error = "render_error"
    return AnchorJobStatus(
        True,
        safe_job_id,
        status,
        str(data.get("file") or ""),
        error,
    )
