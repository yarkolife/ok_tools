"""Admin interface for running management commands."""

from django.contrib import admin
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.management import call_command
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.utils.html import format_html
from io import StringIO
import logging

from media_files.tasks import (
    run_auto_scan_task,
    run_scan_video_storage_task,
    run_sync_licenses_videos_task,
    run_link_orphan_licenses_task,
    run_cleanup_playout_task,
    run_find_duplicates_task,
    run_cleanup_duplicates_task,
)


logger = logging.getLogger('django')


class SystemManagementAdmin:
    """
    Pseudo-admin for system management commands.
    
    Provides a UI to run management commands without terminal access.
    """
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_staff
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_module_permission(self, request):
        return request.user.is_staff


def system_management_view(request):
    """View for running system management commands."""
    
    if not request.user.is_staff:
        messages.error(request, _('Permission denied'))
        return redirect('admin:index')
    
    # Handle command execution
    if request.method == 'POST':
        command = request.POST.get('command')
        options = {}
        
        # Parse command-specific options
        if command == 'scan_video_storage':
            storage_id = request.POST.get('storage_id')
            if storage_id:
                options['storage_id'] = int(storage_id)
            else:
                options['all'] = True
            if request.POST.get('force'):
                options['force'] = True
            if request.POST.get('strict_check'):
                options['strict_check'] = True
            if request.POST.get('calculate_checksum'):
                options['calculate_checksum'] = True
            if request.POST.get('skip_metadata'):
                options['skip_metadata'] = True
            if request.POST.get('delete_missing'):
                options['delete_missing'] = True
        
        elif command == 'auto_scan':
            if request.POST.get('force'):
                options['force'] = True
            if request.POST.get('strict_check'):
                options['strict_check'] = True
            if request.POST.get('calculate_checksums'):
                options['calculate_checksums'] = True
            if request.POST.get('skip_metadata'):
                options['skip_metadata'] = True
            storage_type = request.POST.get('storage_type')
            if storage_type:
                options['storage_type'] = storage_type
        
        elif command == 'sync_licenses_videos':
            if request.POST.get('dry_run'):
                options['dry_run'] = True
            if request.POST.get('force_sync_duration'):
                options['force_sync_duration'] = True
            number = request.POST.get('number')
            if number:
                options['number'] = int(number)
        
        elif command == 'link_orphan_licenses':
            if request.POST.get('dry_run'):
                options['dry_run'] = True
            if request.POST.get('scan_first'):
                options['scan_first'] = True
                # Add scan options if scan_first is enabled
                if request.POST.get('force_scan'):
                    options['force_scan'] = True
                if request.POST.get('strict_check_scan'):
                    options['strict_check_scan'] = True
                if request.POST.get('skip_metadata_scan'):
                    options['skip_metadata_scan'] = True
            number = request.POST.get('number')
            if number:
                options['number'] = int(number)
        
        elif command == 'cleanup_playout':
            if request.POST.get('dry_run'):
                options['dry_run'] = True
            if request.POST.get('check_attributes'):
                options['check_attributes'] = True
            if request.POST.get('check_locks'):
                options['check_locks'] = True
            older_than = request.POST.get('older_than', '7')
            options['older_than'] = int(older_than)
            storage_id = request.POST.get('storage_id')
            if storage_id:
                options['storage_id'] = int(storage_id)
        
        elif command == 'find_duplicates':
            # Map UI options to actual command parameters
            if request.POST.get('output_format') == 'json':
                options['json'] = True
            storage_type = request.POST.get('storage_type')
            if storage_type:
                options['storage_type'] = storage_type
            # Note: find_duplicates doesn't have number or min_duplicates parameters
        
        elif command == 'cleanup_duplicates':
            if request.POST.get('dry_run'):
                options['dry_run'] = True
            storage_type = request.POST.get('storage_type')
            if storage_type:
                options['storage_type'] = storage_type
            number = request.POST.get('number')
            if number:
                options['number'] = int(number)
        
        # Execute command via Celery task
        try:
            task = None
            
            # Map commands to Celery tasks
            if command == 'scan_video_storage':
                task = run_scan_video_storage_task.delay(**options)
            elif command == 'auto_scan':
                task = run_auto_scan_task.delay(**options)
            elif command == 'sync_licenses_videos':
                task = run_sync_licenses_videos_task.delay(**options)
            elif command == 'link_orphan_licenses':
                task = run_link_orphan_licenses_task.delay(**options)
            elif command == 'cleanup_playout':
                task = run_cleanup_playout_task.delay(**options)
            elif command == 'find_duplicates':
                task = run_find_duplicates_task.delay(**options)
            elif command == 'cleanup_duplicates':
                task = run_cleanup_duplicates_task.delay(**options)
            else:
                messages.error(request, f'❌ {_("Unknown command")}: {command}')
                logger.error(f'Unknown command: {command}')
                return redirect('admin:media_files_system_management')
            
            if task:
                # Create link to task results
                task_results_url = reverse('admin:django_celery_results_taskresult_changelist')
                task_results_url += f'?task_id__exact={task.id}'
                
                message = format_html(
                    '✓ {}! {}: <strong>{}</strong>. {}<br>'
                    '<a href="{}" target="_blank">{} →</a>',
                    _("Task queued successfully"),
                    _("Task ID"),
                    task.id,
                    _("The command is running in the background. Check task results for progress."),
                    task_results_url,
                    _("View Task Results")
                )
                messages.success(request, message)
                
                logger.info(
                    f'User {request.user.username} queued Celery task: {command} '
                    f'(task_id={task.id}) with options: {options}'
                )
            
        except Exception as e:
            messages.error(request, f'❌ {_("Error queueing task")}: {str(e)}')
            logger.error(f'Error queueing task {command}: {str(e)}', exc_info=True)
    
    # Get list of available storage locations for dropdowns
    from media_files.models import StorageLocation
    storages = StorageLocation.objects.filter(is_active=True)
    playout_storages = storages.filter(storage_type='PLAYOUT')
    
    context = {
        'title': _('System Management'),
        'storages': storages,
        'playout_storages': playout_storages,
        'site_header': admin.site.site_header,
        'site_title': admin.site.site_title,
        'has_permission': True,
    }
    
    return render(request, 'admin/system_management.html', context)
