from .models import TagesPlan
from datetime import timedelta
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from licenses.models import License
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
@csrf_exempt
def save_day_plan(request):
    """Save a day plan with the provided data."""
    try:
        data = json.loads(request.body)
        # This explicitly parses ISO date as server timezone, timezone-naive
        date = parse_date(data.get("date"))
        if not date:
            return JsonResponse({"error": _("Invalid date")}, status=400)



        plan_data = {
            "items": data.get("items", []),
            "draft": data.get("draft", False),
            "planned": data.get("planned", False),
        }

        kommentar = data.get("comment", "")

        plan = TagesPlan.objects.filter(datum=date).first()
        if plan:
            old_items = plan.json_plan.get("items", [])
            old_draft = plan.json_plan.get("draft", False)
            old_comment = plan.kommentar or ""
            # If this is a draft plan and only the comment has changed
            if (
                old_draft
                and old_items == plan_data["items"]
                and old_draft == plan_data["draft"]
                and kommentar != old_comment
            ):
                plan.kommentar = kommentar
                plan.save(update_fields=["kommentar"])
                return JsonResponse({"status": "comment_updated", "created": False})
        plan, created = TagesPlan.objects.update_or_create(
            datum=date, defaults={"json_plan": plan_data, "kommentar": kommentar}
        )

        # Auto-copy videos to playout if plan is not draft and feature is enabled
        # Check all required settings before proceeding
        auto_copy_enabled = getattr(settings, 'VIDEO_AUTO_COPY_ON_SCHEDULE', False)
        copy_to_archive = getattr(settings, 'VIDEO_AUTO_COPY_TO_ARCHIVE', False)
        copy_to_playout = getattr(settings, 'VIDEO_AUTO_COPY_TO_PLAYOUT', False)
        
        if (not plan_data.get('draft') 
            and auto_copy_enabled 
            and (copy_to_archive or copy_to_playout)):
            try:
                from media_files.tasks import copy_videos_for_plan
                numbers = [item.get('number') for item in plan_data.get('items', []) if item.get('number')]
                if numbers:
                    logger.info(
                        f"Triggering auto-copy for {len(numbers)} videos for plan {date} "
                        f"(archive={copy_to_archive}, playout={copy_to_playout})"
                    )
                    # Run asynchronously via Celery if available, otherwise sync
                    try:
                        copy_videos_for_plan.delay(numbers, date, user_id=request.user.id)
                    except AttributeError:
                        # Celery not available, run synchronously
                        copy_videos_for_plan(numbers, date, user_id=request.user.id)
            except ImportError:
                logger.warning("media_files module not available, skipping auto-copy")
            except Exception as e:
                logger.error(f"Error in auto-copy videos: {str(e)}", exc_info=True)

        return JsonResponse({"status": "ok", "created": created})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
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

        # Enrich items with current data from License (dynamic data)
        items = plan.json_plan.get("items", [])

        # Optimize: get all license numbers and fetch licenses in one query
        license_numbers = [item.get("number") for item in items if item.get("number")]
        licenses_dict = {}
        video_files_dict = {}
        
        if license_numbers:
            # Fetch all licenses with their profiles and video_files in one query
            licenses = License.objects.filter(number__in=license_numbers).select_related('profile', 'video_file')
            licenses_dict = {lic.number: lic for lic in licenses}
            
            # Fetch all VideoFiles for these numbers in one query (for cases where license.video_file is None)
            try:
                from media_files.models import VideoFile
                video_files = VideoFile.objects.filter(number__in=license_numbers).select_related('license')
                video_files_dict = {vf.number: vf for vf in video_files if vf.duration}
            except ImportError:
                pass  # media_files app not available
        
        enriched_items = []
        for item in items:
            license_number = item.get("number")
            enriched_item = item.copy()  # Start with saved data as fallback
            
            if license_number and license_number in licenses_dict:
                license = licenses_dict[license_number]
                # Update with current data from License
                enriched_item["title"] = license.title or item.get("title", "")
                enriched_item["subtitle"] = license.subtitle or item.get("subtitle", "")
                
                # Get real duration from VideoFile if available, otherwise use License duration
                duration_seconds = int(license.duration.total_seconds())
                if hasattr(license, 'video_file') and license.video_file and license.video_file.duration:
                    # Use real video file duration if available via relationship
                    duration_seconds = int(license.video_file.duration.total_seconds())
                elif license_number in video_files_dict:
                    # Use VideoFile found by number if license.video_file is None
                    video_file = video_files_dict[license_number]
                    duration_seconds = int(video_file.duration.total_seconds())
                
                enriched_item["duration"] = duration_seconds
                enriched_item["license_id"] = license.id
                
                # Get author and sender_responsible from profile
                if license.profile:
                    author_name = f"{license.profile.first_name or ''} {license.profile.last_name or ''}".strip()
                    enriched_item["author"] = author_name
                    enriched_item["sender_responsible"] = author_name
                else:
                    enriched_item["author"] = item.get("author", "")
                    enriched_item["sender_responsible"] = item.get("sender_responsible", item.get("author", ""))
            # If license not found, use saved data (fallback)
            
            enriched_items.append(enriched_item)
        
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
            plan = TagesPlan.objects.get(datum=date_obj)
            plan.delete()
            return JsonResponse({"status": "deleted"}, status=204)
        except TagesPlan.DoesNotExist:
            return JsonResponse({"error": _("No plan for this day")}, status=404)
    else:
        return JsonResponse({"error": _("Method not allowed")}, status=405)


def calendar_weeks_view(request):
    """Render the calendar weeks view.

    Implementation of the calendar_weeks_view.
    """
    return HttpResponseRedirect(reverse("admin:calendar_weeks_view"))
