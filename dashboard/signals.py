from .models import UserJourney
from .models import UserJourneyStage
from .utils import AlertManager
from .utils import FunnelTracker
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from registration.models import OKUser
from registration.models import Profile
import logging

# Import models only if modules are enabled
try:
    from contributions.models import Contribution
    CONTRIBUTIONS_AVAILABLE = True
except (ImportError, RuntimeError, ModuleNotFoundError):
    CONTRIBUTIONS_AVAILABLE = False
    Contribution = None

try:
    from licenses.models import License
    LICENSES_AVAILABLE = True
except (ImportError, RuntimeError, ModuleNotFoundError):
    LICENSES_AVAILABLE = False
    License = None

try:
    from rental.models import RentalRequest
    RENTAL_AVAILABLE = True
except (ImportError, RuntimeError, ModuleNotFoundError):
    RENTAL_AVAILABLE = False
    RentalRequest = None


logger = logging.getLogger(__name__)


@receiver(post_save, sender=OKUser)
def track_user_registration(sender, instance, created, **kwargs):
    """Track when a user registers."""
    if created:
        try:
            tracker = FunnelTracker()
            tracker.track_user_stage(
                instance,
                UserJourneyStage.REGISTERED,
                metadata={'source': 'user_registration'}
            )
            logger.info(f"Tracked user registration: {instance.email}")
        except Exception as e:
            logger.error(f"Error tracking user registration: {e}")


@receiver(post_save, sender=Profile)
def track_user_verification(sender, instance, **kwargs):
    """Track when a user profile is verified."""
    if instance.verified and instance.okuser:
        try:
            tracker = FunnelTracker()
            tracker.track_user_stage(
                instance.okuser,
                UserJourneyStage.VERIFIED,
                metadata={'source': 'profile_verification'}
            )
            logger.info(f"Tracked user verification: {instance.okuser.email}")
        except Exception as e:
            logger.error(f"Error tracking user verification: {e}")


# Rental signals - only register if rental module is available
def track_rental_request(sender, instance, created, **kwargs):
    """Track when a user requests equipment rental."""
    if created:
        try:
            tracker = FunnelTracker()
            tracker.track_user_stage(
                instance.user,
                UserJourneyStage.RENTAL_REQUESTED,
                rental_request_id=instance.id,
                metadata={'source': 'rental_request'}
            )
            logger.info(f"Tracked rental request: {instance.user.email}")
        except Exception as e:
            logger.error(f"Error tracking rental request: {e}")


def track_rental_completion(sender, instance, **kwargs):
    """Track when a rental is completed."""
    if instance.status == 'returned' and instance.actual_end_date:
        try:
            tracker = FunnelTracker()
            tracker.track_user_stage(
                instance.user,
                UserJourneyStage.RENTAL_COMPLETED,
                rental_request_id=instance.id,
                metadata={'source': 'rental_completion'}
            )
            logger.info(f"Tracked rental completion: {instance.user.email}")
        except Exception as e:
            logger.error(f"Error tracking rental completion: {e}")


# Register rental signals only if available
if RENTAL_AVAILABLE and RentalRequest is not None:
    post_save.connect(track_rental_request, sender=RentalRequest)
    post_save.connect(track_rental_completion, sender=RentalRequest)


# License signals - only register if licenses module is available
def track_license_creation(sender, instance, created, **kwargs):
    """Track when a user creates a license."""
    if created and instance.profile and instance.profile.okuser:
        try:
            tracker = FunnelTracker()
            tracker.track_user_stage(
                instance.profile.okuser,
                UserJourneyStage.LICENSE_CREATED,
                license_id=instance.id,
                metadata={'source': 'license_creation'}
            )
            logger.info(f"Tracked license creation: {instance.profile.okuser.email}")
        except Exception as e:
            logger.error(f"Error tracking license creation: {e}")


# Register license signals only if available
if LICENSES_AVAILABLE and License is not None:
    post_save.connect(track_license_creation, sender=License)


# Contribution signals - only register if contributions module is available
def track_contribution_creation(sender, instance, created, **kwargs):
    """Track when a contribution is created."""
    if created and instance.license and instance.license.profile and instance.license.profile.okuser:
        try:
            tracker = FunnelTracker()
            tracker.track_user_stage(
                instance.license.profile.okuser,
                UserJourneyStage.CONTRIBUTION_CREATED,
                contribution_id=instance.id,
                metadata={'source': 'contribution_creation'}
            )

            # Check if this is the user's first broadcast
            user_contributions = Contribution.objects.filter(
                license__profile__okuser=instance.license.profile.okuser
            ).order_by('broadcast_date')

            if user_contributions.count() == 1:
                # First broadcast
                tracker.track_user_stage(
                    instance.license.profile.okuser,
                    UserJourneyStage.FIRST_BROADCAST,
                    contribution_id=instance.id,
                    metadata={'source': 'first_broadcast'}
                )
                logger.info(f"Tracked first broadcast: {instance.license.profile.okuser.email}")
            elif user_contributions.count() > 1:
                # Multiple broadcasts
                tracker.track_user_stage(
                    instance.license.profile.okuser,
                    UserJourneyStage.MULTIPLE_BROADCASTS,
                    contribution_id=instance.id,
                    metadata={'source': 'multiple_broadcasts'}
                )
                logger.info(f"Tracked multiple broadcasts: {instance.license.profile.okuser.email}")

        except Exception as e:
            logger.error(f"Error tracking contribution creation: {e}")


def check_daily_alerts(sender, instance, **kwargs):
    """Check alerts after contribution creation."""
    try:
        # Only check once per day to avoid spam
        from django.core.cache import cache
        cache_key = f"daily_alert_check_{timezone.now().date()}"

        if not cache.get(cache_key):
            # Run alert check
            tracker = FunnelTracker()
            end_date = timezone.now().date()
            start_date = end_date - timezone.timedelta(days=1)

            metrics = tracker.get_funnel_metrics(start_date, end_date)

            alert_manager = AlertManager()
            triggered_alerts = alert_manager.check_thresholds(metrics)

            if triggered_alerts:
                logger.warning(f"Triggered {len(triggered_alerts)} alerts")

            # Cache for 24 hours
            cache.set(cache_key, True, 86400)

    except Exception as e:
        logger.error(f"Error checking daily alerts: {e}")


# Register contribution signals only if available
if CONTRIBUTIONS_AVAILABLE and Contribution is not None:
    post_save.connect(track_contribution_creation, sender=Contribution)
    post_save.connect(check_daily_alerts, sender=Contribution)
