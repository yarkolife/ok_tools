VERIFIED_BADGE = 'bi-check-circle me-1"></i>Verified'


def test_views__home__1(browser, user):
    """It shows the dashboard of the logged in user."""
    browser.login()
    assert user.email in browser.contents
    assert 'My Dashboard' in browser.contents


def test_views__home__2(browser, user):
    """It links to the password change and to the application form."""
    browser.login()
    dashboard_url = browser.url

    browser.follow('Change Password')
    assert 'password_reset' in browser.url

    browser.open(dashboard_url)
    browser.follow('Print Registration')
    assert 'profile/application' in browser.url


def test_views__home__3(browser, user):
    """It marks the profile as verified only if it is verified."""
    browser.login()
    dashboard_url = browser.url
    assert VERIFIED_BADGE not in browser.contents

    user.profile.verified = True
    user.profile.save()
    browser.open(dashboard_url)

    assert VERIFIED_BADGE in browser.contents
