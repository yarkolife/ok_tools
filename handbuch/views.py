"""Pages of the manual inside the admin."""

from .kapitel import available_chapters
from .kapitel import get_chapter
from .models import HandbuchNotiz
from django.contrib import messages
from django.http import Http404
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.translation import gettext as _


def handbuch_index(request, admin_site):
    """All chapters available in this installation."""
    chapters = available_chapters()
    counts = {}
    for row in HandbuchNotiz.objects.values_list('kapitel', flat=True):
        counts[row] = counts.get(row, 0) + 1
    context = {
        **admin_site.each_context(request),
        'title': _('Manual'),
        'chapters': [
            {'kapitel': kapitel, 'notes': counts.get(kapitel.slug, 0)}
            for kapitel in chapters
        ],
    }
    return TemplateResponse(request, 'handbuch/index.html', context)


def handbuch_kapitel(request, slug, admin_site):
    """One chapter, followed by the notes of the staff."""
    kapitel = get_chapter(slug)
    if kapitel is None:
        raise Http404(_('This chapter does not exist.'))

    url = reverse('admin:handbuch_kapitel', args=[slug])
    can_add = request.user.has_perm('handbuch.add_handbuchnotiz')
    if request.method == 'POST':
        text = (request.POST.get('text') or '').strip()
        if not can_add:
            messages.error(request, _('You may not add notes to the manual.'))
        elif not text:
            messages.error(request, _('The note is empty.'))
        else:
            HandbuchNotiz.objects.create(kapitel=slug, text=text, created_by=request.user)
            messages.success(request, _('The note was added.'))
        return HttpResponseRedirect(f'{url}#notizen')

    notes = HandbuchNotiz.objects.filter(kapitel=slug).select_related('created_by')
    context = {
        **admin_site.each_context(request),
        'title': kapitel.title,
        'kapitel': kapitel,
        'notes': notes,
        'can_add_note': can_add,
        'can_change_note': request.user.has_perm('handbuch.change_handbuchnotiz'),
        'index_url': reverse('admin:handbuch_index'),
    }
    return TemplateResponse(request, 'handbuch/kapitel.html', context)
