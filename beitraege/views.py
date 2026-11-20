"""Mobile pages: write, edit, check and approve a post; photos for Meta.

None of these pages lives below /admin, which a channel may only open from
its office network: staff on the road log in at /profile/login/.

- "Neuer Beitrag" needs a login and the right to add posts.
- "Meine Beiträge" lists the own posts and those waiting for the approver.
- "Bearbeiten": the author and the approvers change a post until it is
  approved; approvers also the text per platform and the crop of a photo.
- The check page opens for approvers (logged in, or from the personal link
  in the approval mail) and read-only for the author. Opening only shows
  the post; approving needs the button (POST), because mail scanners open
  links on their own.
- Photo renditions: public under their token once the post is approved
  (Instagram and Facebook download them), before that only with a signed
  preview link.
"""

from . import workflow
from .forms import BeitragForm
from .links import preview_allowed
from .links import previews
from .models import Beitrag
from .models import BeitragFoto
from .models import in_platform_order
from .models import person_name
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
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_http_methods
from pathlib import Path


CROP_CHOICES = [(0, gettext_lazy('top')), (25, '25 %'), (50, gettext_lazy('middle')),
                (75, '75 %'), (100, gettext_lazy('bottom'))]


def _works_with_posts(user) -> bool:
    """Staff who write or approve posts."""
    return bool(user.has_perm('beitraege.add_beitrag') or user.has_perm('beitraege.freigeben_alle')
                or user.beitrag_themen.exists())


@login_required
@permission_required('beitraege.add_beitrag', raise_exception=True)
@require_http_methods(['GET', 'POST'])
def neu(request):
    form = BeitragForm(request.POST or None, request.FILES or None)
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
def meine(request):
    """The own posts and, for approvers, the posts waiting for them."""
    from django.db.models import Q

    if not _works_with_posts(request.user):
        raise PermissionDenied
    own = Beitrag.objects.filter(created_by=request.user).select_related('thema')[:30]
    waiting = []
    submitted = Beitrag.objects.filter(status=Beitrag.STATUS_SUBMITTED).select_related('thema', 'created_by')
    if not request.user.has_perm('beitraege.freigeben_alle'):
        submitted = submitted.filter(Q(thema__freigeber=request.user))
    for beitrag in submitted.distinct().order_by('created_at'):
        beitrag.autor_name = person_name(beitrag.created_by)
        waiting.append(beitrag)
    return render(request, 'beitraege/meine.html', {
        'title': _('My posts'),
        'own': own,
        'waiting': waiting,
        'may_write': request.user.has_perm('beitraege.add_beitrag'),
    })


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
def bearbeiten(request, pk):
    beitrag = get_object_or_404(Beitrag.objects.select_related('thema'), pk=pk)
    if not beitrag.may_edit(request.user):
        raise PermissionDenied
    is_approver = beitrag.may_approve(request.user)
    fotos = list(beitrag.fotos.all())
    ziele = in_platform_order(beitrag.ziele.all())
    initial = {
        'thema': beitrag.thema, 'titel': beitrag.titel, 'text': beitrag.text, 'link': beitrag.link,
        'einwilligung': beitrag.einwilligung, 'publish_at': beitrag.publish_at,
        'plattformen': [z.plattform for z in ziele if z.aktiv],
    }
    form = BeitragForm(request.POST or None, request.FILES or None, initial=initial,
                       existing_photos=len(fotos))
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        remove = {f.pk for f in fotos if request.POST.get(f'entfernen_{f.pk}')}
        kept = [f for f in fotos if f.pk not in remove]
        if len(kept) + len(data['fotos']) > Beitrag.MAX_PHOTOS:
            form.add_error('fotos', _('At most %(max)s photos.') % {'max': Beitrag.MAX_PHOTOS})
        elif (kept or data['fotos']) and not data['einwilligung']:
            form.add_error('einwilligung', _('Confirm the consent before sending photos.'))
        else:
            with transaction.atomic():
                for field in ('thema', 'titel', 'text', 'einwilligung', 'publish_at'):
                    setattr(beitrag, field, data[field])
                beitrag.link = data['link'] or ''
                beitrag.save()
                BeitragFoto.objects.filter(beitrag=beitrag, pk__in=remove).delete()
                for foto in kept:
                    value = request.POST.get(f'fokus_{foto.pk}')
                    if value is not None and value.isdigit() and int(value) != foto.fokus_y:
                        foto.fokus_y = max(0, min(100, int(value)))
                        foto.save(update_fields=['fokus_y'])
                start = max([f.position for f in kept], default=-1) + 1
                for offset, upload in enumerate(data['fotos']):
                    BeitragFoto.objects.create(beitrag=beitrag, bild=upload, position=start + offset)
                if is_approver:
                    for ziel in beitrag.ziele.all():
                        text = request.POST.get(f'text_{ziel.plattform}')
                        if text is not None and text.strip() != ziel.text.strip():
                            ziel.text = text.strip()
                            workflow.mark_edited(ziel)
                            ziel.save()
                workflow.ensure_ziele(beitrag, platforms=data['plattformen'])
                resubmit = beitrag.status in (Beitrag.STATUS_DRAFT, Beitrag.STATUS_REJECTED)
                if resubmit:
                    workflow.submit(beitrag)
            if resubmit and not is_approver:
                return redirect('beitraege:eingereicht', pk=beitrag.pk)
            return redirect('beitraege:pruefen', pk=beitrag.pk)
    return render(request, 'beitraege/bearbeiten.html', {
        'title': _('Edit post'),
        'beitrag': beitrag,
        'form': form,
        'fotos': previews(fotos),
        'crop_choices': CROP_CHOICES,
        'ziele': ziele if is_approver else [],
        'resubmit': beitrag.status in (Beitrag.STATUS_DRAFT, Beitrag.STATUS_REJECTED),
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
    context = {
        'beitrag': beitrag,
        'ziele': in_platform_order(beitrag.ziele.filter(aktiv=True)),
        'autor': person_name(beitrag.created_by),
        'fotos': previews(beitrag.fotos.all()),
        'may_edit': beitrag.may_edit(request.user),
    }
    if not beitrag.may_approve(user):
        # The author may look at the own post (status, links), not approve it.
        if beitrag.created_by_id is None or beitrag.created_by_id != getattr(user, 'pk', None):
            raise PermissionDenied
        context.update(state='view', title=beitrag.get_status_display(),
                       message=beitrag.rejection_note if beitrag.status == Beitrag.STATUS_REJECTED else '')
        return render(request, 'beitraege/pruefen.html', context)
    context.update(problems=workflow.problems(beitrag), approver=user)
    open_states = Beitrag.EDITABLE
    if request.method == 'POST' and beitrag.status in open_states:
        if request.POST.get('aktion') == 'ablehnen':
            workflow.reject(beitrag, user, request.POST.get('grund', '').strip())
            context.update(state='done', title=_('Sent back'),
                           message=_('The author has been told.'), may_edit=False)
            return render(request, 'beitraege/pruefen.html', context)
        try:
            workflow.approve(beitrag, user)
        except ValidationError as exc:
            context.update(state='error', title=_('The post cannot be approved'),
                           message='; '.join(exc.messages))
            return render(request, 'beitraege/pruefen.html', context, status=400)
        context.update(state='done', may_edit=False, title=_('Approved'), message=(
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
    """A JPEG rendition of a photo, made once and kept out of the public media."""
    if variant not in images.VARIANTS:
        raise Http404()
    photo = BeitragFoto.objects.select_related('beitrag').filter(token=token).first()
    if photo is None:
        raise Http404()
    if photo.beitrag.status not in Beitrag.PHOTOS_PUBLIC and not preview_allowed(photo, request.GET.get('s')):
        raise Http404()
    cache = Path(settings.MEDIA_ROOT) / '.beitraege' / 'cache'
    target = cache / f'{photo.token}-{variant}-{photo.fokus_y}.jpg'
    if not target.exists():
        cache.mkdir(parents=True, exist_ok=True)
        with photo.bild.open('rb') as handle:
            target.write_bytes(images.rendition(handle, variant, photo.fokus_y))
    response = FileResponse(target.open('rb'), content_type='image/jpeg')
    response['Cache-Control'] = 'private, max-age=3600'
    return response
