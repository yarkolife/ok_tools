"""
Management command to fix quantity_issued for rental items.

This command recalculates quantity_issued based on 'issue' transactions
and fixes items where quantity_issued was incorrectly set due to double increment bug.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from rental.models import RentalItem
from rental.models import RentalTransaction
import logging


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Management command to fix quantity_issued for rental items."""

    help = _('Fix quantity_issued for rental items based on transactions.')

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
        parser.add_argument(
            '--fix-all',
            action='store_true',
            help=_('Fix all items, not just those with incorrect values'),
        )

    def handle(self, *args, **options):
        """Execute command logic to fix quantity_issued."""
        dry_run = options['dry_run']
        verbose = options['verbose']
        fix_all = options['fix_all']

        self.stdout.write(
            self.style.SUCCESS('🚀 Starting fix of quantity_issued for rental items...')
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('⚠️  TEST MODE - changes will not be applied')
            )

        # Get all rental items
        rental_items = RentalItem.objects.select_related(
            'rental_request', 'inventory_item'
        ).all()

        items_to_fix = []
        items_checked = 0

        for rental_item in rental_items:
            items_checked += 1
            
            # Calculate correct quantity_issued from transactions
            issue_transactions = RentalTransaction.objects.filter(
                rental_item=rental_item,
                transaction_type='issue'
            )
            
            correct_quantity_issued = issue_transactions.aggregate(
                total=Sum('quantity')
            )['total'] or 0
            
            current_quantity_issued = rental_item.quantity_issued or 0
            
            # Check if fix is needed
            if fix_all or current_quantity_issued != correct_quantity_issued:
                items_to_fix.append({
                    'item': rental_item,
                    'current': current_quantity_issued,
                    'correct': correct_quantity_issued,
                    'difference': current_quantity_issued - correct_quantity_issued
                })

        if not items_to_fix:
            self.stdout.write(
                self.style.SUCCESS(f'✅ All {items_checked} rental items have correct quantity_issued')
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f'📊 Found {len(items_to_fix)} items with incorrect quantity_issued out of {items_checked} checked'
            )
        )

        if verbose:
            self.stdout.write(_('\n📋 Items to fix:'))
            for item_data in items_to_fix[:20]:  # Show first 20
                item = item_data['item']
                self.stdout.write(
                    _('  • Rental #{rental_id}, Item #{item_id} ({inventory_number}): '
                      'current={current}, correct={correct}, diff={diff}').format(
                        rental_id=item.rental_request.id,
                        item_id=item.id,
                        inventory_number=item.inventory_item.inventory_number,
                        current=item_data['current'],
                        correct=item_data['correct'],
                        diff=item_data['difference']
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
        self.stdout.write(_('\n🔄 Applying fixes...'))

        try:
            with transaction.atomic():
                fixed_count = 0
                total_correction = 0

                for item_data in items_to_fix:
                    rental_item = item_data['item']
                    correct_value = item_data['correct']
                    old_value = item_data['current']
                    
                    rental_item.quantity_issued = correct_value
                    rental_item.save(update_fields=['quantity_issued'])
                    
                    fixed_count += 1
                    total_correction += item_data['difference']
                    
                    if verbose:
                        self.stdout.write(
                            _('  ✅ Fixed Rental #{rental_id}, Item #{item_id}: '
                              '{old} → {new}').format(
                                rental_id=rental_item.rental_request.id,
                                item_id=rental_item.id,
                                old=old_value,
                                new=correct_value
                            )
                        )

                self.stdout.write(
                    self.style.SUCCESS(
                        _('\n✅ Successfully fixed {} rental items').format(fixed_count)
                    )
                )
                self.stdout.write(
                    _('📊 Total correction: {} units').format(total_correction)
                )

                # Log result
                logger.info(
                    _('Fixed quantity_issued for rental items: '
                      'fixed {} items, total correction: {} units').format(
                        fixed_count,
                        total_correction
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ Error during processing: {str(e)}')
            )
            logger.error(_('Error during fix of quantity_issued: {}').format(str(e)))
            raise

        self.stdout.write(
            self.style.SUCCESS(_('\n🎉 Fix of quantity_issued completed!'))
        )

