"""Posts: one text with photos, published on Instagram, Facebook and the website.

A post is written once and belongs to a topic. The topic adds hashtags and a
signature per platform; every platform gets its own text, built from the
post and the topic, which staff may still change before approving. One
approval publishes the post on every platform switched on for it; each
platform keeps its own status, so a failure on one does not stop the others.
"""

from django.conf import settings
from django.db import models
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from pathlib import Path
import uuid


PLATFORM_INSTAGRAM = 'instagram'
PLATFORM_FACEBOOK = 'facebook'
PLATFORM_WEBSITE = 'website'
PLATFORM_CHOICES = [
    (PLATFORM_INSTAGRAM, _('Instagram')),
    (PLATFORM_FACEBOOK, _('Facebook')),
    (PLATFORM_WEBSITE, _('Website')),
]
# Pages list the platforms in this order, not alphabetically.
PLATFORM_ORDER = [code for code, _label in PLATFORM_CHOICES]


def in_platform_order(ziele) -> list:
    """Instagram, Facebook, website."""
    return sorted(ziele, key=lambda ziel: PLATFORM_ORDER.index(ziel.plattform))


def approve_all_q():
    """Users given "approve posts of every topic" explicitly (not superusers by default)."""
    from django.db.models import Q

    return Q(user_permissions__codename='freigeben_alle',
             user_permissions__content_type__app_label='beitraege') | Q(
        groups__permissions__codename='freigeben_alle',
        groups__permissions__content_type__app_label='beitraege')


def approves_all(user) -> bool:
    """True for people named as approvers of every topic (see :func:`approve_all_q`)."""
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(pk=user.pk).filter(approve_all_q()).exists()


def person_name(user) -> str:
    """First and last name from the profile; the mail address as a fallback."""
    if user is None:
        return '-'
    profile = getattr(user, 'profile', None)
    name = ' '.join(filter(None, [getattr(profile, 'first_name', ''), getattr(profile, 'last_name', '')]))
    return name.strip() or user.email or str(user)


class BeitragsConfig(models.Model):
    """Channel settings for posts (singleton)."""

    instagram_enabled = models.BooleanField(
        default=False,
        verbose_name=_('Publish on Instagram'),
        help_text=_('Uses the Instagram account and token of the Tools configuration.'),
    )
    facebook_enabled = models.BooleanField(
        default=False,
        verbose_name=_('Publish on Facebook'),
        help_text=_('Uses the Facebook page and token of the Tools configuration (Facebook Login).'),
    )
    website_enabled = models.BooleanField(
        default=False,
        verbose_name=_('Publish on the website'),
        help_text=_('WordPress website, through its REST API and an application password.'),
    )
    wordpress_url = models.URLField(
        blank=True,
        verbose_name=_('WordPress address'),
        help_text=_('Address of the website, e.g. https://www.example.de'),
    )
    wordpress_user = models.CharField(
        max_length=150, blank=True, verbose_name=_('WordPress user'),
        help_text=_('User with the right to publish posts.'),
    )
    wordpress_app_password = models.CharField(
        max_length=200, blank=True, verbose_name=_('WordPress application password'),
        help_text=_('Users → Profile → Application passwords in WordPress.'),
    )
    wordpress_comments = models.BooleanField(
        default=False,
        verbose_name=_('Allow comments on the website'),
        help_text=_('Off: posts are created with comments and pingbacks closed.'),
    )
    mail_enabled = models.BooleanField(
        default=False,
        verbose_name=_('Posts by mail'),
        help_text=_('Staff send a mail with text and photos to a mailbox; OK-Tools turns it into a post.'),
    )
    imap_host = models.CharField(max_length=200, blank=True, verbose_name=_('IMAP server'))
    imap_port = models.PositiveIntegerField(default=993, verbose_name=_('IMAP port'),
                                            help_text=_('993 for IMAP over SSL.'))
    imap_user = models.CharField(max_length=200, blank=True, verbose_name=_('IMAP user'))
    imap_password = models.CharField(max_length=200, blank=True, verbose_name=_('IMAP password'))
    imap_folder = models.CharField(max_length=100, default='INBOX', verbose_name=_('IMAP folder'))
    mail_address = models.EmailField(
        blank=True, verbose_name=_('Address for posts'),
        help_text=_('Shown to staff; mails to it are fetched from the IMAP mailbox above.'))
    mail_code = models.CharField(
        max_length=50, blank=True, verbose_name=_('Code in the subject'),
        help_text=_('Only mails whose subject contains this code are taken, e.g. "#okpost". The '
                    'sender alone is no proof: a sender address can be forged.'))
    approval_mail = models.BooleanField(
        default=True,
        verbose_name=_('Approval by mail'),
        help_text=_('Approvers get a mail with a link to check and approve the post on the phone.'),
    )

    class Meta:
        verbose_name = _('Post configuration')
        verbose_name_plural = _('Post configuration')

    def __str__(self):
        return str(_('Post configuration'))

    @classmethod
    def get_config(cls):
        """Return the singleton, creating it if needed."""
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    def is_website_configured(self) -> bool:
        return bool(self.website_enabled and self.wordpress_url and self.wordpress_user
                    and self.wordpress_app_password)

    def is_mail_configured(self) -> bool:
        return bool(self.mail_enabled and self.imap_host and self.imap_user and self.imap_password
                    and self.mail_code)

    @staticmethod
    def meta_config():
        """The Tools configuration holding the Meta account and token, or None."""
        from django.apps import apps

        if not apps.is_installed('tools'):
            return None
        from tools.models import ToolsConfig

        return ToolsConfig.get_config()

    def is_instagram_configured(self) -> bool:
        meta = self.meta_config()
        return bool(self.instagram_enabled and meta and meta.instagram_account_id
                    and meta.instagram_access_token)

    def is_facebook_configured(self) -> bool:
        meta = self.meta_config()
        return bool(self.facebook_enabled and meta and meta.facebook_page_id
                    and meta.instagram_access_token
                    and meta.instagram_api_host == 'graph.facebook.com')

    def configured_platforms(self) -> list[str]:
        """Platforms posts can be published on right now."""
        checks = [
            (PLATFORM_INSTAGRAM, self.is_instagram_configured()),
            (PLATFORM_FACEBOOK, self.is_facebook_configured()),
            (PLATFORM_WEBSITE, self.is_website_configured()),
        ]
        return [platform for platform, ready in checks if ready]

    PUBLISH_TASK_NAME = 'beitraege.tasks.publish_due_beitraege'
    MAIL_TASK_NAME = 'beitraege.tasks.fetch_mail_beitraege'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.sync_periodic_task()

    def sync_periodic_task(self) -> None:
        """Check for approved posts whose time has come every 5 minutes."""
        try:
            from django_celery_beat.models import IntervalSchedule
            from django_celery_beat.models import PeriodicTask
            import json

            every_5, _created = IntervalSchedule.objects.get_or_create(
                every=5, period=IntervalSchedule.MINUTES)
            PeriodicTask.objects.update_or_create(
                name=str(_('Posts: publish approved posts')),
                defaults={
                    'task': self.PUBLISH_TASK_NAME,
                    'interval': every_5,
                    'crontab': None,
                    'enabled': bool(self.configured_platforms()),
                    'kwargs': json.dumps({}),
                },
            )
            PeriodicTask.objects.update_or_create(
                name=str(_('Posts: fetch posts sent by mail')),
                defaults={
                    'task': self.MAIL_TASK_NAME,
                    'interval': every_5,
                    'crontab': None,
                    'enabled': self.is_mail_configured(),
                    'kwargs': json.dumps({}),
                },
            )
        except Exception:
            # The configuration must stay saveable during setup and migrations.
            return


class Thema(models.Model):
    """A topic of the channel; every post belongs to one."""

    name = models.CharField(max_length=100, unique=True, verbose_name=_('Name'))
    hashtags = models.CharField(
        max_length=300, blank=True, verbose_name=_('Hashtags'),
        help_text=_('Added to every post of this topic, e.g. "#Medienbildung #Merseburg".'),
    )
    signatur_instagram = models.TextField(
        blank=True, verbose_name=_('Signature on Instagram'),
        help_text=_('Last lines of every Instagram post of this topic.'))
    signatur_facebook = models.TextField(
        blank=True, verbose_name=_('Signature on Facebook'))
    signatur_website = models.TextField(
        blank=True, verbose_name=_('Signature on the website'))
    wordpress_categories = models.CharField(
        max_length=300, blank=True, verbose_name=_('WordPress categories'),
        help_text=_('Category names on the website, comma separated; missing ones are created.'),
    )
    wordpress_tags = models.CharField(
        max_length=300, blank=True, verbose_name=_('WordPress tags'),
        help_text=_('Tag names on the website, comma separated; missing ones are created.'),
    )
    instagram = models.BooleanField(default=True, verbose_name=_('Instagram by default'))
    facebook = models.BooleanField(default=True, verbose_name=_('Facebook by default'))
    website = models.BooleanField(default=True, verbose_name=_('Website by default'))
    freigeber = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='beitrag_themen',
        verbose_name=_('Approvers'),
        help_text=_('May approve posts of this topic. People with "approve all posts" may '
                    'approve every topic.'),
    )
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    position = models.PositiveSmallIntegerField(default=0, verbose_name=_('Order'))

    class Meta:
        verbose_name = _('Topic')
        verbose_name_plural = _('Topics')
        ordering = ['position', 'name']

    def __str__(self):
        return self.name


class Beitrag(models.Model):
    """A post: title, text and photos, published on the chosen platforms."""

    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_APPROVED = 'approved'
    STATUS_PUBLISHING = 'publishing'
    STATUS_PUBLISHED = 'published'
    STATUS_PARTIAL = 'partial'
    STATUS_FAILED = 'failed'
    STATUS_REJECTED = 'rejected'
    STATUS_WITHDRAWN = 'withdrawn'
    STATUS_CHOICES = [
        (STATUS_DRAFT, _('Draft')),
        (STATUS_SUBMITTED, pgettext_lazy('beitrag', 'Waiting for approval')),
        (STATUS_APPROVED, _('Approved')),
        (STATUS_PUBLISHING, _('Publishing')),
        (STATUS_PUBLISHED, _('Published')),
        (STATUS_PARTIAL, _('Partly published')),
        (STATUS_FAILED, _('Failed')),
        (STATUS_REJECTED, _('Rejected')),
        (STATUS_WITHDRAWN, _('Withdrawn')),
    ]
    MAX_PHOTOS = 10

    titel = models.CharField(max_length=200, verbose_name=_('Title'))
    text = models.TextField(verbose_name=_('Text'))
    link = models.URLField(blank=True, verbose_name=_('Link'),
                           help_text=_('E.g. the Mediathek; clickable on Facebook and the website.'))
    thema = models.ForeignKey(Thema, on_delete=models.PROTECT, related_name='beitraege',
                              verbose_name=_('Topic'))
    einwilligung = models.BooleanField(
        default=False, verbose_name=_('Consent of the people shown'),
        help_text=_('Everybody recognisable on the photos agreed to the publication.'))
    publish_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Publish at'),
        help_text=_('Empty: right after the approval.'))
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT,
                              db_index=True, verbose_name=_('Status'))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='+',
                                   verbose_name=_('Created by'))
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='+',
                                    verbose_name=_('Approved by'))
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Approved at'))
    rejection_note = models.TextField(blank=True, verbose_name=_('Reason for rejection'))
    mail_message_id = models.CharField(
        max_length=255, blank=True, default='', db_index=True, editable=False,
        help_text='Message-ID of the mail the post came from; a mail is never imported twice.')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = pgettext_lazy('beitrag', 'Post')
        verbose_name_plural = pgettext_lazy('beitrag', 'Posts')
        ordering = ['-created_at']
        permissions = [
            ('freigeben_alle', _('Can approve posts of every topic')),
        ]

    def __str__(self):
        return self.titel

    EDITABLE = (STATUS_DRAFT, STATUS_SUBMITTED, STATUS_REJECTED)
    # From the approval on, Instagram and Facebook may download the photos.
    PHOTOS_PUBLIC = (STATUS_APPROVED, STATUS_PUBLISHING, STATUS_PUBLISHED, STATUS_PARTIAL, STATUS_FAILED)

    def may_edit(self, user) -> bool:
        """Author and approvers, as long as the post is not approved yet."""
        if self.status not in self.EDITABLE or not getattr(user, 'is_authenticated', False):
            return False
        return self.created_by_id == user.pk or self.may_approve(user)

    def may_delete(self, user) -> bool:
        """The author, as long as the post is not approved yet."""
        return bool(self.status in self.EDITABLE and getattr(user, 'is_authenticated', False)
                    and self.created_by_id == user.pk)

    def may_withdraw(self, user) -> bool:
        """Approvers may take a published post off the platforms again."""
        return (self.status in (self.STATUS_PUBLISHED, self.STATUS_PARTIAL, self.STATUS_FAILED)
                and self.ziele.filter(status=BeitragZiel.STATUS_PUBLISHED).exists()
                and self.may_approve(user))

    def may_unapprove(self, user) -> bool:
        """An approved post that waits for its time may be held back."""
        return self.status == self.STATUS_APPROVED and self.may_approve(user)

    def may_approve(self, user) -> bool:
        """Approvers of the topic and people allowed to approve every topic."""
        if not getattr(user, 'is_authenticated', False) or not user.is_active:
            return False
        return bool(user.has_perm('beitraege.freigeben_alle')
                    or self.thema.freigeber.filter(pk=user.pk).exists())

    def approvers(self):
        """The approvers to tell (active users with a mail address).

        Only people named explicitly: approvers of the topic and those given
        "approve posts of every topic" (directly or by group). Superusers
        may approve too, but are not told unless they are named.
        """
        from django.contrib.auth import get_user_model
        from django.db.models import Q

        User = get_user_model()
        return User.objects.filter(is_active=True).filter(
            approve_all_q() | Q(beitrag_themen=self.thema)).exclude(email='').distinct()


def _foto_path(instance, filename):
    suffix = Path(filename).suffix.lower() or '.jpg'
    # A folder starting with a dot: web servers in front of /media/ do not
    # serve it (nginx: location ~ /\. deny), only Django does.
    return f'.beitraege/{instance.beitrag_id or "neu"}/{uuid.uuid4().hex}{suffix}'


class BeitragFoto(models.Model):
    """A photo of a post as uploaded; renditions are made when publishing."""

    beitrag = models.ForeignKey(Beitrag, on_delete=models.CASCADE, related_name='fotos',
                                verbose_name=pgettext_lazy('beitrag', 'Post'))
    bild = models.ImageField(upload_to=_foto_path, verbose_name=_('Photo'))
    position = models.PositiveSmallIntegerField(default=0, verbose_name=_('Order'))
    fokus_y = models.PositiveSmallIntegerField(
        default=50, verbose_name=_('Crop position (%)'),
        help_text=_('Where the 4:5 crop for Instagram sits: 0 top, 50 middle, 100 bottom.'))
    token = models.CharField(max_length=32, default='', blank=True, editable=False, db_index=True)

    class Meta:
        verbose_name = _('Photo')
        verbose_name_plural = _('Photos')
        ordering = ['position', 'id']

    def __str__(self):
        return Path(self.bild.name).name

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = uuid.uuid4().hex
        if self.bild and not getattr(self.bild, '_committed', True):
            # A new upload: keep it only as an upright JPEG without EXIF/GPS.
            from .services import images
            from django.core.files.base import ContentFile

            self.bild.file.seek(0)
            content = images.clean_original(self.bild.file)
            name = Path(self.bild.name).stem + '.jpg'
            self.bild.save(name, ContentFile(content), save=False)
        super().save(*args, **kwargs)


class BeitragZiel(models.Model):
    """One platform of a post: its text and its publishing state."""

    STATUS_OPEN = ''
    STATUS_PUBLISHING = 'publishing'
    STATUS_PUBLISHED = 'published'
    STATUS_FAILED = 'failed'
    STATUS_WITHDRAWN = 'withdrawn'
    STATUS_CHOICES = [
        (STATUS_OPEN, _('Open')),
        (STATUS_PUBLISHING, _('Publishing')),
        (STATUS_PUBLISHED, _('Published')),
        (STATUS_FAILED, _('Failed')),
        (STATUS_WITHDRAWN, _('Withdrawn')),
    ]

    beitrag = models.ForeignKey(Beitrag, on_delete=models.CASCADE, related_name='ziele',
                                verbose_name=pgettext_lazy('beitrag', 'Post'))
    plattform = models.CharField(max_length=12, choices=PLATFORM_CHOICES, verbose_name=_('Platform'))
    aktiv = models.BooleanField(default=True, verbose_name=_('Publish here'))
    text = models.TextField(blank=True, verbose_name=_('Text on this platform'),
                            help_text=_('Built from the post and its topic; may be changed.'))
    text_bearbeitet = models.BooleanField(default=False, editable=False)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_OPEN,
                              blank=True, verbose_name=_('Status'))
    remote_id = models.CharField(max_length=60, blank=True, verbose_name=_('ID on the platform'))
    permalink = models.URLField(blank=True, max_length=500, verbose_name=_('Link'))
    published_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Published at'))
    error = models.TextField(blank=True, verbose_name=_('Error'))

    class Meta:
        verbose_name = _('Platform')
        verbose_name_plural = _('Platforms')
        unique_together = [('beitrag', 'plattform')]
        ordering = ['beitrag', 'plattform']

    def __str__(self):
        return f'{self.beitrag} · {self.get_plattform_display()}'


@receiver(post_delete, sender=BeitragFoto)
def _delete_photo_files(sender, instance, **kwargs):
    """Remove the upload and its renditions once the photo row is gone."""
    name, storage, token = instance.bild.name, instance.bild.storage, instance.token

    def remove():
        if name:
            storage.delete(name)
        cache = Path(settings.MEDIA_ROOT) / '.beitraege' / 'cache'
        for rendition in cache.glob(f'{token}-*.jpg'):
            rendition.unlink(missing_ok=True)

    transaction.on_commit(remove)
