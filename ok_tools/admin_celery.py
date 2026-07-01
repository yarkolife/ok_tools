"""Custom admin for Celery Beat periodic tasks and task results."""

from ast import literal_eval
from celery import current_app
from django.contrib import admin
from django.contrib import messages
from django.urls import reverse
from django.utils.html import format_html
from django.utils.html import format_html_join
from django.utils.translation import gettext_lazy as _
from django_celery_beat.models import ClockedSchedule
from django_celery_beat.models import CrontabSchedule
from django_celery_beat.models import IntervalSchedule
from django_celery_beat.models import PeriodicTask
from django_celery_beat.models import SolarSchedule
import json


try:
    from django_celery_beat.admin import \
        PeriodicTaskAdmin as BasePeriodicTaskAdmin
except ImportError:
    # Fallback if admin is not available
    from django.contrib.admin import ModelAdmin as BasePeriodicTaskAdmin

from django_celery_results.models import TaskResult


TASK_DISPLAY_NAMES = {
    'austausch.tasks.download_exchange_files': _('Download exchange files'),
    'austausch.tasks.export_to_server': _('Export broadcasts to server'),
    'austausch.tasks.import_exchange_item': _('Import exchange item'),
    'austausch.tasks.sync_exchange_folders': _('Synchronize exchange folders'),
    'celery.backend_cleanup': _('Clean up Celery task results'),
    'licenses.tasks.download_nextcloud_video_file_to_storage': _('Download Nextcloud video to storage'),
    'licenses.tasks.refresh_license_mediathek_url': _('Refresh media library link'),
    'licenses.tasks.rescan_mediathek_links_for_period': _('Rescan media library links'),
    'licenses.tasks.send_license_notification_email': _('Send license notification email'),
    'media_files.tasks.copy_videos_for_plan': _('Copy videos for broadcast plan'),
    'media_files.tasks.render_video_task': _('Render video'),
    'media_files.tasks.run_auto_scan': _('Run automatic media scan'),
    'media_files.tasks.run_cleanup_duplicates': _('Clean up duplicate media files'),
    'media_files.tasks.run_cleanup_missing_files': _('Clean up missing media files'),
    'media_files.tasks.run_cleanup_old_file_operations': _('Clean up old file operations'),
    'media_files.tasks.run_cleanup_playout': _('Clean up playout storage'),
    'media_files.tasks.run_find_duplicates': _('Find duplicate media files'),
    'media_files.tasks.run_link_orphan_licenses': _('Link unassigned licenses'),
    'media_files.tasks.run_scan_video_storage': _('Scan video storage'),
    'media_files.tasks.run_sync_licenses_videos': _('Synchronize licenses and videos'),
    'media_files.tasks.run_update_video_metadata': _('Update video metadata'),
    'media_files.tasks.transcode_hevc_to_h264': _('Convert HEVC video to H.264'),
    'ok_tools.tasks.cleanup_old_backups_task': _('Clean up old backups'),
    'ok_tools.tasks.run_backup_db_task': _('Create database backup'),
    'ok_tools.tasks.run_cleanup_deleted_nextcloud_videos_task': _('Clean up deleted Nextcloud videos'),
    'ok_tools.tasks.run_cleanup_signing_sessions_task': _('Clean up old signing sessions'),
    'ok_tools.tasks.run_expire_room_rentals_task': _('Expire outdated room rentals'),
    'ok_tools.tasks.send_return_reminders_task': _('Send return reminders'),
    'planung.tasks.anchor_render_chain': _('Anchor Render Chain'),
    'planung.tasks.poll_anchor_render_job': _('Poll anchor render job'),
    'planung.tasks.sync_playout_missing_media': _('Synchronize missing playout media'),
    'tools.tasks.analyze_audio_normalize_job': _('Analyze audio for normalization'),
    'tools.tasks.cleanup_old_audio_normalize_jobs_task': _('Clean up old audio normalization jobs'),
    'tools.tasks.cleanup_old_projects_task': _('Clean up old slideshow projects'),
    'tools.tasks.cleanup_old_video_render_operations_task': _('Clean up old video render operations'),
    'tools.tasks.send_daily_reel_reminder': _('Send daily reel reminder'),
    'tools.tasks.generate_slideshow': _('Generate slideshow video'),
    'tools.tasks.normalize_audio': _('Normalize audio'),
}

PERIODIC_TASK_NAMES = {
    'auto_scan': 'media_files.tasks.run_auto_scan',
    'celery.backend_cleanup': 'celery.backend_cleanup',
    'cleanup_deleted_nextcloud_videos': 'ok_tools.tasks.run_cleanup_deleted_nextcloud_videos_task',
    'cleanup_missing_files': 'media_files.tasks.run_cleanup_missing_files',
    'cleanup_old_audio_normalize_jobs': 'tools.tasks.cleanup_old_audio_normalize_jobs_task',
    'cleanup_old_backups': 'ok_tools.tasks.cleanup_old_backups_task',
    'cleanup_old_file_operations': 'media_files.tasks.run_cleanup_old_file_operations',
    'cleanup_old_tool_projects': 'tools.tasks.cleanup_old_projects_task',
    'cleanup_old_video_render_operations': 'tools.tasks.cleanup_old_video_render_operations_task',
    'cleanup_signing_sessions': 'ok_tools.tasks.run_cleanup_signing_sessions_task',
    'expire_rentals': 'ok_tools.tasks.run_expire_room_rentals_task',
    'link_orphan_licenses': 'media_files.tasks.run_link_orphan_licenses',
    'run_backup_db': 'ok_tools.tasks.run_backup_db_task',
    'send_return_reminders': 'ok_tools.tasks.send_return_reminders_task',
    'sync_exchange_folders': 'austausch.tasks.sync_exchange_folders',
    'sync_licenses_videos': 'media_files.tasks.run_sync_licenses_videos',
    'sync_playout_missing_media': 'planung.tasks.sync_playout_missing_media',
    'update_video_metadata': 'media_files.tasks.run_update_video_metadata',
}

TASK_STATUS_NAMES = {
    'FAILURE': _('Failed'),
    'PENDING': _('Waiting'),
    'PROGRESS': _('In progress'),
    'RECEIVED': _('Received'),
    'RETRY': _('Retrying'),
    'REVOKED': _('Canceled'),
    'STARTED': _('Started'),
    'SUCCESS': _('Completed'),
}

TASK_PROGRESS_STATUS_NAMES = {
    'completed': _('Completed'),
    'downloading': _('Downloading'),
    'exporting': _('Exporting'),
    'failed': _('Failed'),
    'importing': _('Importing'),
    'processing': _('Processing'),
    'rendering': _('Rendering'),
    'skipped': _('Skipped'),
    'success': _('Completed'),
    'uploading': _('Uploading'),
}

TASK_FIELD_LABELS = {
    'current': _('Current'),
    'current_item_id': _('Current item ID'),
    'details': _('Details'),
    'error': _('Error'),
    'exc_message': _('Exception message'),
    'exc_module': _('Exception module'),
    'exc_type': _('Exception type'),
    'failure_count': _('Failed'),
    'failed': _('Failed entries'),
    'job_id': _('Job ID'),
    'output_file': _('Output file'),
    'output_path_external': _('External output path'),
    'progress': _('Progress'),
    'reason': _('Reason'),
    'recommendations': _('Recommendations'),
    'run_id': _('Report ID'),
    'skipped_no_pdf': _('Skipped without PDF'),
    'skipped_no_pdf_count': _('Skipped without PDF'),
    'speed_mbps': _('Upload speed'),
    'status': _('Status'),
    'success_count': _('Successful'),
    'success_ids': _('Successful IDs'),
    'success_license_numbers': _('Successful license numbers'),
    'total': _('Total'),
}


def _get_task_display_name(task_name):
    """Return a user-facing task name while keeping unknown task names readable."""
    if not task_name:
        return _('Unknown task')
    return TASK_DISPLAY_NAMES.get(task_name, task_name.rsplit('.', 1)[-1].replace('_', ' ').title())


def _get_periodic_task_display_name(periodic_task_name, task_name=None):
    """Return a user-facing PeriodicTask name while keeping the stored name unchanged."""
    if not periodic_task_name:
        return _('Unknown periodic task')
    return _get_task_display_name(task_name or PERIODIC_TASK_NAMES.get(periodic_task_name, periodic_task_name))


def _replace_list_filter(list_filter, field_name, replacement):
    """Replace a model field list filter with a custom filter class."""
    filters = []
    replaced = False
    for item in list_filter:
        item_field_name = item[0] if isinstance(item, tuple) else item
        if item_field_name == field_name:
            if not replaced:
                filters.append(replacement)
                replaced = True
            continue
        filters.append(item)
    if not replaced:
        filters.append(replacement)
    return tuple(filters)


def _replace_list_display(list_display, field_name, replacement):
    """Replace a ModelAdmin list_display field with a computed display method."""
    display = []
    replaced = False
    for item in list_display:
        if item == field_name:
            if not replaced:
                display.append(replacement)
                replaced = True
            continue
        display.append(item)
    if not replaced:
        display.insert(0, replacement)
    return tuple(display)


class ReadableTaskNameFilter(admin.SimpleListFilter):
    """TaskResult task filter using user-facing task names."""

    title = _('Task')
    parameter_name = 'task_name__exact'

    def lookups(self, request, model_admin):
        task_names = (
            model_admin.get_queryset(request)
            .exclude(task_name='')
            .values_list('task_name', flat=True)
            .distinct()
        )
        choices = ((task_name, _get_task_display_name(task_name)) for task_name in task_names if task_name)
        return sorted(choices, key=lambda choice: str(choice[1]).casefold())

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(task_name=self.value())
        return queryset


class ReadablePeriodicTaskNameFilter(admin.SimpleListFilter):
    """TaskResult periodic task filter using user-facing periodic task names."""

    title = _('Periodic Task Name')
    parameter_name = 'periodic_task_name'

    def lookups(self, request, model_admin):
        periodic_task_names = (
            model_admin.get_queryset(request)
            .exclude(periodic_task_name='')
            .values_list('periodic_task_name', flat=True)
            .distinct()
        )
        choices = (
            (periodic_task_name, _get_periodic_task_display_name(periodic_task_name))
            for periodic_task_name in periodic_task_names
            if periodic_task_name
        )
        return sorted(choices, key=lambda choice: str(choice[1]).casefold())

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(periodic_task_name=self.value())
        return queryset


class ReadablePeriodicTaskFilter(admin.SimpleListFilter):
    """PeriodicTask task filter using user-facing task names."""

    title = _('Task')
    parameter_name = 'task__exact'

    def lookups(self, request, model_admin):
        task_names = (
            model_admin.get_queryset(request)
            .exclude(task='')
            .values_list('task', flat=True)
            .distinct()
        )
        choices = ((task_name, _get_task_display_name(task_name)) for task_name in task_names if task_name)
        return sorted(choices, key=lambda choice: str(choice[1]).casefold())

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(task=self.value())
        return queryset


def _loads_json(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None


def _loads_task_args(value):
    parsed = _loads_json(value)
    if isinstance(parsed, str):
        try:
            return literal_eval(parsed)
        except (SyntaxError, ValueError):
            return parsed
    return parsed


def _is_empty_task_value(value):
    parsed = _loads_task_args(value)
    if parsed in (None, '', '-', (), [], {}):
        return True
    if isinstance(parsed, str) and parsed.strip() in ('', '-', '()', '[]', '{}'):
        return True
    return False


def _format_task_value(value):
    parsed = _loads_task_args(value)
    if parsed is None:
        return '-'
    return parsed


def _format_field_label(key):
    if key in TASK_FIELD_LABELS:
        return TASK_FIELD_LABELS[key]
    return str(key).replace('_', ' ').title()


def _format_sequence(values):
    if not values:
        return '-'
    return format_html(
        '<ul style="margin: 0; padding-left: 1.25rem;">{}</ul>',
        format_html_join(
            '',
            '<li>{}</li>',
            ((_format_generic_value(None, value),) for value in values),
        ),
    )


def _format_mapping(mapping):
    if not mapping:
        return '-'
    return _format_definition_list(
        (_format_field_label(key), _format_generic_value(key, value))
        for key, value in mapping.items()
    )


def _format_generic_value(key, value):
    if value in (None, ''):
        return '-'
    if key == 'status' and isinstance(value, str):
        return TASK_PROGRESS_STATUS_NAMES.get(value, TASK_STATUS_NAMES.get(value, value))
    if isinstance(value, bool):
        return _('Yes') if value else _('No')
    if isinstance(value, dict):
        return _format_mapping(value)
    if isinstance(value, (list, tuple, set)):
        return _format_sequence(list(value))
    if isinstance(value, str) and value.startswith(('http://', 'https://')):
        return format_html('<a href="{}">{}</a>', value, value)
    return value


def _format_definition_list(rows):
    return format_html(
        '<dl style="margin: 0;">{}</dl>',
        format_html_join(
            '',
            '<dt style="font-weight: 600;">{}</dt><dd style="margin: 0 0 0.5rem;">{}</dd>',
            rows,
        ),
    )


def _format_mode(mode):
    if mode == 'licenses':
        return _('licenses')
    if mode == 'contributions':
        return _('contributions')
    return mode or _('unknown')


def _format_count(value):
    if isinstance(value, (list, tuple, set)):
        return len(value)
    return value


def _get_export_task_args(obj):
    if obj.task_name != 'austausch.tasks.export_to_server':
        return None
    args = _loads_task_args(obj.task_args)
    if not isinstance(args, tuple) or len(args) < 2:
        return None
    selected_ids = args[0] if isinstance(args[0], (list, tuple)) else []
    user_id = args[2] if len(args) >= 3 else None
    return selected_ids, args[1], user_id


def _admin_change_link(url_name, obj_id, label):
    try:
        url = reverse(url_name, args=[obj_id])
    except Exception:
        return label
    return format_html('<a href="{}">{}</a>', url, label)


def _format_user_link(user_id):
    if not user_id:
        return '-'
    try:
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.filter(pk=user_id).first()
    except Exception:
        user = None
    if not user:
        return _('User ID %(user_id)s') % {'user_id': user_id}
    label = getattr(user, 'email', None) or str(user)
    return _admin_change_link(
        'admin:registration_user_change',
        user.pk,
        _('%(label)s (ID %(user_id)s)') % {'label': label, 'user_id': user_id},
    )


def _format_license_links(numbers, limit=20):
    try:
        from licenses.models import License
        licenses = {
            license_obj.number: license_obj
            for license_obj in License.objects.filter(number__in=numbers)
        }
    except Exception:
        licenses = {}

    links = []
    for number in numbers[:limit]:
        license_obj = licenses.get(number)
        if license_obj:
            label = _('#%(number)s %(title)s') % {
                'number': license_obj.number,
                'title': license_obj.title or '',
            }
            links.append(_admin_change_link('admin:licenses_license_change', license_obj.pk, label))
        else:
            links.append(_('#%(number)s (not found)') % {'number': number})
    return _format_link_list(links, numbers, limit)


def _format_contribution_links(ids, limit=20):
    try:
        from contributions.models import Contribution
        contributions = {
            contribution.pk: contribution
            for contribution in Contribution.objects.select_related('license').filter(pk__in=ids)
        }
    except Exception:
        contributions = {}

    links = []
    for contribution_id in ids[:limit]:
        contribution = contributions.get(contribution_id)
        if contribution:
            label = _('#%(id)s - license %(number)s %(title)s') % {
                'id': contribution.pk,
                'number': contribution.license.number,
                'title': contribution.license.title or '',
            }
            links.append(_admin_change_link(
                'admin:contributions_contribution_change',
                contribution.pk,
                label,
            ))
        else:
            links.append(_('#%(id)s (not found)') % {'id': contribution_id})
    return _format_link_list(links, ids, limit)


def _format_link_list(links, all_values, limit):
    more_count = max(len(all_values) - limit, 0)
    if more_count:
        links.append(_('and %(count)s more') % {'count': more_count})
    return format_html(
        '<ul style="margin: 0; padding-left: 1.25rem;">{}</ul>',
        format_html_join('', '<li>{}</li>', ((link,) for link in links)),
    )


def _format_selected_entries(mode, selected_ids):
    if not selected_ids:
        return _('No selected entries')
    if mode == 'licenses':
        return _format_license_links(selected_ids)
    if mode == 'contributions':
        return _format_contribution_links(selected_ids)
    return ', '.join(str(value) for value in selected_ids)


def _format_current_entry(mode, item_id):
    if not item_id:
        return '-'
    if mode == 'licenses':
        return _format_license_links([item_id], limit=1)
    if mode == 'contributions':
        return _format_contribution_links([item_id], limit=1)
    return item_id


@admin.action(description=_('Run selected periodic tasks now'))
def run_periodic_tasks_now(modeladmin, request, queryset):
    """Admin action to run selected periodic tasks immediately."""
    success_count = 0
    error_count = 0
    
    for task in queryset:
        try:
            # Get the task function from Celery app
            celery_app = current_app
            task_func = celery_app.tasks.get(task.task)
            
            if task_func is None:
                messages.error(
                    request,
                    _('Task "%(task_name)s" not found in Celery app.') % {'task_name': task.task}
                )
                error_count += 1
                continue
            
            # Parse task kwargs if available
            import json
            kwargs = {}
            if task.kwargs:
                try:
                    kwargs = json.loads(task.kwargs)
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Run task asynchronously
            result = task_func.apply_async(kwargs=kwargs)
            
            messages.success(
                request,
                _('Task "%(task_name)s" started. Task ID: %(task_id)s') % {
                    'task_name': task.name,
                    'task_id': result.id
                }
            )
            success_count += 1
            
        except Exception as e:
            messages.error(
                request,
                _('Error running task "%(task_name)s": %(error)s') % {
                    'task_name': task.name,
                    'error': str(e)
                }
            )
            error_count += 1
    
    if success_count > 0:
        messages.success(request, _('%d task(s) started successfully.') % success_count)
    if error_count > 0:
        messages.warning(request, _('%d task(s) failed to start.') % error_count)


class PeriodicTaskAdmin(BasePeriodicTaskAdmin):
    """Custom admin for PeriodicTask with run task action."""
    
    # Use custom template to add "Run task now" button
    change_form_template = 'admin/django_celery_beat/periodictask/change_form.html'
    
    # Get base actions and add our custom action
    base_actions = getattr(BasePeriodicTaskAdmin, 'actions', [])
    actions = list(base_actions) + [run_periodic_tasks_now]
    
    # Get base list_display and extend it
    base_list_display = getattr(BasePeriodicTaskAdmin, 'list_display', ('name', 'task', 'enabled'))
    # Convert to list, replace raw name, extend, then convert back to tuple (Django expects tuple)
    list_display = tuple(
        list(_replace_list_display(base_list_display, 'name', 'readable_periodic_task_name')) +
        ['last_run_info', 'task_results_link']
    )
    list_display_links = ('readable_periodic_task_name',)
    
    # Get base readonly_fields and extend it
    base_readonly_fields = getattr(BasePeriodicTaskAdmin, 'readonly_fields', ())
    readonly_fields = tuple(base_readonly_fields) + ('last_run_info', 'task_results_link')

    base_list_filter = getattr(BasePeriodicTaskAdmin, 'list_filter', ())
    list_filter = _replace_list_filter(base_list_filter, 'task', ReadablePeriodicTaskFilter)

    def readable_periodic_task_name(self, obj):
        """Display the periodic task name in a way staff users can understand."""
        return _get_periodic_task_display_name(obj.name, obj.task)
    readable_periodic_task_name.short_description = _('Name')
    readable_periodic_task_name.admin_order_field = 'name'
    
    def last_run_info(self, obj):
        """Display last run information."""
        if obj.last_run_at:
            return format_html(
                '<strong>{}</strong><br><small>{}</small>',
                obj.last_run_at.strftime('%Y-%m-%d %H:%M:%S'),
                _('Total runs: {}').format(obj.total_run_count or 0)
            )
        return _('Never run')
    last_run_info.short_description = _('Last Run')
    
    def task_results_link(self, obj):
        """Link to task results for this periodic task."""
        if not obj.task:
            return _('No task specified')
        
        # Count recent task results
        recent_results = TaskResult.objects.filter(task_name=obj.task).order_by('-date_created')[:5]
        count = TaskResult.objects.filter(task_name=obj.task).count()
        
        if count == 0:
            return _('No results yet')
        
        # Get URL to task results admin filtered by task name
        url = reverse('admin:django_celery_results_taskresult_changelist')
        url += f'?task_name__exact={obj.task}'
        
        # Get last result status
        last_result = recent_results.first() if recent_results else None
        status_color = 'green' if last_result and last_result.status == 'SUCCESS' else 'orange' if last_result and last_result.status == 'FAILURE' else 'gray'
        
        return format_html(
            '<a href="{}" style="color: {};">{} {}</a><br><small>{}</small>',
            url,
            status_color,
            _('View Results'),
            f'({count})',
            _('Last: {}').format(last_result.status if last_result else _('N/A'))
        )
    task_results_link.short_description = _('Task Results')
    
    def response_change(self, request, obj):
        """Handle 'Run task now' button click."""
        if '_run_task' in request.POST:
            # Run the task
            try:
                celery_app = current_app
                task_func = celery_app.tasks.get(obj.task)
                
                if task_func is None:
                    messages.error(request, _('Task "%(task_name)s" not found in Celery app.') % {'task_name': obj.task})
                    return super().response_change(request, obj)
                
                # Parse task kwargs if available
                import json
                kwargs = {}
                if obj.kwargs:
                    try:
                        kwargs = json.loads(obj.kwargs)
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                # Run task asynchronously
                result = task_func.apply_async(kwargs=kwargs)
                
                messages.success(
                    request,
                    _('Task "%(task_name)s" started successfully. Task ID: %(task_id)s') % {
                        'task_name': obj.name,
                        'task_id': result.id
                    }
                )
            except Exception as e:
                messages.error(
                    request,
                    _('Error running task "%(task_name)s": %(error)s') % {
                        'task_name': obj.name,
                        'error': str(e)
                    }
                )
            
            # Redirect back to change page to show the message
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(request.path)
        
        return super().response_change(request, obj)
    


# Unregister default admin and register custom admin
# This must be done after all apps are loaded
def register_periodic_task_admin():
    """Register custom PeriodicTask admin."""
    try:
        # Try to unregister if already registered
        try:
            admin.site.unregister(PeriodicTask)
        except admin.sites.NotRegistered:
            # PeriodicTask might not be registered yet, which is fine
            pass
        
        # Register our custom admin
        admin.site.register(PeriodicTask, PeriodicTaskAdmin)
        
        # Log success (only in debug mode)
        import logging
        logger = logging.getLogger(__name__)
        logger.debug("Custom PeriodicTaskAdmin registered successfully")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to register PeriodicTaskAdmin: {e}", exc_info=True)

# Register the admin
register_periodic_task_admin()

# Hide unused schedule types from admin (we only use Crontab and ClockedSchedule)
def hide_unused_schedules():
    """
    Hide IntervalSchedule and SolarSchedule from admin since we don't use them.
    
    ClockedSchedule is kept visible for one-time scheduled tasks (e.g., "run task exactly on Dec 25 at 15:30").
    """
    try:
        # Try to unregister IntervalSchedule if registered
        try:
            admin.site.unregister(IntervalSchedule)
        except admin.sites.NotRegistered:
            pass
        
        # Try to unregister SolarSchedule if registered
        try:
            admin.site.unregister(SolarSchedule)
        except admin.sites.NotRegistered:
            pass
        
        # ClockedSchedule is kept available for one-time scheduled tasks
        # (not unregistering it)
        
        import logging
        logger = logging.getLogger(__name__)
        logger.debug("Hidden unused schedule types from admin")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to hide unused schedules: {e}")

# Hide unused schedules
hide_unused_schedules()

# Custom admin for TaskResult to improve visibility
try:
    from django_celery_results.admin import \
        TaskResultAdmin as BaseTaskResultAdmin
    from django_celery_results.models import GroupResult
    from django_celery_results.models import TaskResult
    
    class TaskResultAdmin(BaseTaskResultAdmin):
        """Custom admin for TaskResult with better filtering and display."""
        
        base_list_filter = getattr(BaseTaskResultAdmin, 'list_filter', ())
        list_filter = _replace_list_filter(
            _replace_list_filter(
                tuple(base_list_filter) + ('task_name', 'periodic_task_name', 'status', 'date_created'),
                'task_name',
                ReadableTaskNameFilter,
            ),
            'periodic_task_name',
            ReadablePeriodicTaskNameFilter,
        )
        
        base_search_fields = getattr(BaseTaskResultAdmin, 'search_fields', ())
        search_fields = list(base_search_fields) + ['task_name']
        
        list_display = (
            'readable_task_name',
            'readable_status',
            'readable_progress',
            'date_done',
            'readable_periodic_task_name',
        )
        readonly_fields = tuple(getattr(BaseTaskResultAdmin, 'readonly_fields', ())) + (
            'readable_task_name',
            'readable_periodic_task_name',
            'readable_status',
            'readable_progress',
            'readable_parameters',
            'readable_result',
        )
        fieldsets = (
            (_('Overview'), {
                'fields': (
                    'readable_task_name',
                    'readable_periodic_task_name',
                    'readable_status',
                    'readable_progress',
                    'readable_parameters',
                    'readable_result',
                    'date_created',
                    'date_done',
                ),
                'classes': ('extrapretty', 'wide'),
            }),
            (_('Technical details'), {
                'fields': (
                    'task_id',
                    'task_name',
                    'periodic_task_name',
                    'status',
                    'worker',
                    'content_type',
                    'content_encoding',
                    'task_args',
                    'task_kwargs',
                    'result',
                    'traceback',
                    'meta',
                ),
                'classes': ('collapse', 'extrapretty', 'wide'),
            }),
        )

        def readable_task_name(self, obj):
            """Display the task name in a way staff users can understand."""
            return _get_task_display_name(obj.task_name)
        readable_task_name.short_description = _('Task')
        readable_task_name.admin_order_field = 'task_name'

        def readable_periodic_task_name(self, obj):
            """Display the periodic task name in a way staff users can understand."""
            return _get_periodic_task_display_name(obj.periodic_task_name, obj.task_name)
        readable_periodic_task_name.short_description = _('Periodic Task Name')
        readable_periodic_task_name.admin_order_field = 'periodic_task_name'

        def get_readonly_fields(self, request, obj=None):
            """Keep computed fields readonly with django-celery-results edits disabled."""
            custom_fields = (
                'readable_task_name',
                'readable_periodic_task_name',
                'readable_status',
                'readable_progress',
                'readable_parameters',
                'readable_result',
            )
            return tuple(dict.fromkeys([*super().get_readonly_fields(request, obj), *custom_fields]))

        def readable_status(self, obj):
            """Display the Celery status with a translated label."""
            label = TASK_STATUS_NAMES.get(obj.status, obj.status or _('Unknown'))
            colors = {
                'FAILURE': '#ba2121',
                'PROGRESS': '#b35f00',
                'RETRY': '#b35f00',
                'SUCCESS': '#118811',
            }
            color = colors.get(obj.status, 'var(--body-fg)')
            return format_html('<strong style="color: {};">{}</strong>', color, label)
        readable_status.short_description = _('Status')
        readable_status.admin_order_field = 'status'

        def readable_progress(self, obj):
            """Summarize task progress from stored result metadata."""
            data = _loads_json(obj.result)
            if not isinstance(data, dict):
                return '-'

            progress = data.get('progress')
            current = data.get('current')
            total = data.get('total')
            status = TASK_PROGRESS_STATUS_NAMES.get(data.get('status'), data.get('status'))
            speed = data.get('speed_mbps')
            parts = []

            if progress is not None:
                parts.append(_('%(progress)s%% complete') % {'progress': progress})
            if current is not None and total is not None:
                parts.append(_('%(current)s of %(total)s') % {'current': current, 'total': total})
            if status:
                parts.append(str(status))
            if speed:
                parts.append(_('%(speed)s Mbit/s') % {'speed': speed})

            return ' · '.join(parts) if parts else '-'
        readable_progress.short_description = _('Progress')

        def readable_parameters(self, obj):
            """Show the user-relevant task arguments."""
            export_args = _get_export_task_args(obj)
            if export_args:
                selected_ids, mode, user_id = export_args
                rows = [
                    (_('Export type'), _format_mode(mode)),
                    (_('Selected entries'), _format_count(selected_ids)),
                    (_('Linked entries'), _format_selected_entries(mode, selected_ids)),
                ]
                if user_id:
                    rows.append((_('Started by'), _format_user_link(user_id)))
                return _format_definition_list(rows)

            if _is_empty_task_value(obj.task_args) and _is_empty_task_value(obj.task_kwargs):
                return _('No parameters')

            rows = []
            args = _format_task_value(obj.task_args)
            kwargs = _format_task_value(obj.task_kwargs)
            if not _is_empty_task_value(obj.task_args):
                if isinstance(args, (list, tuple)):
                    rows.extend(
                        (_('Argument %(number)s') % {'number': index}, _format_generic_value(None, value))
                        for index, value in enumerate(args, start=1)
                    )
                else:
                    rows.append((_('Arguments'), _format_generic_value(None, args)))
            if not _is_empty_task_value(obj.task_kwargs):
                if isinstance(kwargs, dict):
                    rows.extend(
                        (_format_field_label(key), _format_generic_value(key, value))
                        for key, value in kwargs.items()
                    )
                else:
                    rows.append((_('Named arguments'), _format_generic_value(None, kwargs)))
            return _format_definition_list(rows)
        readable_parameters.short_description = _('Parameters')

        def readable_result(self, obj):
            """Show a concise result summary for common task result payloads."""
            data = _loads_json(obj.result)
            if not isinstance(data, dict):
                if _is_empty_task_value(obj.result):
                    return '-'
                return _format_generic_value('result', _format_task_value(obj.result))

            rows = []
            handled_keys = set()
            export_args = _get_export_task_args(obj)
            mode = export_args[1] if export_args else None

            if 'status' in data:
                rows.append((_('Status'), _format_generic_value('status', data.get('status'))))
                handled_keys.add('status')
            if 'success_count' in data:
                rows.append((_('Successful'), data.get('success_count')))
                handled_keys.add('success_count')
            if 'failure_count' in data:
                rows.append((_('Failed'), data.get('failure_count')))
                handled_keys.add('failure_count')
            if 'skipped_no_pdf_count' in data:
                rows.append((_('Skipped without PDF'), data.get('skipped_no_pdf_count')))
                handled_keys.add('skipped_no_pdf_count')
            if 'run_id' in data:
                rows.append((_('Report ID'), data.get('run_id')))
                handled_keys.add('run_id')
            if 'progress' in data:
                rows.append((_('Progress'), _('%(progress)s%% complete') % {'progress': data.get('progress')}))
                handled_keys.add('progress')
            if data.get('current') is not None and data.get('total') is not None:
                if data.get('status') == 'uploading':
                    rows.append((_('Uploaded chunks'), _('%(current)s of %(total)s') % {
                        'current': data.get('current'),
                        'total': data.get('total'),
                    }))
                    rows.append((_('Meaning'), _('The file is being uploaded in parts; this is the uploaded chunk count.')))
                else:
                    rows.append((_('Processed entries'), _('%(current)s of %(total)s') % {
                        'current': data.get('current'),
                        'total': data.get('total'),
                    }))
                handled_keys.update(('current', 'total'))
            if 'current_item_id' in data and data.get('current_item_id'):
                rows.append((_('Current entry'), _format_current_entry(mode, data.get('current_item_id'))))
                handled_keys.add('current_item_id')
            elif 'current_item_id' in data:
                handled_keys.add('current_item_id')
            if data.get('speed_mbps'):
                rows.append((_('Upload speed'), _('%(speed)s Mbit/s') % {'speed': data.get('speed_mbps')}))
                handled_keys.add('speed_mbps')

            rows.extend(
                (_format_field_label(key), _format_generic_value(key, value))
                for key, value in data.items()
                if key not in handled_keys
            )

            return _format_definition_list(rows) if rows else '-'
        readable_result.short_description = _('Result')
    
    # Register custom TaskResult admin
    if TaskResult in admin.site._registry:
        admin.site.unregister(TaskResult)
    admin.site.register(TaskResult, TaskResultAdmin)
    
    # Hide GroupResult from admin (not used - we don't use Celery groups/chords/chains)
    try:
        admin.site.unregister(GroupResult)
    except admin.sites.NotRegistered:
        pass
    
except (ImportError, Exception):
    # If TaskResultAdmin is not available or registration fails, skip customization
    pass
