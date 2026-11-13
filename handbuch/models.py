"""Notes the staff add to a chapter of the manual.

The chapters themselves are templates in the code, so they are updated with
every release. What only one channel needs to know ("the label printer is in
office 2") is written here, below the chapter, and survives updates.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class HandbuchNotiz(models.Model):
    """A note below one chapter of the manual."""

    kapitel = models.CharField(
        max_length=80,
        db_index=True,
        verbose_name=_('Chapter'),
    )
    text = models.TextField(verbose_name=_('Note'))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('Written by'),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Written at'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Changed at'))

    class Meta:
        verbose_name = _('Manual note')
        verbose_name_plural = _('Manual notes')
        ordering = ['kapitel', 'created_at']

    def __str__(self):
        return f'{self.kapitel}: {self.text[:60]}'
