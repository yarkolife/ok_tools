from . import models
from datetime import datetime
from datetime import date as date_type
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.forms import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from io import BytesIO
from licenses.models import License
from openpyxl import load_workbook
from openpyxl import Workbook
from zoneinfo import ZoneInfo
import logging
import os
import pandas as pd
import re


logger = logging.getLogger('django')

BEGIN = 1
END = 2
DURATION = 3
TITLE = 4
TYPE = 11

WS_NAME = 'Auftragsfenster'
INFO = 'Infoblock'
LIVE = 'Live-Quelle'
IGNORED_PREFIXES = ['Trailer', 'Programmvorschau']


def _detect_excel_format(file) -> str:
    """
    Detect Excel file format by checking magic bytes.
    
    Args:
        file: File object
        
    Returns:
        'xlsx' for Office Open XML format, 'xls' for legacy BIFF format
    """
    if hasattr(file, 'seek'):
        file.seek(0)
    
    # Read first 8 bytes to detect format
    if hasattr(file, 'read'):
        header = file.read(8)
        file.seek(0)
    else:
        with open(file, 'rb') as f:
            header = f.read(8)
    
    # XLSX files start with PK (ZIP archive)
    if header[:2] == b'PK':
        return 'xlsx'
    # XLS files start with compound document header (D0 CF 11 E0)
    elif header[:4] == b'\xd0\xcf\x11\xe0':
        return 'xls'
    else:
        # Fallback: try by extension
        filename = getattr(file, 'name', str(file))
        if filename.lower().endswith('.xls'):
            return 'xls'
        return 'xlsx'


def convert_xls_to_xlsx(file) -> BytesIO:
    """
    Convert .xls file to .xlsx format using pandas + xlrd.
    
    Args:
        file: File object or path to .xls file (must be actual XLS format)
        
    Returns:
        BytesIO object containing .xlsx data
    """
    if hasattr(file, 'seek'):
        file.seek(0)
    
    # Read .xls file with xlrd engine
    df = pd.read_excel(file, engine='xlrd', sheet_name=WS_NAME, header=None)
    
    # Create new .xlsx in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=WS_NAME, index=False, header=False)
    
    output.seek(0)
    return output


def _load_workbook_auto(file):
    """
    Load workbook from file, automatically handling format detection and conversion.
    
    Args:
        file: File object (can be .xls or .xlsx, detected by content)
        
    Returns:
        openpyxl Workbook object
    """
    file_format = _detect_excel_format(file)
    
    if file_format == 'xls':
        # Convert real XLS to XLSX
        if hasattr(file, 'seek'):
            file.seek(0)
        xlsx_data = convert_xls_to_xlsx(file)
        return load_workbook(xlsx_data)
    else:
        # Already XLSX format (even if extension is .xls)
        if hasattr(file, 'seek'):
            file.seek(0)
        return load_workbook(file)


def get_unique_dates(file) -> list[date_type]:
    """
    Extract unique dates from the Anfang column of DISA export file.
    
    Args:
        file: File object (.xls or .xlsx)
        
    Returns:
        Sorted list of unique dates found in the file
    """
    try:
        wb = _load_workbook_auto(file)
        
        if WS_NAME not in wb.sheetnames:
            logger.warning(f'Worksheet {WS_NAME} not found in file')
            return []
        
        ws = wb[WS_NAME]
        rows = ws.rows
        next(rows)  # Skip header
        
        unique_dates = set()
        
        for row in rows:
            # Skip empty rows
            if not any([row[i].value for i in range(TYPE)]):
                continue
            
            date_str = row[BEGIN].value
            if date_str:
                parsed_date = _parse_date_string(date_str)
                if parsed_date:
                    unique_dates.add(parsed_date.date())
        
        return sorted(unique_dates)
        
    except Exception as e:
        logger.error(f'Error extracting dates from file: {e}')
        return []


def _check_title(title: str, type: str) -> bool:
    """Check weather the title is valid."""
    if re.match(r'^\d+_', title):
        return True

    if type == INFO:
        return True

    if any([title.startswith(x) for x in IGNORED_PREFIXES]):
        return True

    return False


def validate(file):
    """
    Validate the DISA export file.

    Check weather the column and title naming is right.
    Supports both .xls and .xlsx formats.
    """
    wb = _load_workbook_auto(file)
    errors: list[ValidationError] = []

    def e(message: str) -> None:
        """Append an new ValidationError to the error list."""
        errors.append(ValidationError(message))

    if WS_NAME not in wb.sheetnames:
        e(_('The worksheet needs to be named "%(name)s".') % {'name': WS_NAME})
        raise ValidationError(errors)

    ws = wb[WS_NAME]
    rows = ws.rows
    header = next(rows)

    if header[BEGIN].value != (NAME := 'Anfang'):
        e(_('Column %(nr)s needs to be named %(name)s')
          % {
            'nr': BEGIN,
            'name': NAME
        })

    if header[END].value != (NAME := 'Ende'):
        e(_('Column %(nr)s needs to be named %(name)s')
          % {
            'nr': END,
            'name': NAME
        })

    if header[DURATION].value != (NAME := 'Länge'):
        e(_('Column %(nr)s needs to be named %(name)s')
          % {
            'nr': DURATION,
            'name': NAME
        })

    if header[TITLE].value != (NAME := 'Titel'):
        e(_('Column %(nr)s needs to be named %(name)s')
          % {
            'nr': TITLE,
            'name': NAME
        })

    if header[TYPE].value != (NAME := 'Typ'):
        e(_('Column %(nr)s needs to be named %(name)s')
          % {
            'nr': TYPE,
            'name': NAME
        })

    for row in rows:
        if not any([row[i].value for i in range(TYPE)]):
            continue
        if (not _check_title(row[TITLE].value, row[TYPE].value)):
            e(_('Invalid title in cell %(c)s%(r)s. Title needs the format'
                ' <nr>_<title>.') %
              {
                  'c': row[TITLE].column_letter,
                  'r': row[TITLE].row,
            })

    if errors:
        raise ValidationError(errors)


def _parse_date_string(date_value):
    """
    Parse date from DISA format (string or datetime object).
    
    Args:
        date_value: Date string in format DD.MM.YYYY HH:MM:SS or datetime object
        
    Returns:
        datetime object with timezone (timezone-aware)
    """
    try:
        # If it's already a datetime object (from openpyxl)
        if isinstance(date_value, datetime):
            # If it's naive, make it timezone-aware
            if timezone.is_naive(date_value):
                return timezone.make_aware(date_value, timezone=ZoneInfo(settings.TIME_ZONE))
            # If it's already aware, return as is
            return date_value
        
        # If it's a string, parse it
        date_str = str(date_value)
        date_parts = [int(x) for x in re.split(r'\.| |:', date_str)]
        return datetime(
            day=date_parts[0],
            month=date_parts[1],
            year=date_parts[2],
            hour=date_parts[3],
            minute=date_parts[4],
            second=date_parts[5],
            tzinfo=ZoneInfo(settings.TIME_ZONE)
        )
    except (ValueError, IndexError, TypeError) as e:
        logger.error(f"Error parsing date '{date_value}': {e}")
        return None


def _extract_license_number(title):
    """
    Extract license number from title.
    
    Args:
        title: Title string containing license number
        
    Returns:
        License number as integer or None if not found
    """
    match = re.match(r'^\d+', title)
    return int(match[0]) if match else None


def _process_row_data(rows, from_date: date_type = None):
    """
    Process and validate row data from Excel file.
    
    Args:
        rows: Iterator of Excel rows
        from_date: Optional date to filter rows (only include rows >= from_date)
        
    Returns:
        Tuple of (processed_rows_data, license_numbers_set)
    """
    rows_data = []
    license_numbers = set()
    
    for row in rows:
        # Skip empty rows (continue instead of break to process entire file)
        if not any([row[i].value for i in range(TYPE)]):
            continue

        if (
            row[TYPE].value == INFO or
            any([row[TITLE].value.startswith(x) for x in IGNORED_PREFIXES])
        ):
            continue

        # Filter by date if from_date is specified
        if from_date:
            date_str = row[BEGIN].value
            if date_str:
                parsed_date = _parse_date_string(date_str)
                if parsed_date and parsed_date.date() < from_date:
                    continue

        license_number = _extract_license_number(row[TITLE].value)
        if license_number:
            license_numbers.add(license_number)
            rows_data.append(row)
    
    return rows_data, license_numbers


def _preload_licenses_data(license_numbers):
    """
    Preload all necessary license data in minimal queries.
    
    Args:
        license_numbers: Set of license numbers to preload
        
    Returns:
        Tuple of (licenses_dict, no_repetition_license_ids, existing_contributions_set)
    """
    # One SQL query for all licenses instead of N queries
    licenses_dict = {
        lic.number: lic
        for lic in License.objects.filter(number__in=license_numbers)
    }
    
    # Get IDs of licenses that don't allow repetitions
    no_repetition_license_ids = set(
        License.objects.filter(
            number__in=license_numbers,
            repetitions_allowed=False
        ).values_list('id', flat=True)
    )
    
    # Get existing contributions for licenses with repetition ban
    existing_contributions_set = set()
    if no_repetition_license_ids:
        existing_contributions_set = set(
            models.Contribution.objects.filter(
                license_id__in=no_repetition_license_ids
            ).values_list('license_id', flat=True).distinct()
        )
    
    return licenses_dict, no_repetition_license_ids, existing_contributions_set


def _prepare_contributions_for_batch_creation(rows_data, licenses_dict, no_repetition_license_ids, existing_contributions_set, request):
    """
    Prepare contribution data for batch creation.
    
    Args:
        rows_data: List of Excel rows
        licenses_dict: Dictionary of licenses indexed by number
        no_repetition_license_ids: Set of license IDs that don't allow repetitions
        existing_contributions_set: Set of license IDs with existing contributions
        request: HTTP request object for error messages
        
    Returns:
        Tuple of (contributions_to_create, dates_to_delete, error_count)
    """
    contributions_to_create = []
    dates_to_delete = set()
    error_count = 0
    
    for row in rows_data:
        license_number = _extract_license_number(row[TITLE].value)
        license = licenses_dict.get(license_number)
        
        if not license:
            msg = _('No license with number %(n)s found.') % {'n': license_number}
            logger.error(msg)
            messages.error(request, msg)
            error_count += 1
            continue

        broadcast_date = _parse_date_string(row[BEGIN].value)
        if not broadcast_date:
            error_count += 1
            continue

        # Collect dates for batch deletion
        dates_to_delete.add(broadcast_date.date())
        
        # Check if repetitions are allowed (skip for Live broadcasts)
        if (not license.is_live and
            license.id in no_repetition_license_ids and
            license.id in existing_contributions_set):
            msg = _('No repetitions for number %(n)s allowed and already'
                    ' found a primary contribution.') % {'n': license_number}
            logger.error(msg)
            messages.error(request, msg)
            error_count += 1
            continue

        # Create contribution object for batch creation
        contribution = models.Contribution(
            license=license,
            broadcast_date=broadcast_date,
            live=(row[TYPE].value == LIVE)
        )
        contributions_to_create.append(contribution)
    
    return contributions_to_create, dates_to_delete, error_count


def _batch_delete_contributions_by_dates(dates_to_delete):
    """
    Delete existing contributions by dates in batch.
    
    Args:
        dates_to_delete: Set of dates to delete contributions for
    """
    if dates_to_delete:
        for date in dates_to_delete:
            models.Contribution.objects.filter(
                broadcast_date__date=date
            ).delete()


def _batch_create_contributions(contributions_to_create):
    """
    Create contributions in batch using bulk_create.
    
    Args:
        contributions_to_create: List of Contribution objects to create
        
    Returns:
        Number of created contributions
    """
    if not contributions_to_create:
        return 0
    
    BATCH_SIZE = 500
    created_count = 0
    
    # Process in batches to avoid memory issues
    for i in range(0, len(contributions_to_create), BATCH_SIZE):
        batch = contributions_to_create[i:i + BATCH_SIZE]
        
        try:
            with transaction.atomic():
                created = models.Contribution.objects.bulk_create(batch, ignore_conflicts=True)
                created_count += len(created)
                logger.info(f'Successfully created {len(created)} contributions in batch')
        except Exception as e:
            logger.error(f'Error creating batch of contributions: {e}')
            # Fall back to individual creation
            for contribution in batch:
                try:
                    with transaction.atomic():
                        contribution.save()
                        created_count += 1
                        logger.info(f'Created contribution {contribution}')
                except Exception as individual_error:
                    logger.error(f'Failed to create contribution {contribution}: {individual_error}')
    
    return created_count


def disa_import(request, file, from_date: date_type = None):
    """
    Import contributions from DISA export - OPTIMIZED VERSION.

    All valid data gets imported even if an error occurs.
    Supports both .xls and .xlsx formats.
    
    Args:
        request: HTTP request object
        file: File object (.xls or .xlsx)
        from_date: Optional date to filter rows (only import rows >= from_date)
    
    Optimizations:
    1. Minimal database queries using preloading
    2. Batch operations for creating contributions
    3. Improved error handling and logging
    4. Better code organization and readability
    """
    try:
        wb = _load_workbook_auto(file)
        ws = wb[WS_NAME]
        rows = ws.rows
        next(rows)  # ignore headers
        next(rows)  # ignore empty row

        # Process row data and extract license numbers (with optional date filtering)
        rows_data, license_numbers = _process_row_data(rows, from_date)
        
        if not rows_data:
            msg = _('No valid data found in file.')
            logger.warning(msg)
            messages.warning(request, msg)
            return

        # Preload all necessary data in minimal queries
        licenses_dict, no_repetition_license_ids, existing_contributions_set = _preload_licenses_data(license_numbers)
        
        # Prepare contributions for batch creation
        contributions_to_create, dates_to_delete, error_count = _prepare_contributions_for_batch_creation(
            rows_data, licenses_dict, no_repetition_license_ids, existing_contributions_set, request
        )
        
        # Delete existing contributions by dates in batch
        _batch_delete_contributions_by_dates(dates_to_delete)
        
        # Create contributions in batch
        created_count = _batch_create_contributions(contributions_to_create)
        
        # Report results
        total_processed = len(rows_data)
        success_count = created_count
        msg = _('Successfully processed %(total)d rows, created %(created)d contributions, %(errors)d errors.') % {
            'total': total_processed,
            'created': success_count,
            'errors': error_count
        }
        logger.info(msg)
        messages.info(request, msg)
        
    except Exception as e:
        error_msg = _('Error during import: %(error)s') % {'error': str(e)}
        logger.error(error_msg, exc_info=True)
        messages.error(request, error_msg)
