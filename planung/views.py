from .models import PlanTemplate
from .models import TagesPlan
from datetime import timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST
from licenses.models import License
from planung.services.plan_service import delete_day_plan
from planung.services.plan_service import enrich_plan_items
from planung.services.plan_service import save_day_plan as save_day_plan_service
from planung.services.validation_service import PlanningValidationError
from planung.services.validation_service import validate_day_plan_payload
import json
import logging


logger = logging.getLogger(__name__)


@staff_member_required
def get_license_by_number(request, number):
    """Return license details by license number."""
    try:
        # Optimize: fetch license with related video_file in one query
        license = License.objects.select_related('profile', 'video_file').get(number=number)
    except License.DoesNotExist:
        raise Http404(_("License not found or not confirmed."))
    
    # Get author name from profile
    author_name = ""
    sender_responsible = ""
    if license.profile:
        author_name = f"{license.profile.first_name or ''} {license.profile.last_name or ''}".strip()
        sender_responsible = author_name  # Sendeverantwortung is the same as author

    # Get real duration from VideoFile if available, otherwise use License duration
    duration_seconds = int(license.duration.total_seconds())
    if hasattr(license, 'video_file') and license.video_file and license.video_file.duration:
        # Use real video file duration if available via relationship
        duration_seconds = int(license.video_file.duration.total_seconds())
    else:
        # Try to find VideoFile by number (fallback if relationship is not set)
        try:
            from media_files.models import VideoFile
            video_file = VideoFile.objects.filter(number=number).first()
            if video_file and video_file.duration:
                duration_seconds = int(video_file.duration.total_seconds())
        except ImportError:
            pass  # media_files app not available

    return JsonResponse(
        {
            "number": license.number,
            "title": license.title or "",
            "subtitle": license.subtitle or "",
            "duration_seconds": duration_seconds,
            "author": author_name,
            "sender_responsible": sender_responsible,
            "license_id": license.id,
        }
    )


@require_POST
@staff_member_required
def save_day_plan(request):
    """Save a day plan with the provided data."""
    try:
        data = json.loads(request.body)
        validated = validate_day_plan_payload(data)
        result = save_day_plan_service(validated=validated, user=request.user)
        return JsonResponse(
            {
                "status": result.status,
                "created": result.created,
                "warnings": result.warnings,
            }
        )
    except PlanningValidationError as exc:
        return JsonResponse(
            {
                "error": _("Validation failed"),
                "errors": exc.errors,
                "warnings": exc.warnings,
            },
            status=400,
        )
    except Exception as e:
        logger.exception("Failed to save day plan")
        return JsonResponse({"error": str(e)}, status=400)


@require_http_methods(["GET", "DELETE"])
@staff_member_required
def day_plan_detail(request, iso_date):
    """Retrieve or delete a day plan by ISO date.

    Handles GET and DELETE requests for a specific day plan.
    """
    # Parse ISO date string to date object - timezone-naive
    date_obj = parse_date(iso_date)
    if not date_obj:
        if request.method == "GET":
            raise Http404(_("Bad date format"))
        return JsonResponse({"error": _("Bad date format")}, status=400)

    if request.method == "GET":
        try:
            plan = TagesPlan.objects.get(datum=date_obj)
        except TagesPlan.DoesNotExist:
            return JsonResponse(
                {
                    "date": str(date_obj),
                    "items": [],
                    "draft": False,
                    "planned": False,
                    "comment": "",
                }
            )

        enriched_items = enrich_plan_items(plan.json_plan.get("items", []))
        
        return JsonResponse(
            {
                "date": str(plan.datum),  # ✅ Return the actual date from the database
                "items": enriched_items,
                "draft": plan.json_plan.get("draft", False),
                "planned": plan.json_plan.get("planned", False),
                "comment": plan.kommentar or "",
            }
        )
    elif request.method == "DELETE":
        try:
            delete_day_plan(iso_date=iso_date, user=getattr(request, "user", None))
            return JsonResponse({"status": "deleted"}, status=204)
        except Http404:
            return JsonResponse({"error": _("No plan for this day")}, status=404)
        except ValueError:
            return JsonResponse({"error": _("Bad date format")}, status=400)
    else:
        return JsonResponse({"error": _("Method not allowed")}, status=405)


@require_GET
@staff_member_required
def week_stats(request):
    """Return aggregated statistics for 4 consecutive weeks."""
    from datetime import date as dt_date
    from registration import organization_config

    start_param = request.GET.get("start")
    if start_param:
        start_date = parse_date(start_param)
    else:
        today = dt_date.today()
        start_date = today - timedelta(days=today.weekday())
    if not start_date:
        return JsonResponse({"error": _("Invalid start date")}, status=400)

    weeks = int(request.GET.get("weeks", 4))
    if weeks < 1:
        weeks = 1
    if weeks > 12:
        weeks = 12

    broadcast_start = organization_config.get_broadcast_start()
    broadcast_end = organization_config.get_broadcast_end()
    start_h, start_m = [int(x) for x in broadcast_start.split(":")]
    end_h, end_m = [int(x) for x in broadcast_end.split(":")]
    max_block_seconds = (end_h * 3600 + end_m * 60) - (start_h * 3600 + start_m * 60)

    end_date = start_date + timedelta(days=(weeks * 7) - 1)
    plans = TagesPlan.objects.filter(datum__range=(start_date, end_date))
    by_date = {plan.datum: plan for plan in plans}

    rows = []
    for week_idx in range(weeks):
        week_start = start_date + timedelta(days=week_idx * 7)
        week_end = week_start + timedelta(days=6)
        planned_days = 0
        total_seconds = 0
        unique_numbers = set()

        for day_offset in range(7):
            day = week_start + timedelta(days=day_offset)
            plan = by_date.get(day)
            if not plan:
                continue
            items = plan.json_plan.get("items", [])
            if items:
                planned_days += 1
            for item in items:
                duration = item.get("duration") or 0
                try:
                    total_seconds += int(duration)
                except Exception:
                    continue
                number = item.get("number")
                if number:
                    unique_numbers.add(str(number))

        max_seconds = max_block_seconds * 7
        fill_rate = round((total_seconds / max_seconds) * 100) if max_seconds > 0 else 0
        rows.append(
            {
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "planned_days": planned_days,
                "total_seconds": total_seconds,
                "max_seconds": max_seconds,
                "fill_rate": fill_rate,
                "licenses_count": len(unique_numbers),
            }
        )

    return JsonResponse({"weeks": rows})


@require_GET
@staff_member_required
def list_templates(request):
    """Return active plan templates for UI selection."""
    templates = PlanTemplate.objects.filter(is_active=True).order_by("name")
    return JsonResponse(
        {
            "templates": [
                {
                    "id": tpl.id,
                    "name": tpl.name,
                    "description": tpl.description,
                }
                for tpl in templates
            ]
        }
    )


@require_POST
@staff_member_required
def apply_template(request):
    """Apply a stored plan template to one target date."""
    payload = json.loads(request.body or "{}")
    target_date = parse_date(payload.get("date") or "")
    template_id = payload.get("template_id")
    overwrite = bool(payload.get("overwrite", False))

    if not target_date:
        return JsonResponse({"error": _("Invalid date")}, status=400)
    if not template_id:
        return JsonResponse({"error": _("Template id is required")}, status=400)

    try:
        template = PlanTemplate.objects.get(pk=int(template_id), is_active=True)
    except (PlanTemplate.DoesNotExist, ValueError):
        return JsonResponse({"error": _("Template not found")}, status=404)

    exists = TagesPlan.objects.filter(datum=target_date).exists()
    if exists and not overwrite:
        return JsonResponse({"error": _("Plan already exists"), "code": "already_exists"}, status=409)

    plan_data = template.json_plan or {}
    data = {
        "date": target_date.isoformat(),
        "items": plan_data.get("items", []),
        "draft": bool(plan_data.get("draft", True)),
        "planned": bool(plan_data.get("planned", False)),
        "comment": payload.get("comment", ""),
    }

    try:
        validated = validate_day_plan_payload(data)
        result = save_day_plan_service(validated=validated, user=request.user)
    except PlanningValidationError as exc:
        return JsonResponse(
            {"error": _("Validation failed"), "errors": exc.errors, "warnings": exc.warnings},
            status=400,
        )

    return JsonResponse({"status": result.status, "created": result.created, "warnings": result.warnings})


@require_POST
@staff_member_required
def copy_plan(request):
    """Copy plan from source date to target date."""
    payload = json.loads(request.body or "{}")
    source_date = parse_date(payload.get("source_date") or "")
    target_date = parse_date(payload.get("target_date") or "")
    overwrite = bool(payload.get("overwrite", False))

    if not source_date or not target_date:
        return JsonResponse({"error": _("Both source and target dates are required")}, status=400)
    if source_date == target_date:
        return JsonResponse({"error": _("Source and target dates must differ")}, status=400)

    try:
        source = TagesPlan.objects.get(datum=source_date)
    except TagesPlan.DoesNotExist:
        return JsonResponse({"error": _("Source plan not found")}, status=404)

    exists = TagesPlan.objects.filter(datum=target_date).exists()
    if exists and not overwrite:
        return JsonResponse({"error": _("Plan already exists"), "code": "already_exists"}, status=409)

    data = {
        "date": target_date.isoformat(),
        "items": source.json_plan.get("items", []),
        "draft": source.json_plan.get("draft", True),
        "planned": source.json_plan.get("planned", False),
        "comment": source.kommentar or "",
    }

    try:
        validated = validate_day_plan_payload(data)
        result = save_day_plan_service(validated=validated, user=request.user)
    except PlanningValidationError as exc:
        return JsonResponse(
            {"error": _("Validation failed"), "errors": exc.errors, "warnings": exc.warnings},
            status=400,
        )

    return JsonResponse({"status": result.status, "created": result.created, "warnings": result.warnings})


@require_GET
@staff_member_required
def export_day_plan(request, iso_date):
    """Export plan payload in JSON format for one date."""
    date_obj = parse_date(iso_date)
    if not date_obj:
        return JsonResponse({"error": _("Bad date format")}, status=400)

    try:
        plan = TagesPlan.objects.get(datum=date_obj)
    except TagesPlan.DoesNotExist:
        return JsonResponse({"error": _("No plan for this day")}, status=404)

    return JsonResponse(
        {
            "date": str(plan.datum),
            "comment": plan.kommentar or "",
            "plan": plan.json_plan,
        }
    )


def calendar_weeks_view(request):
    """Render the calendar weeks view.

    Implementation of the calendar_weeks_view.
    """
    return HttpResponseRedirect(reverse("admin:calendar_weeks_view"))
