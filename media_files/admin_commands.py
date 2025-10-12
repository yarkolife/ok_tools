"""Admin interface for running management commands."""

from django.contrib import admin
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.management import call_command
from django.utils.translation import gettext_lazy as _
from io import StringIO
import logging


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
        if command == 'scan_storage':
            storage_id = request.POST.get('storage_id')
            if storage_id:
                options['storage_id'] = int(storage_id)
            else:
                options['all'] = True
            if request.POST.get('force'):
                options['force'] = True
            if request.POST.get('calculate_checksum'):
                options['calculate_checksum'] = True
        
        elif command == 'auto_scan':
            if request.POST.get('force'):
                options['force'] = True
            if request.POST.get('calculate_checksums'):
                options['calculate_checksums'] = True
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
        
        # Execute command
        try:
            out = StringIO()
            err = StringIO()
            
            call_command(command, stdout=out, stderr=err, **options)
            
            output = out.getvalue()
            errors = err.getvalue()
            
            if errors:
                messages.error(request, f'❌ Ошибки при выполнении:\n{errors}')
            else:
                messages.success(request, f'✓ Команда выполнена успешно!')
                
                # Show output in a more readable format
                if output:
                    # Parse output for key statistics
                    lines = output.split('\n')
                    for line in lines:
                        if 'Complete' in line or 'found' in line.lower() or 'created' in line.lower():
                            messages.info(request, line)
            
            logger.info(f'User {request.user.username} executed command: {command} with options: {options}')
            
        except Exception as e:
            messages.error(request, f'❌ Ошибка выполнения команды: {str(e)}')
            logger.error(f'Error executing command {command}: {str(e)}', exc_info=True)
    
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
