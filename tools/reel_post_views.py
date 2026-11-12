"""Approve an Instagram post from the link in the morning reel reminder.

Like the rental approval links, the page needs no login: the signed token in
the URL is the permission and it expires after 36 hours. Opening the link only
shows the post; publishing needs the button (POST), because mail scanners open
links on their own and must not publish anything.
"""

from .models import ReelPost
from .reel_posts import approve_from_mail
from .reel_posts import post_from_token
from .reel_posts import public_video_url
from django.core.exceptions import ValidationError
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods


@require_http_methods(['GET', 'POST'])
def reel_post_approve(request, token: str):
    from .models import ToolsConfig
    from django.http import Http404
    if not ToolsConfig.get_config().is_instagram_configured():
        raise Http404()
    post = post_from_token(token)
    if post is None:
        return render(request, 'tools/reel_post_approve.html', {
            'state': 'invalid',
            'title': _('Invalid or expired link'),
            'message': _('This link is invalid or has expired. Approve the post in OK-Tools instead.'),
        }, status=400)

    link = getattr(post.license, 'mediathek_url', '') or ''
    context = {
        'post': post,
        'video_url': public_video_url(post.filename),
        'caption': post.caption.replace(
            '{mediathek}', link or _('[Mediathek link is added when publishing]')),
    }
    approvable = post.status in (ReelPost.STATUS_DRAFT, ReelPost.STATUS_FAILED)

    if request.method == 'POST' and approvable:
        try:
            approve_from_mail(post)
        except ValidationError as exc:
            context.update(state='error', title=_('The post cannot be published'),
                           message='; '.join(exc.messages))
            return render(request, 'tools/reel_post_approve.html', context, status=400)
        context.update(state='done', title=_('Approved'),
                       message=_('The reel is being published on Instagram now.'))
        return render(request, 'tools/reel_post_approve.html', context)

    if not approvable:
        context.update(state='done', title=_('Nothing to do'),
                       message=_('This post is already %(status)s.') % {
                           'status': post.get_status_display().lower()})
        return render(request, 'tools/reel_post_approve.html', context)

    context.update(state='confirm', title=_('Publish the reel on Instagram?'))
    return render(request, 'tools/reel_post_approve.html', context)
