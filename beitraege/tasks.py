"""Celery tasks for posts."""

from celery import shared_task


@shared_task(name='beitraege.tasks.publish_due_beitraege')
def publish_due_beitraege():
    """Start every approved post whose time has come (every 5 minutes)."""
    from .workflow import due_posts

    started = 0
    for beitrag_id in due_posts().values_list('pk', flat=True):
        publish_beitrag.delay(beitrag_id)
        started += 1
    return {'started': started}


@shared_task(name='beitraege.tasks.publish_beitrag')
def publish_beitrag(beitrag_id):
    """Publish one approved post on its platforms."""
    from .workflow import claim
    from .workflow import publish

    beitrag = claim(beitrag_id)
    if beitrag is None:
        return {'status': 'skipped'}
    return {'status': publish(beitrag)}


@shared_task(name='beitraege.tasks.fetch_mail_beitraege')
def fetch_mail_beitraege():
    """Read the posts mailbox (every 5 minutes)."""
    from .mailin import fetch

    return fetch()
