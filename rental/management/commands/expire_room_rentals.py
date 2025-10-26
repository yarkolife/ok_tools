from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rental.models import RentalRequest
from rental.models import RentalTransaction
from rental.models import RoomRental
import logging


logger = logging.getLogger(__name__)
OKUser = get_user_model()


class Command(BaseCommand):
    """Management command to expire room rentals and generate transactions."""

    help = _('Automatically expire room rentals and create corresponding transactions.')

    def add_arguments(self, parser):
        """Register command-line arguments."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help=_('Show what would be done without applying changes'),
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help=_('Verbose output'),
        )

    def handle(self, *args, **options):
        """Execute command logic to expire reservations and rentals."""
        dry_run = options['dry_run']
        verbose = options['verbose']

        self.stdout.write(
            self.style.SUCCESS('🚀 Starting automatic expiration of expired room rentals...')
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('⚠️  TEST MODE - changes will not be applied')
            )

        # Find all active room rentals that have expired
        now = timezone.now()
        expired_rentals = []

        # Get all active room rentals
        active_room_rentals = RoomRental.objects.filter(
            rental_request__status__in=['reserved', 'issued']
        ).select_related('rental_request', 'room')

        for room_rental in active_room_rentals:
            if room_rental.is_expired:
                expired_rentals.append(room_rental)

        if not expired_rentals:
            self.stdout.write(
                self.style.SUCCESS('✅ No expired room rentals found')
            )
            return

        self.stdout.write(
            _('📊 Found {} expired room rentals').format(len(expired_rentals))
        )

        # Group by status for better display
        reserved_expired = [r for r in expired_rentals if r.rental_request.status == 'reserved']
        issued_expired = [r for r in expired_rentals if r.rental_request.status == 'issued']

        if reserved_expired:
            self.stdout.write(
                _('🔴 {} expired room reservations (will be auto-returned)').format(len(reserved_expired))
            )

        if issued_expired:
            self.stdout.write(
                _('🟡 {} expired room rentals (will be returned)').format(len(issued_expired))
            )

        if verbose:
            self.stdout.write(_('📋 Details of expired rentals:'))
            for rental in expired_rentals:
                status = 'RESERVED' if rental.rental_request.status == 'reserved' else 'ISSUED'
                self.stdout.write(
                    _('  • {} - {} '
                      '({}) - Expired: {}').format(
                        rental.room.name,
                        rental.rental_request.project_name,
                        status,
                        rental.rental_request.requested_end_date.strftime("%d.%m.%Y %H:%M")
                    )
                )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(_('\n⚠️  In test mode, changes are not applied'))
            )
            return

        # Apply changes
        self.stdout.write(_('\n🔄 Applying changes...'))

        try:
            with transaction.atomic():
                processed_count = 0

                for room_rental in expired_rentals:
                    rental_request = room_rental.rental_request

                    if rental_request.status == 'reserved':
                        # For room reservations: create return transaction (auto-return)
                        RentalTransaction.objects.create(
                            room=room_rental.room,
                            transaction_type='return',
                            quantity=1,  # Room = 1 unit
                            notes=_('Automatic return of expired room reservation: {}').format(room_rental.room.name),
                            performed_by=OKUser.objects.filter(is_superuser=True).first()
                        )

                        # Update request status to returned (not cancelled)
                        rental_request.status = 'returned'
                        rental_request.actual_end_date = now
                        rental_request.save()

                        if verbose:
                            self.stdout.write(
                                f'  ✅ Auto-returned room reservation: {room_rental.room.name}'
                            )

                    elif rental_request.status == 'issued':
                        # For rentals: create return transaction
                        RentalTransaction.objects.create(
                            room=room_rental.room,
                            transaction_type='return',
                            quantity=1,  # Room = 1 unit
                            notes=_('Automatic return of expired room rental: {}').format(room_rental.room.name),
                            performed_by=OKUser.objects.filter(is_superuser=True).first()
                        )

                        # Update request status and return date
                        rental_request.status = 'returned'
                        rental_request.actual_end_date = now
                        rental_request.save()

                        if verbose:
                            self.stdout.write(
                                f'  ✅ Returned room: {room_rental.room.name}'
                            )

                    processed_count += 1

                self.stdout.write(
                    self.style.SUCCESS(_('\n✅ Successfully processed {} expired room rentals').format(processed_count))
                )

                # Log result
                logger.info(
                    _('Automatic expiration of expired room rentals: '
                      'processed {} rentals, '
                      'auto-returned reservations: {}, '
                      'returned rentals: {}').format(
                        processed_count,
                        len(reserved_expired),
                        len(issued_expired)
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ Error during processing: {str(e)}')
            )
            logger.error(_('Error during automatic expiration of expired room rentals: {}').format(str(e)))
            raise

        self.stdout.write(
            self.style.SUCCESS(_('\n🎉 Automatic expiration of expired room rentals completed!'))
        )
