# Fix Quantity Issued - Production Deployment Guide

This guide explains how to apply the fix for the `quantity_issued` double increment bug on the production server.

## Problem

The bug caused `quantity_issued` to be incremented twice when creating issue transactions:
1. Once in `create_transaction()` method
2. Once in the signal handler

This resulted in items showing 3 units issued instead of 1.

## Solution Steps

### Step 1: Commit and Push Code Changes

First, commit and push all code changes to the repository:

```bash
git add .
git commit -m "Fix double increment bug in quantity_issued calculation"
git push -u origin HEAD  # or your branch name
```

### Step 2: Update Production Server

SSH into your production server and update the code:

```bash
cd /path/to/ok_tools_production
./update.sh
```

This will:
- Pull latest code from git
- Rebuild Docker containers
- Run migrations (if any)
- Restart services

### Step 3: Verify Code Update

Check that the containers are running with the new code:

```bash
docker compose ps
docker compose logs web --tail=50
```

### Step 4: Fix Existing Data (DRY RUN FIRST!)

**IMPORTANT**: Always run with `--dry-run` first to see what will be changed!

```bash
# Check what will be fixed (dry run)
docker compose exec web python manage.py fix_quantity_issued --dry-run --verbose

# Review the output carefully
```

### Step 5: Apply Data Fixes

If the dry-run output looks correct, apply the fixes:

```bash
# Fix quantity_issued values based on transactions
docker compose exec web python manage.py fix_quantity_issued --verbose
```

### Step 6: Fix Missing Issue Transactions

Some items may have been issued directly (without creating transactions). Fix them:

```bash
# Check what needs to be fixed (dry run)
docker compose exec web python manage.py fix_missing_issue_transactions --dry-run --verbose

# Apply fixes
docker compose exec web python manage.py fix_missing_issue_transactions --verbose
```

### Step 7: Verify Results

Verify that all fixes were applied correctly:

```bash
docker compose exec web python manage.py shell -c "
from rental.models import RentalItem, RentalTransaction
from django.db.models import Sum

# Check a few items to verify
items = RentalItem.objects.filter(quantity_issued__gt=0)[:5]
for item in items:
    correct = RentalTransaction.objects.filter(
        rental_item=item, transaction_type='issue'
    ).aggregate(total=Sum('quantity'))['total'] or 0
    print(f'Item #{item.id}: quantity_issued={item.quantity_issued}, correct={correct}, match={item.quantity_issued == correct}')
"
```

## Complete Command Sequence

Here's the complete sequence for production:

```bash
# 1. Update code
cd /path/to/ok_tools_production
./update.sh

# 2. Fix quantity_issued (dry run)
docker compose exec web python manage.py fix_quantity_issued --dry-run --verbose

# 3. Fix quantity_issued (apply)
docker compose exec web python manage.py fix_quantity_issued --verbose

# 4. Fix missing transactions (dry run)
docker compose exec web python manage.py fix_missing_issue_transactions --dry-run --verbose

# 5. Fix missing transactions (apply)
docker compose exec web python manage.py fix_missing_issue_transactions --verbose
```

## Rollback

If something goes wrong, you can rollback the code:

```bash
cd /path/to/ok_tools_production
./rollback.sh
```

However, **data changes cannot be automatically rolled back**. If you need to restore data, you'll need to restore from a database backup.

## Backup Before Fixing

**IMPORTANT**: Always backup the database before running data fixes!

```bash
# Create database backup
docker compose exec web python manage.py backup_db --compress

# Or use your backup script
./backup_db.sh
```

## What Gets Fixed

1. **fix_quantity_issued**: Recalculates `quantity_issued` based on existing 'issue' transactions
2. **fix_missing_issue_transactions**: Creates missing 'issue' transactions for items that are in 'issued' or 'returned' status but don't have corresponding transactions

## Notes

- Both commands are safe to run multiple times (idempotent)
- The fix only affects `quantity_issued` values, not other data
- Transactions are preserved and used as the source of truth
- The fix is backward compatible - old data is corrected, new data works correctly

