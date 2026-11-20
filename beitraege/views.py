"""Mobile pages: write a post, check and approve it, photos for Meta.

- "Neuer Beitrag" needs a login and the right to add posts.
- The check page opens for approvers who are logged in, or without login
  from the personal link in the approval mail. Opening only shows the post;
  approving needs the button (POST), because mail scanners open links on
  their own.
- Photo renditions are public under an unguessable token: Instagram and
  Facebook download them from there when publishing.
"""

from . import workflow
from .forms import NeuerBeitragForm
from .models import Beitrag
from .models import BeitragFoto
from .services import images
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods
from pathlib import Path


@login_required
@permission_required('beitraege.add_beitrag', raise_exception=True)
@require_http_methods(['GET', 'POST'])
def neu(request):
    form = NeuerBeitragForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            beitrag = Beitrag.objects.create(
                titel=data['titel'], text=data['text'], link=data['link'] or '',
                thema=data['thema'], einwilligung=data['einwilligung'],
                publish_at=data['publish_at'], created_by=request.user)
            for position, upload in enumerate(data['fotos']):
                BeitragFoto.objects.create(beitrag=beitrag, bild=upload, position=position)
            workflow.ensure_ziele(beitrag, platforms=data['plattformen'])
            workflow.submit(beitrag)
        return redirect('beitraege:eingereicht', pk=beitrag.pk)
    return render(request, 'beitraege/neu.html', {'form': form, 'title': _('New post')})


@login_required
def eingereicht(request, pk):
    beitrag = get_object_or_404(Beitrag, pk=pk)
    if beitrag.created_by_id != request.user.pk and not beitrag.may_approve(request.user):
        raise PermissionDenied
    return render(request, 'beitraege/eingereicht.html', {
        'beitrag': beitrag, 'title': _('Post submitted'),
        'may_approve': beitrag.may_approve(request.user),
    })


@login_required
@require_http_methods(['GET', 'POST'])
def pruefen(request, pk):
    beitrag = get_object_or_404(Beitrag.objects.select_related('thema'), pk=pk)
    return _check_page(request, beitrag, request.user)


@require_http_methods(['GET', 'POST'])
def freigabe(request, token):
    from .notify import from_token

    beitrag, user = from_token(token)
    if beitrag is None:
        return render(request, 'beitraege/pruefen.html', {
            'state': 'invalid', 'title': _('Invalid or expired link'),
            'message': _('This link is invalid or has expired. Open the post in OK-Tools instead.'),
        }, status=400)
    return _check_page(request, beitrag, user)


def _check_page(request, beitrag, user):
    if not beitrag.may_approve(user):
        raise PermissionDenied
    context = {
        'beitrag': beitrag,
        'ziele': beitrag.ziele.filter(aktiv=True),
        'fotos': beitrag.fotos.all(),
        'problems': workflow.problems(beitrag),
        'admin_url': reverse('admin:beitraege_beitrag_change', args=[beitrag.pk]),
        'approver': user,
    }
    open_states = (Beitrag.STATUS_DRAFT, Beitrag.STATUS_SUBMITTED, Beitrag.STATUS_REJECTED)
    if request.method == 'POST' and beitrag.status in open_states:
        if request.POST.get('aktion') == 'ablehnen':
            workflow.reject(beitrag, user, request.POST.get('grund', '').strip())
            context.update(state='done', title=_('Sent back'),
                           message=_('The author has been told.'))
            return render(request, 'beitraege/pruefen.html', context)
        try:
            workflow.approve(beitrag, user)
        except ValidationError as exc:
            context.update(state='error', title=_('The post cannot be approved'),
                           message='; '.join(exc.messages))
            return render(request, 'beitraege/pruefen.html', context, status=400)
        context.update(state='done', title=_('Approved'), message=(
            _('The post is being published now.') if beitrag.publish_at is None
            else _('The post is published at its time.')))
        return render(request, 'beitraege/pruefen.html', context)
    if beitrag.status not in open_states:
        context.update(state='done', title=_('Nothing to do'),
                       message=_('This post is already %(status)s.') % {
                           'status': beitrag.get_status_display().lower()})
        return render(request, 'beitraege/pruefen.html', context)
    context.update(state='confirm', title=_('Check the post'))
    return render(request, 'beitraege/pruefen.html', context)


def foto(request, token, variant):
    """A JPEG rendition of a photo, made once and kept next to the uploads."""
    if variant not in images.VARIANTS:
        raise Http404()
    photo = BeitragFoto.objects.filter(token=token).first()
    if photo is None:
        raise Http404()
    cache = Path(settings.MEDIA_ROOT) / 'beitraege' / 'cache'
    target = cache / f'{photo.token}-{variant}-{photo.fokus_y}.jpg'
    if not target.exists():
        cache.mkdir(parents=True, exist_ok=True)
        with photo.bild.open('rb') as handle:
            target.write_bytes(images.rendition(handle, variant, photo.fokus_y))
    return FileResponse(target.open('rb'), content_type='image/jpeg')
