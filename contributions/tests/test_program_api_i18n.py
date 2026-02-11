"""Tests for program API localization behavior."""

from datetime import datetime

import pytest
from django.urls import reverse

from ok_tools.datetime import TZ
from ok_tools.testing import create_contribution
from ok_tools.testing import create_license


@pytest.mark.django_db
def test__contributions__api__program_schedule__returns_de_localized_user_fields(
    client,
    user,
    license_dict,
    contribution_dict,
):
    """Program API returns localized user-facing fields in German locale."""
    # Regular contribution to verify localized credits text.
    regular_license = create_license(user.profile, license_dict)
    contribution_dict["broadcast_date"] = datetime(2026, 2, 11, 22, 15, tzinfo=TZ)
    create_contribution(regular_license, contribution_dict)

    # Infoblock contribution to verify localized info block title.
    infoblock_license_dict = dict(license_dict)
    infoblock_license_dict["title"] = "Infoblock Source"
    infoblock_license = create_license(user.profile, infoblock_license_dict)
    infoblock_license.infoblock = True
    infoblock_license.save(update_fields=["infoblock"])

    contribution_dict["broadcast_date"] = datetime(2026, 2, 11, 23, 55, tzinfo=TZ)
    create_contribution(infoblock_license, contribution_dict)

    client.force_login(user)
    response = client.get(
        reverse("contributions:api-program-schedule"),
        HTTP_ACCEPT_LANGUAGE="de",
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    credits_values = [row.get("credits", "") for row in data]
    assert any(credits.startswith("Ein Beitrag von ") for credits in credits_values)

    titles = [row.get("title", "") for row in data]
    assert "Infoblock" in titles

