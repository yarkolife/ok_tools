"""Admin for the notes of the manual (edited from the chapter page)."""

from .models import HandbuchNotiz
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from ok_tools.admin_base import ModelAdmin


@admin.register(HandbuchNotiz)
class HandbuchNotizAdmin(ModelAdmin):
    """Notes are written on the chapter page; this admin edits or removes them."""

    list_display = ('kapitel', 'text', 'created_by', 'updated_at')
    list_filter = ('kapitel',)
    search_fields = ('text',)
    readonly_fields = ('kapitel', 'created_by', 'created_at', 'updated_at')
    fields = ('kapitel', 'text', 'created_by', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        # A note belongs to a chapter: it is added on the chapter page.
        return False

    def _back_to_chapter(self, obj):
        url = reverse('admin:handbuch_kapitel', args=[obj.kapitel])
        return HttpResponseRedirect(f'{url}#notizen')

    def response_change(self, request, obj):
        if '_continue' in request.POST:
            return super().response_change(request, obj)
        return self._back_to_chapter(obj)
