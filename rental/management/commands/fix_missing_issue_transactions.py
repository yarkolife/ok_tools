"""
Management command to create missing issue transactions for rental items.

This command finds rental items that are in 'issued' or 'returned' status
but don't have corresponding 'issue' transactions, and creates them.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rental.models import RentalItem
from rental.models import RentalRequest
from rental.models import RentalTransaction
from rental.services import RentalService
import logging


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Management command to create missing issue transactions."""

    help = _('Create missing issue transactions for rental items.')

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
        """Execute command logic to create missing issue transactions."""
        dry_run = options['dry_run']
        verbose = options['verbose']

        self.stdout.write(
            self.style.SUCCESS('🚀 Starting fix of missing issue transactions...')
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('⚠️  TEST MODE - changes will not be applied')
            )

        # Find rentals in 'issued' or 'returned' status
        rentals = RentalRequest.objects.filter(
            status__in=['issued', 'returned']
        ).prefetch_related('items')

        items_to_fix = []

        for rental in rentals:
            for item in rental.items.all():
                # Check if issue transaction exists
                has_issue = RentalTransaction.objects.filter(
                    rental_item=item,
                    transaction_type='issue'
                ).exists()

                # Check if return transaction exists (indicates item was issued)
                has_return = RentalTransaction.objects.filter(
                    rental_item=item,
                    transaction_type='return'
                ).exists()

                # Determine if we should create issue transaction
                should_create = False
                reason = ''

                if rental.status == 'issued' and item.quantity_requested > 0 and not has_issue:
                    should_create = True
                    reason = 'Rental is issued but no issue transaction exists'
                elif rental.status == 'returned' and has_return and not has_issue:
                    should_create = True
                    reason = 'Rental is returned (has return transaction) but no issue transaction exists'

                if should_create:
                    items_to_fix.append({
                        'item': item,
                        'rental': rental,
                        'reason': reason
                    })

        if not items_to_fix:
            self.stdout.write(
                self.style.SUCCESS('✅ All rental items have correct issue transactions')
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f'📊 Found {len(items_to_fix)} items that need issue transactions'
            )
        )

        if verbose:
            self.stdout.write(_('\n📋 Items to fix:'))
            for item_data in items_to_fix[:20]:  # Show first 20
                item = item_data['item']
                rental = item_data['rental']
                self.stdout.write(
                    _('  • Rental #{rental_id}, Item #{item_id} ({inventory_number}): '
                      '{reason}').format(
                        rental_id=rental.id,
                        item_id=item.id,
                        inventory_number=item.inventory_item.inventory_number,
                        reason=item_data['reason']
                    )
                )
            if len(items_to_fix) > 20:
                self.stdout.write(
                    _('  ... and {} more items').format(len(items_to_fix) - 20)
                )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(_('\n⚠️  In test mode, changes are not applied'))
            )
            return

        # Apply fixes
        self.stdout.write(_('\n🔄 Creating missing issue transactions...'))

        try:
            with transaction.atomic():
                created_count = 0

                for item_data in items_to_fix:
                    rental_item = item_data['item']
                    rental = item_data['rental']
                    
                    # Get user who created the rental
                    performed_by = rental.created_by
                    
                    # Create issue transaction
                    RentalService.create_transaction(
                        rental_item=rental_item,
                        transaction_type='issue',
                        quantity=rental_item.quantity_requested,
                        performed_by=performed_by,
                        notes=_('Created automatically to fix missing issue transaction')
                    )
                    
                    created_count += 1
                    
                    if verbose:
                        self.stdout.write(
                            _('  ✅ Created issue transaction for Rental #{rental_id}, '
                              'Item #{item_id}: {quantity} unit(s)').format(
                                rental_id=rental.id,
                                item_id=rental_item.id,
                                quantity=rental_item.quantity_requested
                            )
                        )

                self.stdout.write(
                    self.style.SUCCESS(
                        _('\n✅ Successfully created {} issue transactions').format(created_count)
                    )
                )

                # Log result
                logger.info(
                    _('Created missing issue transactions: '
                      'created {} transactions').format(created_count)
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ Error during processing: {str(e)}')
            )
            logger.error(_('Error during creation of missing issue transactions: {}').format(str(e)))
            raise

        self.stdout.write(
            self.style.SUCCESS(_('\n🎉 Fix of missing issue transactions completed!'))
        )

