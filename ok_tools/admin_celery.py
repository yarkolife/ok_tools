"""
Custom admin for Celery Beat periodic tasks.
Adds ability to run tasks manually from Django admin interface.
"""

from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import reverse
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
try:
    from django_celery_beat.admin import PeriodicTaskAdmin as BasePeriodicTaskAdmin
except ImportError:
    # Fallback if admin is not available
    from django.contrib.admin import ModelAdmin as BasePeriodicTaskAdmin
from django_celery_results.models import TaskResult
from celery import current_app
from django.utils.translation import gettext_lazy as _


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
    # Convert to list, extend, then convert back to tuple (Django expects tuple)
    list_display = tuple(list(base_list_display) + ['last_run_info', 'task_results_link'])
    
    # Get base readonly_fields and extend it
    base_readonly_fields = getattr(BasePeriodicTaskAdmin, 'readonly_fields', ())
    readonly_fields = tuple(base_readonly_fields) + ('last_run_info', 'task_results_link')
    
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

# Custom admin for TaskResult to improve visibility
try:
    from django_celery_results.admin import TaskResultAdmin as BaseTaskResultAdmin
    from django_celery_results.models import TaskResult
    
    class TaskResultAdmin(BaseTaskResultAdmin):
        """Custom admin for TaskResult with better filtering and display."""
        
        base_list_filter = getattr(BaseTaskResultAdmin, 'list_filter', ())
        list_filter = tuple(base_list_filter) + ('task_name', 'status', 'date_created')
        
        base_search_fields = getattr(BaseTaskResultAdmin, 'search_fields', ())
        search_fields = list(base_search_fields) + ['task_name']
        
        list_display = getattr(BaseTaskResultAdmin, 'list_display', None)
        readonly_fields = getattr(BaseTaskResultAdmin, 'readonly_fields', ())
    
    # Register custom TaskResult admin
    if TaskResult in admin.site._registry:
        admin.site.unregister(TaskResult)
    admin.site.register(TaskResult, TaskResultAdmin)
    
except (ImportError, Exception):
    # If TaskResultAdmin is not available or registration fails, skip customization
    pass

