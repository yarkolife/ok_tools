from .disa_import import validate
from datetime import datetime
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from licenses.models import License


class ContributionManager(models.Manager):
    """Provide methods to determine primary contributions."""

    # Set of all licenses of the given contributions
    licenses = {}
    # Mapping each license id to a list of belonging contributions.
    # The list of contributions is sorted by broadcast_date
    contr_by_license = {}

    def _set_up(self, contributions):
        """Initialize self.licensees and self.contr_by_license."""
        self.licenses = {c.license for c in contributions}
        self.contr_by_license = {}
        # TODO only iterate through contributions once for better performence
        for license in self.licenses:
            self.contr_by_license[license.id] = sorted(
                [c for c in contributions if c.license == license],
                key=lambda c: c.broadcast_date)

    def primary_contributions(self, contributions):
        """
        Return a list of ids belonging to all primary contributions.

        Base of the search are the given contributions.
        """
        self._set_up(contributions)
        return [c.id for c in contributions
                if c == self.contr_by_license[c.license.id][0]]

    def repetitions(self, contributions):
        """
        Return a list of ids belonging to all repetitions.

        Base of the search are the given contributions.
        """
        self._set_up(contributions)
        return [c.id for c in contributions
                if c != self.contr_by_license[c.license.id][0]]


class Contribution(models.Model):
    """
    Model representing a contribution.

    Each Contribution belongs to a license
    """

    license = models.ForeignKey(
        License,
        on_delete=models.CASCADE,
        verbose_name=_('License'),
        blank=False,
        null=False,
    )

    broadcast_date = models.DateTimeField(  # datetime
        _('Broadcast Date'),
        blank=False,
        null=False,
    )

    live = models.BooleanField(
        _('Is live'),
        blank=False,
        null=False,
    )

    def is_primary(self) -> bool:
        """Determine weather the contribution is primary."""
        contributions = (self.__class__.objects
                         .filter(license=self.license)
                         .order_by('broadcast_date'))

        return self.broadcast_date == contributions[0].broadcast_date

    def __str__(self) -> str:
        """Represent a contribution by its title and subtitle."""
        return str(self.license)

    class Meta:
        """Defines the message IDs."""

        verbose_name = _('Contribution')
        verbose_name_plural = _('Contributions')


class DisaImport(models.Model):
    """
    Model representing the DISA-Import.

    The Contributions get imported from a xlsx-file.
    """

    def timestamp_path(instance, filename):
        """Create a path based on the current timestamp."""
        now: datetime = datetime.now()
        return (f'{now.year}/{now.month}/{now.day}/{now.hour}-{now.minute}-'
                f'{now.second}-{now.microsecond}.xlsx')

    file = models.FileField(
        verbose_name=_('DISA export file'),
        upload_to=timestamp_path,
        validators=[
            FileExtensionValidator(allowed_extensions=['xlsx']),
        ],
        blank=False,
        null=False,
    )

    imported = models.BooleanField(
        _('Imported'),
        default=False,
        blank=False,
        null=False,
        help_text=_('Just marking the file as imported does not import'
                    ' the file!')
    )

    def clean(self) -> None:
        """Validate the uploaded file."""
        validate(self.file)
        return super().clean()

    def __str__(self) -> str:
        """Represent DISA import as its file name."""
        return str(self.file.name)

    class Meta:
        """Defines the message IDs."""

        verbose_name = _('DISA-Import')
        verbose_name_plural = _('DISA-Imports')
