from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, gettext
from django_prometheus.models import ExportModelOperationsMixin


class UserManager(BaseUserManager):
    """Define a model manager for User model with no username field."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError(_('The given email must be set'))
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular User with the given email and password."""
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self._create_user(email, password, **extra_fields)


class OKUser(AbstractUser):
    """
    Model for a User.

    A User don't has a username and gets identified by his/her email
    address. Nevertheless the email is optional due to administrative
    reasons of the OKs.
    """

    # If a User specifies an email address it needs to be unique
    username = None
    email = models.EmailField(
        _('email address'), unique=True, null=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()

    staff_signature_svg = models.TextField(
        _('Staff signature SVG'),
        blank=True,
        null=True,
        help_text=_('SVG path data of the staff member\'s hand-drawn signature for Freistellung PDF.'),
    )
    staff_signature_points = models.JSONField(
        _('Staff signature points'),
        blank=True,
        null=True,
        default=None,
        help_text=_('Biometric stroke points for re-editing the signature on the canvas.'),
    )

    def __str__(self) -> str:
        """Represent OKUser by e-mail address."""
        return self.email

    class Meta:
        """Define the message IDs."""

        verbose_name = _('User')
        verbose_name_plural = _('Users')


class MediaAuthority(models.Model):
    """
    Model for a MediaAuthority.

    Every Profile belongs to a MediaAuthority. The default authority name of
    the default authority is defined in settings.py by OK_NAME_SHORT.
    """

    name = models.CharField(
        _('Media Authority'),
        default=settings.OK_NAME_SHORT,
        max_length=150,
        unique=True)
    
    full_name = models.CharField(
        _('Full Name'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Full name of the media authority (e.g., "Offener Kanal Dessau")'))

    target_channel = models.CharField(
        _('Target Channel'),
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text=_('Target channel identifier (e.g., "@ok_dessau@lokalmedial.de")'),
    )

    def __str__(self) -> str:
        """Represent a MediaAuthority by its name."""
        return self.name

    class Meta:
        """Define the message IDs."""

        verbose_name = _('Media Authority')
        verbose_name_plural = _('Media Authorities')


def default_media_authority():
    """Provide the default MediaAuthority."""
    return MediaAuthority.objects.get_or_create(
        name=settings.OK_NAME_SHORT)[0]


class Gender(models.TextChoices):
    """The gender of the user."""

    NOT_GIVEN = 'none', _('not given')
    MALE = 'm', _('male')
    FEMALE = 'f', _('female')
    DIVERSE = 'd', _('diverse')

    @classmethod
    def verbose_name(cls, value: str) -> str:
        """Return the verbose name to the given value."""
        for choice in cls.choices:
            if value == choice[0]:
                return choice[1]  # verbose name

        return ''


class Profile(ExportModelOperationsMixin('profile'), models.Model):
    """
    Model for a profil.

    A profil stores further informations about a user. Every profil
    belongs to a user.
    """

    okuser = models.OneToOneField(
        OKUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_('User'),
    )

    first_name = models.CharField(
        _('first name'), blank=False, null=True, max_length=150)
    last_name = models.CharField(
        _('last name'), blank=False, null=True, max_length=150)

    gender = models.CharField(
        _('gender'),
        max_length=4,
        choices=Gender.choices,
        default=Gender.NOT_GIVEN,
    )

    # phone number as char field due to missing support from zope.testbrowser
    # phone (optional)
    phone_number = models.CharField(
        _('phone number'), blank=True, null=True, max_length=30)
    # mobile (optional)
    mobile_number = models.CharField(
        _('mobile number'), blank=True, null=True, max_length=30)
    
    # ID document number
    ausweisnummer = models.CharField(
        _('ID document number'), blank=True, null=True, max_length=50,
        help_text=_('ID document number (passport, ID card, etc.)')
    )

    # birthday
    birthday = models.DateField(
        _('birthday'), blank=False, null=True)

    # address (street, zipcode, location) mandatory
    street = models.CharField(_('street'), null=True, max_length=95)
    house_number = models.CharField(
        _('house number'), null=True, max_length=20)
    zipcode = models.CharField(
        _('zipcode'), null=True, max_length=5)
    city = models.CharField(
        _('city'), null=True, max_length=35)

    # was the profile validated by an employee
    verified = models.BooleanField(
        _('verified'),
        default=False,
        help_text=_('The profile data was verified by showing the ID to an'
                    ' employee.')
    )

    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now,
        db_index=True,
    )

    media_authority = models.ForeignKey(
        MediaAuthority,
        on_delete=models.CASCADE,
        default=default_media_authority,
        verbose_name=_('Media Authority'),
    )

    member = models.BooleanField(
        _('member'),
        default=False,
        blank=False,
        null=False,
    )

    rental_only = models.BooleanField(
        _('rental only'),
        default=False,
        blank=False,
        null=False,
        help_text=_('The profile may only rent equipment. Mutually exclusive '
                    'with member: a profile is either a member or rental '
                    'only, never both.')
    )

    global_producer = models.BooleanField(
        _('Global Producer'),
        default=False,
        blank=False,
        null=False,
        help_text=_('Global producer status for the profile.')
    )

    comment = models.TextField(
        _('comment'),
        null=True,
        blank=True,
    )
    
    # Data sharing permissions
    phone_data_sharing_allowed = models.BooleanField(
        _('Phone data sharing allowed'),
        default=False,
        help_text=_('Permission to share phone number with third parties')
    )
    
    email_data_sharing_allowed = models.BooleanField(
        _('Email data sharing allowed'),
        default=False,
        help_text=_('Permission to share email address with third parties')
    )

    def __str__(self):
        """Represent Profile by first and last name."""
        return f'{self.first_name} {self.last_name}'

    def clean(self):
        """Reject profiles that are member and rental only at once."""
        super().clean()
        if self.member and self.rental_only:
            raise ValidationError({
                'rental_only': _(
                    'A profile is either a member or rental only, not both.'
                ),
            })

    class Meta:
        """Define the message IDs."""

        verbose_name = _('Profile')
        verbose_name_plural = _('Profiles')
        indexes = [
            models.Index(fields=['first_name', 'last_name'], name='profile_name_idx'),
            models.Index(fields=['ausweisnummer'], name='profile_ausweis_idx'),
        ]


class Notification(models.Model):
    """Model for system notifications that can be displayed to users."""

    NOTIFICATION_TYPES = [
        ('info', _('Information')),
        ('success', _('Success')),
        ('warning', _('Warning')),
        ('danger', _('Danger')),
    ]

    ICON_CHOICES = [
        ('info-circle', _('Info Circle')),
        ('check-circle', _('Check Circle')),
        ('exclamation-triangle', _('Exclamation Triangle')),
        ('exclamation-circle', _('Exclamation Circle')),
        ('clock', _('Clock')),
        ('bell', _('Bell')),
        ('broadcast', _('Broadcast')),
        ('star', _('Star')),
        ('gear', _('Gear')),
        ('shield-check', _('Shield Check')),
    ]

    title = models.CharField(
        _('Title'),
        max_length=200,
        help_text=_('Short title for the notification')
    )

    message = models.TextField(
        _('Message'),
        help_text=_('Main notification text')
    )

    notification_type = models.CharField(
        _('Type'),
        max_length=10,
        choices=NOTIFICATION_TYPES,
        default='info',
        help_text=_('Notification type determines color and style')
    )

    icon = models.CharField(
        _('Icon'),
        max_length=20,
        choices=ICON_CHOICES,
        default='info-circle',
        help_text=_('Bootstrap Icons icon name')
    )

    is_active = models.BooleanField(
        _('Active'),
        default=True,
        help_text=_('Only active notifications are displayed to users')
    )

    priority = models.IntegerField(
        _('Priority'),
        default=1,
        help_text=_('Higher priority notifications appear first (1-10)')
    )

    start_date = models.DateTimeField(
        _('Start Date'),
        default=timezone.now,
        help_text=_('When to start showing this notification')
    )

    end_date = models.DateTimeField(
        _('End Date'),
        null=True,
        blank=True,
        help_text=_('When to stop showing this notification (optional)')
    )

    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True
    )

    created_by = models.ForeignKey(
        OKUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Created By'),
        help_text=_('Admin who created this notification (auto-filled)')
    )

    def __str__(self):
        """Represent Notification by title."""
        return f"{self.title} ({self.get_notification_type_display()})"

    class Meta:
        """Define the message IDs."""

        verbose_name = _('Notification')
        verbose_name_plural = _('Notifications')
        ordering = ['-priority', '-created_at']

    def is_currently_active(self):
        """Check if notification should be displayed now."""
        now = timezone.now()
        if not self.is_active:
            return False
        if now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True


class RegistrationConfig(models.Model):
    """Configuration for registration module (singleton)."""
    
    # PDF template file for registration form (must be in files/ directory)
    # Options: Nutzerkartei.pdf, Nutzerkartei_Anmeldung_2022_n.pdf
    form_pdf = models.CharField(
        max_length=255,
        default='Nutzerkartei_Anmeldung_2022_n.pdf',
        verbose_name=_('Registration Form PDF'),
        help_text=_('PDF template file for registration form (must be in files/ directory)')
    )
    
    @staticmethod
    def get_available_pdf_files():
        """
        Get list of available PDF files from files/ directory.
        
        Returns:
            List of PDF filenames (without path), sorted alphabetically.
            Returns empty list if directory doesn't exist or is not accessible.
        """
        from django.conf import settings
        from pathlib import Path
        import logging
        
        logger = logging.getLogger(__name__)
        pdf_files = []
        
        try:
            files_dir = Path(settings.BASE_DIR) / 'files'
            
            if not files_dir.exists():
                logger.warning(f"Registration PDF files directory does not exist: {files_dir}")
                return pdf_files
            
            if not files_dir.is_dir():
                logger.warning(f"Registration PDF files path is not a directory: {files_dir}")
                return pdf_files
            
            for file_path in files_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() == '.pdf':
                    pdf_files.append(file_path.name)
            
            # Sort alphabetically
            pdf_files.sort()
            
        except Exception as e:
            logger.error(f"Error reading PDF files from files/ directory: {e}", exc_info=True)
        
        return pdf_files
    
    # Registration form type: PDF, HTML, or TEXT
    # PDF - generates filled PDF form using pdftk
    # HTML - generates HTML form (can be printed from browser)
    # TEXT - generates plain text form
    FORM_TYPE_CHOICES = [
        ('PDF', _('PDF')),
        ('HTML', _('HTML')),
        ('TEXT', _('TEXT')),
    ]
    form_type = models.CharField(
        max_length=10,
        choices=FORM_TYPE_CHOICES,
        default='PDF',
        verbose_name=_('Registration Form Type'),
        help_text=_('Type of registration form to generate')
    )
    
    class Meta:
        verbose_name = _('Registration Configuration')
        verbose_name_plural = _('Registration Configuration')
    
    def __str__(self):
        """Return string representation."""
        return str(_("Registration Configuration"))
    
    def save(self, *args, **kwargs):
        """Ensure only one config instance exists."""
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_config(cls):
        """Get the singleton config instance, create if doesn't exist."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class OrganizationConfig(models.Model):
    """Configuration for main organization (singleton)."""

    BUNDESLAND_CHOICES = [
        ('Baden-Württemberg', _('Baden-Württemberg')),
        ('Bayern', _('Bayern')),
        ('Berlin', _('Berlin')),
        ('Brandenburg', _('Brandenburg')),
        ('Bremen', _('Bremen')),
        ('Hamburg', _('Hamburg')),
        ('Hessen', _('Hessen')),
        ('Mecklenburg-Vorpommern', _('Mecklenburg-Vorpommern')),
        ('Niedersachsen', _('Niedersachsen')),
        ('Nordrhein-Westfalen', _('Nordrhein-Westfalen')),
        ('Rheinland-Pfalz', _('Rheinland-Pfalz')),
        ('Saarland', _('Saarland')),
        ('Sachsen', _('Sachsen')),
        ('Sachsen-Anhalt', _('Sachsen-Anhalt')),
        ('Schleswig-Holstein', _('Schleswig-Holstein')),
        ('Thüringen', _('Thüringen')),
    ]

    BUNDESLAND_CODE_CHOICES = [
        ('BW', 'BW'),
        ('BY', 'BY'),
        ('BE', 'BE'),
        ('BB', 'BB'),
        ('HB', 'HB'),
        ('HH', 'HH'),
        ('HE', 'HE'),
        ('MV', 'MV'),
        ('NI', 'NI'),
        ('NW', 'NW'),
        ('RP', 'RP'),
        ('SL', 'SL'),
        ('SN', 'SN'),
        ('ST', 'ST'),
        ('SH', 'SH'),
        ('TH', 'TH'),
    ]

    BUNDESLAND_TO_CODE = dict(zip(
        [choice[0] for choice in BUNDESLAND_CHOICES],
        [choice[0] for choice in BUNDESLAND_CODE_CHOICES],
    ))
    
    # Basic organization info
    name = models.CharField(
        max_length=255,
        default='Open Channel Merseburg-Querfurt e.V.',
        verbose_name=_('Organization Name'),
        help_text=_('Full name of the organization')
    )
    
    short_name = models.CharField(
        max_length=150,
        default='OK Merseburg',
        verbose_name=_('Short Name'),
        help_text=_('Short name of the organization')
    )
    
    # Contact information
    website = models.URLField(
        max_length=255,
        blank=True,
        verbose_name=_('Website'),
        help_text=_('Organization website URL')
    )
    
    email = models.EmailField(
        max_length=255,
        blank=True,
        verbose_name=_('Email'),
        help_text=_('Contact email address')
    )
    
    phone = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Phone'),
        help_text=_('Contact phone number')
    )
    
    fax = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Fax'),
        help_text=_('Fax number')
    )
    
    address = models.TextField(
        blank=True,
        verbose_name=_('Address'),
        help_text=_('Organization address (multiline)')
    )
    
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Welcome message or organization description')
    )

    logo_large = models.FileField(
        blank=True,
        null=True,
        upload_to='organization/logos/',
        verbose_name=_('Large logo'),
        help_text=_('Large logo displayed in the expanded sidebar')
    )

    logo_small = models.FileField(
        blank=True,
        null=True,
        upload_to='organization/logos/',
        verbose_name=_('Small logo'),
        help_text=_('Square logo or SVG displayed in the collapsed sidebar')
    )
    
    opening_hours = models.TextField(
        blank=True,
        verbose_name=_('Opening Hours'),
        help_text=_('Opening hours (multiline)')
    )
    
    # Regulatory and ownership
    state_media_institution = models.CharField(
        max_length=50,
        default='MSA',
        verbose_name=_('State Media Institution'),
        help_text=_('Regulatory institution code (MSA, LFK, BLM, etc.)')
    )
    
    organization_owner = models.CharField(
        max_length=150,
        default='OKMQ',
        verbose_name=_('Organization Owner'),
        help_text=_('Owner/operator identifier (matches MediaAuthority name)')
    )

    bundesland = models.CharField(
        max_length=64,
        choices=BUNDESLAND_CHOICES,
        default='Sachsen-Anhalt',
        verbose_name=_('Bundesland'),
        help_text=_('German federal state written to exchange metadata; code is generated automatically')
    )

    bundesland_code = models.CharField(
        max_length=2,
        choices=BUNDESLAND_CODE_CHOICES,
        default='ST',
        verbose_name=_('Bundesland Code'),
        help_text=_('Two-letter federal state code written to exchange metadata')
    )
    
    # Broadcasting schedule
    broadcast_start = models.TimeField(
        default='06:00',
        verbose_name=_('Broadcast Start Time'),
        help_text=_('Default broadcast start time')
    )
    
    broadcast_end = models.TimeField(
        default='23:00',
        verbose_name=_('Broadcast End Time'),
        help_text=_('Default broadcast end time')
    )
    
    # Integration
    media_authority = models.ForeignKey(
        MediaAuthority,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='organization_configs',
        verbose_name=_('Own Media Authority'),
        help_text=_(
            'Which "Offener Kanal" this installation is. Used to tell own '
            'productions from material of other channels.'),
    )

    peertube_channel = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('PeerTube Channel'),
        help_text=_('PeerTube channel identifier')
    )
    
    # Legal texts (for future use)
    datenschutz = models.TextField(
        blank=True,
        verbose_name=_('Privacy Policy (Datenschutz)'),
        help_text=_('Privacy policy text')
    )
    
    impressum = models.TextField(
        blank=True,
        verbose_name=_('Imprint (Impressum)'),
        help_text=_('Legal imprint text')
    )
    
    agb = models.TextField(
        blank=True,
        verbose_name=_('Terms and Conditions (AGB)'),
        help_text=_('Terms and conditions text')
    )
    
    class Meta:
        verbose_name = _('Organization Configuration')
        verbose_name_plural = _('Organization Configuration')
    
    def __str__(self):
        """Return string representation."""
        return str(_("Organization Configuration"))

    def clean(self):
        super().clean()
        expected_code = self.BUNDESLAND_TO_CODE.get(self.bundesland)
        if expected_code:
            self.bundesland_code = expected_code
    
    def save(self, *args, **kwargs):
        """Ensure only one config instance exists."""
        expected_code = self.BUNDESLAND_TO_CODE.get(self.bundesland)
        if expected_code:
            self.bundesland_code = expected_code
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_config(cls):
        """Get the singleton config instance, create if doesn't exist."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
