# All test descriptions are in English per project rules.

import io
import pytest
from types import SimpleNamespace
from unittest.mock import patch

from django.utils import timezone

from contributions import models as contrib_models
from contributions.disa_import import (
    _parse_date_string,
    _extract_license_number,
    _process_row_data,
    _prepare_contributions_for_batch_creation,
    _batch_create_contributions,
    disa_import,
    INFO,
    LIVE,
    TITLE,
    TYPE,
    BEGIN,
)
from licenses.models import License


class Cell:
    """Minimal cell stub with .value attribute used by row processing."""
    def __init__(self, value):
        self.value = value


@pytest.mark.django_db
def test__disa_import___parse_date_string__valid():
    """Parse valid DISA date string returns timezone-aware datetime."""
    dt = _parse_date_string("08.09.2022 09:30:00")
    assert dt is not None
    assert timezone.is_aware(dt)
    assert dt.year == 2022 and dt.month == 9 and dt.day == 8
    assert dt.hour == 9 and dt.minute == 30 and dt.second == 0


def test__disa_import___parse_date_string__invalid():
    """Parse invalid DISA date string returns None and logs."""
    # Missing seconds
    assert _parse_date_string("08.09.2022 09:30") is None
    # Non-numeric parts
    assert _parse_date_string("08.09.XXXX 09:30:00") is None
    # Empty
    assert _parse_date_string("") is None


def test__disa_import___extract_license_number():
    """Extract number from title string or return None."""
    assert _extract_license_number("123_Title") == 123
    assert _extract_license_number("9999_Another") == 9999
    assert _extract_license_number("TrailerTest") is None
    assert _extract_license_number("Programmvorschau_something") is None
    assert _extract_license_number("Infoblock") is None


def test__disa_import___process_row_data__ignores_info_and_prefixes():
    """Process rows ignores INFO type and ignored prefixes, returns valid data only."""
    # Row with INFO type should be ignored
    row_info = [Cell(None)] * (TYPE + 1)
    row_info[TITLE] = Cell("Infoblock_Title")
    row_info[TYPE] = Cell(INFO)

    # Row with ignored prefix should be ignored
    row_trailer = [Cell(None)] * (TYPE + 1)
    row_trailer[TITLE] = Cell("Trailer_ABC")
    row_trailer[TYPE] = Cell("SomeType")

    # Valid row should be included
    row_valid = [Cell(None)] * (TYPE + 1)
    row_valid[TITLE] = Cell("123_Something")
    row_valid[TYPE] = Cell(LIVE)

    rows_data, license_numbers = _process_row_data(iter([row_info, row_trailer, row_valid]))
    assert len(rows_data) == 1
    assert license_numbers == {123}


@pytest.mark.django_db
def test__disa_import___prepare_contributions_for_batch_creation__no_license():
    """No license found should add error message and skip row."""
    # Build a single valid-like row for a missing license number 999
    row = [Cell(None)] * (TYPE + 1)
    row[TITLE] = Cell("999_Test")
    row[TYPE] = Cell(LIVE)
    row[BEGIN] = Cell("08.09.2022 09:30:00")

    rows_data = [row]
    licenses_dict = {}  # No licenses loaded
    no_repetition_license_ids = set()
    existing_contributions_set = set()

    # Patch messages.error to capture calls without needing request storage
    with patch("django.contrib.messages.error") as msg_error:
        contributions_to_create, dates_to_delete, error_count = _prepare_contributions_for_batch_creation(
            rows_data,
            licenses_dict,
            no_repetition_license_ids,
            existing_contributions_set,
            request=SimpleNamespace()
        )

        assert error_count == 1
        assert len(contributions_to_create) == 0
        assert msg_error.called
        # Ensure date parsing was attempted and date collected only when a license exists;
        # since license missing, dates_to_delete should be empty.
        assert len(dates_to_delete) == 0


@pytest.mark.django_db
def test__disa_import___prepare_contributions_for_batch_creation__repetition_block_with_existing_primary():
    """Block repetitions when not allowed and primary already exists."""
    # Create a license that disallows repetitions
    lic = License.objects.create(
        profile=None,  # minimal stub, actual model requires fields in fixtures elsewhere
        title="Block Test",
        description="desc",
        duration=timezone.timedelta(minutes=1),
        repetitions_allowed=False,
        number=123,
    )
    # Create an existing contribution for that license (primary)
    contrib_models = contrib_models  # alias to avoid shadowing
    contrib_models.Contribution.objects.create(
        license=lic,
        broadcast_date=timezone.now(),
        live=False
    )

    # Build a row for that license
    row = [Cell(None)] * (TYPE + 1)
    row[TITLE] = Cell("123_Something")
    row[TYPE] = Cell(LIVE)
    row[BEGIN] = Cell("08.09.2022 09:30:00")

    rows_data = [row]
    # Preloaded data
    licenses_dict = {123: lic}
    no_repetition_license_ids = {lic.id}
    existing_contributions_set = {lic.id}

    with patch("django.contrib.messages.error") as msg_error:
        contributions_to_create, dates_to_delete, error_count = _prepare_contributions_for_batch_creation(
            rows_data,
            licenses_dict,
            no_repetition_license_ids,
            existing_contributions_set,
            request=SimpleNamespace()
        )
        assert error_count == 1
        assert len(contributions_to_create) == 0
        assert msg_error.called


@pytest.mark.django_db
def test__disa_import___batch_create_contributions__fallback_on_error():
    """bulk_create error should fall back to individual save, counting created entries."""
    # Create a license to attach contributions to
    lic = License.objects.create(
        profile=None,
        title="Create Test",
        description="desc",
        duration=timezone.timedelta(minutes=1),
        repetitions_allowed=True,
        number=777,
    )

    # Prepare one contribution object
    c = contrib_models.Contribution(
        license=lic,
        broadcast_date=timezone.now(),
        live=True
    )

    # Force bulk_create to raise an exception
    with patch.object(contrib_models.Contribution.objects, "bulk_create", side_effect=Exception("boom")):
        created = _batch_create_contributions([c])
        assert created == 1
        # Ensure it was persisted individually
        assert contrib_models.Contribution.objects.count() == 1


@pytest.mark.django_db
def test__disa_import___disa_import__handles_exception():
    """Any exception during import should be reported via messages.error."""
    with patch("contributions.disa_import.load_workbook", side_effect=Exception("boom")), \
         patch("django.contrib.messages.error") as msg_error:
        # Call with a dummy file-like object
        disa_import(SimpleNamespace(), io.BytesIO(b"dummy"))
        assert msg_error.called
        # Error message contains the exception string
        assert "boom" in str(msg_error.call_args[0][1])


@pytest.mark.django_db
def test__disa_import___disa_import__no_valid_data_warning():
    """No valid data should report messages.warning and return without creating contributions."""
    # Minimal workbook stubs
    class MinimalWS:
        def __init__(self):
            # Two rows consumed as headers/empty per implementation (next twice)
            self._rows = iter([
                [Cell("header-ignored")] * (TYPE + 1),
                [Cell(None)] * (TYPE + 1),
            ])

        @property
        def rows(self):
            return self._rows

    class MinimalWB:
        def __getitem__(self, key):
            # Return our minimal worksheet for the expected WS_NAME
            return MinimalWS()

    with patch("contributions.disa_import.load_workbook", return_value=MinimalWB()), \
         patch("contributions.disa_import._process_row_data", return_value=([], set())), \
         patch("django.contrib.messages.warning") as msg_warn:
        disa_import(SimpleNamespace(), io.BytesIO(b"dummy"))
        assert msg_warn.called
        assert "No valid data found in file" in str(msg_warn.call_args[0][1])
        assert contrib_models.Contribution.objects.count() == 0