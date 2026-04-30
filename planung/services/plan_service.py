"""Core orchestration service for planning API operations."""

from __future__ import annotations

from dataclasses import dataclass
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.db import transaction
from django.http import Http404
from django.utils.translation import gettext as _
from licenses.models import License
from planung.models import PlanChangeLog
from planung.models import TagesPlan

from .auto_copy_service import trigger_auto_copy_for_plan
from .notification_service import send_plan_status_notifications
from .validation_service import ValidatedPlanPayload


@dataclass(frozen=True)
class SavePlanResult:
    """Result object for save operations."""

    status: str
    created: bool
    warnings: list[dict]


def _user_or_none(user):
    """Normalize anonymous users to None for audit log foreign key."""
    if user is None or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
        return None
    return user


def _invalidate_planning_cache() -> None:
    """Invalidate known planning cache entries."""
    cache.delete("planung_week_stats")
    version = cache.get("planung_cache_version", 1)
    cache.set("planung_cache_version", int(version) + 1, timeout=None)


def save_day_plan(*, validated: ValidatedPlanPayload, user) -> SavePlanResult:
    """Persist plan and trigger side effects."""
    plan_data = {
        "items": validated.items,
        "draft": validated.draft,
        "planned": validated.planned,
    }

    with transaction.atomic():
        plan = TagesPlan.objects.filter(datum=validated.plan_date).first()

        if plan:
            old_items = plan.json_plan.get("items", [])
            old_draft = plan.json_plan.get("draft", False)
            old_comment = plan.kommentar or ""
            if (
                old_draft
                and old_items == plan_data["items"]
                and old_draft == plan_data["draft"]
                and validated.comment != old_comment
            ):
                old_payload = {
                    "json_plan": plan.json_plan,
                    "comment": old_comment,
                }
                plan.kommentar = validated.comment
                plan.save(update_fields=["kommentar"])
                PlanChangeLog.objects.create(
                    plan_date=validated.plan_date,
                    action=PlanChangeLog.ACTION_UPDATE,
                    old_payload=old_payload,
                    new_payload={"json_plan": plan.json_plan, "comment": plan.kommentar},
                    changed_by=_user_or_none(user),
                )
                _invalidate_planning_cache()
                return SavePlanResult(status="comment_updated", created=False, warnings=validated.warnings)

        old_payload = None
        if plan:
            old_payload = {"json_plan": plan.json_plan, "comment": plan.kommentar or ""}

        plan, created = TagesPlan.objects.update_or_create(
            datum=validated.plan_date,
            defaults={"json_plan": plan_data, "kommentar": validated.comment},
        )

        PlanChangeLog.objects.create(
            plan_date=validated.plan_date,
            action=PlanChangeLog.ACTION_CREATE if created else PlanChangeLog.ACTION_UPDATE,
            old_payload=old_payload or {},
            new_payload={"json_plan": plan.json_plan, "comment": plan.kommentar or ""},
            changed_by=_user_or_none(user),
        )

    send_plan_status_notifications(plan_date=validated.plan_date, plan_data=plan_data)
    trigger_auto_copy_for_plan(
        plan_date=validated.plan_date,
        plan_data=plan_data,
        user_id=getattr(user, "id", None),
    )
    _invalidate_planning_cache()
    return SavePlanResult(status="ok", created=created, warnings=validated.warnings)


def delete_day_plan(*, iso_date, user) -> None:
    """Delete plan and write audit entry."""
    from django.utils.dateparse import parse_date

    date_obj = parse_date(iso_date)
    if not date_obj:
        raise ValueError(_("Bad date format"))

    try:
        plan = TagesPlan.objects.get(datum=date_obj)
    except TagesPlan.DoesNotExist as exc:
        raise Http404(_("No plan for this day")) from exc

    old_payload = {"json_plan": plan.json_plan, "comment": plan.kommentar or ""}
    plan.delete()
    PlanChangeLog.objects.create(
        plan_date=date_obj,
        action=PlanChangeLog.ACTION_DELETE,
        old_payload=old_payload,
        new_payload={},
        changed_by=_user_or_none(user),
    )
    _invalidate_planning_cache()


def enrich_plan_items(items: list[dict]) -> list[dict]:
    """Enrich stored items with actual license/video metadata."""
    license_numbers = [item.get("number") for item in items if item.get("number")]
    licenses_dict = {}
    video_files_dict = {}

    if license_numbers:
        licenses = License.objects.filter(number__in=license_numbers).select_related("profile", "video_file")
        licenses_dict = {lic.number: lic for lic in licenses}
        try:
            from media_files.models import VideoFile

            video_files = VideoFile.objects.filter(number__in=license_numbers).select_related("license")
            video_files_dict = {vf.number: vf for vf in video_files if vf.duration}
        except ImportError:
            pass

    enriched_items = []
    for item in items:
        license_number = item.get("number")
        enriched_item = item.copy()
        if not license_number or license_number not in licenses_dict:
            enriched_items.append(enriched_item)
            continue

        license_obj = licenses_dict[license_number]
        enriched_item["title"] = license_obj.title or item.get("title", "")
        enriched_item["subtitle"] = license_obj.subtitle or item.get("subtitle", "")
        enriched_item["is_live"] = license_obj.is_live

        duration_seconds = int(license_obj.duration.total_seconds())
        if getattr(license_obj, "video_file", None) and license_obj.video_file.duration:
            duration_seconds = int(license_obj.video_file.duration.total_seconds())
        elif license_number in video_files_dict:
            duration_seconds = int(video_files_dict[license_number].duration.total_seconds())

        enriched_item["duration"] = duration_seconds
        enriched_item["license_id"] = license_obj.id

        if license_obj.profile:
            author_name = f"{license_obj.profile.first_name or ''} {license_obj.profile.last_name or ''}".strip()
            enriched_item["author"] = author_name
            enriched_item["sender_responsible"] = author_name
        else:
            enriched_item["author"] = item.get("author", "")
            enriched_item["sender_responsible"] = item.get("sender_responsible", item.get("author", ""))

        enriched_items.append(enriched_item)

    return enriched_items
