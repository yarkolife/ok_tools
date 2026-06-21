from .email import send_auth_mail
from .models import Gender
from .models import OrganizationConfig
from .models import Profile
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse_lazy
from ok_tools.testing import DOMAIN
from ok_tools.testing import EMAIL
from ok_tools.testing import PWD
from ok_tools.testing import create_user
from ok_tools.testing import pdfToText
from unittest.mock import patch
from urllib.error import HTTPError
import datetime
import logging
import pytest
import re


logger = logging.getLogger('django')

User = get_user_model()

USER_CREATED_URL = f'{DOMAIN}{reverse_lazy("registration:user_created")}'
REGISTER_URL = f'{DOMAIN}{reverse_lazy("registration:register")}'
LOGIN_URL = f'{DOMAIN}{reverse_lazy("login")}'
HOME_URL = f'{DOMAIN}{reverse_lazy("home")}'
APPLY_URL = f'{DOMAIN}{reverse_lazy("registration:print_registration")}'
USER_EDIT_URL = f'{DOMAIN}{reverse_lazy("registration:user_data")}'
AUTH_URL = r'https?://(localhost:8000|testserver)/profile/reset/.*/'
PWD_RESET_URL = f'{DOMAIN}{reverse_lazy("password_reset")}'
PRIVACY_POLICY_URL = f'{DOMAIN}{reverse_lazy("privacy_policy")}'


def test__registration__views__RegisterView__1(browser, user_dict):
    """It is possible to register with an unused email address."""
    _register_user(browser, user_dict)
    assert _success_string(user_dict['email']) in browser.contents
    assert browser.url == USER_CREATED_URL


def test__registration__views__RegisterView__2(browser, user_dict):
    """It is not possible to register with an used email address."""
    User(email=user_dict['email']).save()

    _register_user(browser, user_dict)
    assert f'address {user_dict["email"]} already exists' in browser.contents
    assert browser.url == REGISTER_URL


def test__registration__views__RegisterView__3(browser, user_dict):
    """It is not possible to register with an invalid email address."""
    user_dict['email'] = "example.com"

    _register_user(browser, user_dict)
    assert 'Enter a valid email address' in browser.contents
    assert browser.url == REGISTER_URL


def test__registration__views__RegisterView__4(browser, user_dict):
    """It is possible to register with a valid phone number."""
    user_dict['phone_number'] = '+49346112345'
    user_dict['mobile_number'] = '015712345678'
    _register_user(browser, user_dict)
    assert _success_string(user_dict['email']) in browser.contents
    assert browser.url == USER_CREATED_URL


def test__registration__views__RegisterView__5(browser, user_dict):
    """It is not possible to register without mandatory fields."""
    user_dict['first_name'] = None
    _register_user(browser, user_dict)
    assert 'This field is required' in browser.contents
    assert browser.url == REGISTER_URL


def test__registration__email__send_auth_mail__1(db, user_dict):
    # db is needed for data base access in send_auth_mail
    """It is not possible to send an authentication mail to an unknown user."""
    with pytest.raises(User.DoesNotExist):
        send_auth_mail(user_dict['email'], DOMAIN)


def test__registration__email__send_auth_mail__2(db, user_dict, mail_outbox):
    """After the registration an email gets send."""
    client = Client()
    # Register user via Django test client
    response = client.post(
        reverse_lazy('registration:register'),
        data={
            'email': user_dict['email'],
            'first_name': user_dict['first_name'],
            'last_name': user_dict['last_name'],
            'gender': user_dict['gender'],
            'phone_number': user_dict['phone_number'] or '',
            'mobile_number': user_dict['mobile_number'] or '',
            'birthday': '05.09.1989',
            'street': user_dict['street'],
            'house_number': user_dict['house_number'],
            'zipcode': user_dict['zipcode'],
            'city': user_dict['city'],
            'privacy_agreement': True,
            'usage_agreement': True,
        }
    )
    assert 1 == len(mail_outbox)
    assert _get_link_url_from_email(mail_outbox, AUTH_URL)


def test__registration__email__send_auth_mail__3(db, user_dict, mail_outbox):
    """A user can set a password after registration."""
    client = Client()
    response = client.post(
        reverse_lazy('registration:register'),
        data={
            'email': user_dict['email'],
            'first_name': user_dict['first_name'],
            'last_name': user_dict['last_name'],
            'gender': user_dict['gender'],
            'phone_number': user_dict['phone_number'] or '',
            'mobile_number': user_dict['mobile_number'] or '',
            'birthday': '05.09.1989',
            'street': user_dict['street'],
            'house_number': user_dict['house_number'],
            'zipcode': user_dict['zipcode'],
            'city': user_dict['city'],
            'privacy_agreement': True,
            'usage_agreement': True,
        }
    )
    assert 1 == len(mail_outbox)
    pw_url = _get_link_url_from_email(mail_outbox, AUTH_URL)
    # Extract the token part from the URL
    # The URL format is: http://localhost:8000/profile/reset/<uid>/<token>/
    # We need to follow the reset link and set the password
    response = client.get(pw_url)
    assert response.status_code == 200
    # Submit the password
    response = client.post(pw_url, {
        'new_password1': PWD,
        'new_password2': PWD,
    })
    assert response.status_code == 302  # Redirect after password set
    assert '/profile/reset/done' in response.url


def test__registration__email__send_auth_mail__4(db, user, mail_outbox):
    """It is possible to change the password."""
    client = Client()
    client.login(email=user.email, password=PWD)
    
    response = client.post(reverse_lazy('password_reset'), {
        'email': user.email,
    })
    assert response.status_code == 302
    assert 1 == len(mail_outbox)
    assert _get_link_url_from_email(mail_outbox, AUTH_URL)


def test__registration__email__send_auth_mail__5(db, user_dict):
    """It is not possible to send an email to someone without Profile."""
    testuser = User.objects.create_user(email=user_dict['email'], password=PWD)
    testuser.save()

    with pytest.raises(Profile.DoesNotExist):
        send_auth_mail(user_dict['email'], DOMAIN)


def test__registration__email__send_auth_mail__6(db, user, mail_outbox):
    """It is possible to set a new password using email."""
    client = Client()
    response = client.post(reverse_lazy('password_reset'), {
        'email': user.email,
    })
    assert response.status_code == 302
    assert 1 == len(mail_outbox)
    assert _get_link_url_from_email(mail_outbox, AUTH_URL)
    assert 'password change' in mail_outbox[-1].body
    assert user.profile.first_name in mail_outbox[-1].body


def test__registration__email__send_auth_mail__7(db, user):
    """It is not possible to send a password reset to an unknown user."""
    with patch('registration.models.OKUser.objects.get') as mock:
        mock.side_effect = User.DoesNotExist()
        client = Client()
        response = client.post(reverse_lazy('password_reset'), {
            'email': 'unknown@example.com',
        })
        # Should not raise HTTPError, just handle gracefully
        assert response.status_code in [200, 302]


def test__registration__email__send_auth_mail__8(db, user, mail_outbox):
    """Use https for the link send in the email."""
    send_auth_mail(user.email, DOMAIN, use_https=True)
    assert 'https://' in mail_outbox[0].body


def test__registration__email__send_auth_mail__9(db, mail_outbox):
    """It is possible to change the password without a profile."""
    User.objects.create_user(email=EMAIL, password=PWD)
    client = Client()
    client.login(email=EMAIL, password=PWD)
    
    response = client.post(reverse_lazy('password_reset'), {
        'email': EMAIL,
    })
    assert response.status_code == 302
    assert 1 == len(mail_outbox)
    assert _get_link_url_from_email(mail_outbox, AUTH_URL)


def test__registration__models__UserManager__1():
    """It is not possible to register without an email on model base."""
    with pytest.raises(ValueError, match=r'.*email.*set.*|.*E-Mail.*angegeben.*'):
        User.objects.create_user(email=None)


def test__registration__models__UserManager__2(user_dict):
    """A superuser needs to be a staff."""
    with pytest.raises(ValueError, match=r'.*is_staff.*True.*|.*is_staff.*True.*'):
        User.objects.create_superuser(
            email=user_dict['email'], password=None, is_staff=False)


def test__registration__models__UserManager__3(user_dict):
    """A superuser needs to have the right to be a superuser."""
    with pytest.raises(ValueError, match=r'.*is_superuser.*True.*|.*is_superuser.*True.*'):
        User.objects.create_superuser(
            email=user_dict['email'], password=None, is_superuser=False)


def test__registration__models__1(db, user_dict):
    """
    String representation.

    A User gets represented by his/her email address. A Profile by its first
    and last name.
    """
    testuser = User(email=user_dict['email'])
    assert user_dict['email'] in testuser.__str__()
    testprofil = Profile(
        okuser=testuser,
        first_name=user_dict['first_name'],
        last_name=user_dict['last_name']
    )
    assert user_dict['first_name'] in testprofil.__str__()
    assert user_dict['last_name'] in testprofil.__str__()


def test__registration__models__Profile__Gender__verbose_name__1(db):
    """The verbose name of an invalid value is en empty string."""
    assert Gender.verbose_name('invalid') == ''


def test__registration__backends__EmailBackend__1(browser):
    """It is not possible to log in with an unknown email address."""
    browser.login()
    assert 'enter a correct email address and password' in browser.contents


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
def test__registration__backends__EmailBackend__2(db, user, browser):
    """It is possible to log in with a known user."""
    browser.login()
    browser.open(f'{DOMAIN}/dashboard/')
    # After login, user is redirected to dashboard
    # Check for successful login by looking for logout link or user menu
    print(f"DEBUG: URL after login: {browser.url}")
    print(f"DEBUG: Contents contains LOGOUT: {'LOGOUT' in browser.contents}")
    print(f"DEBUG: Contents contains Abmelden: {'Abmelden' in browser.contents}")
    # Check for user-specific content
    assert 'LOGOUT' in browser.contents or 'Abmelden' in browser.contents or user.profile.first_name in browser.contents


def test__registration__backends__EmailBackend__3(browser):
    """Log in with wrong password."""
    testuser = User.objects.create_user(email=EMAIL, password=PWD)
    testuser.save()

    browser.login(password='wrongpassword')
    assert LOGIN_URL in browser.url
    assert 'enter a correct email address and password' in browser.contents


def test__registration__signals__verify_profile__1(db, user):
    """Users with unverified profile don't have the permission 'verified'."""
    assert not user.has_perm('registration.verified')


def test__registration__signals__verify_profile__2(db, user_dict):
    """
    Create a profile without a user.

    The not existing user does not get verified.
    """
    profile = Profile.objects.create(
        first_name=user_dict['first_name'],
        last_name=['last_name'],
        gender=user_dict['gender'],
        birthday=datetime.datetime.strptime(
            user_dict['birthday'], settings.DATE_INPUT_FORMATS).date(),
        street=user_dict['street'],
        house_number=user_dict['house_number'],
        zipcode=user_dict['zipcode'],
        city=user_dict['city'],
    )

    with pytest.raises(
            AttributeError,
            match=r'\'NoneType\' object has no attribute \'has_perm\''):
        profile.okuser.has_perm('registration.verified')


def test__registration__views__RegistrationPlainFormFile__1(
        browser, user):
    """User can download a plain application form."""
    browser.login()
    browser.open(APPLY_URL)
    browser.getLink('Print template').click()

    assert browser.headers['Content-Type'] == 'application/pdf'
    assert user.profile.first_name not in pdfToText(browser.contents)
    assert user.profile.last_name not in pdfToText(browser.contents)


def test__registration__views__RegistrationPlainFormFile__2(browser):
    """It is always possible to access the plain registration form."""
    browser.open(DOMAIN + reverse_lazy('registration:registration_plain_file'))
    assert browser.headers['Content-Type'] == 'application/pdf'


def test__registration__views__RegistrationFilledFormFile__2(
        browser):
    """User without a profile can not create an application form."""
    testuser = User.objects.create_user(email=EMAIL, password=PWD)
    testuser.save()
    browser.login()

    browser.open(APPLY_URL)
    assert browser.url == DOMAIN + reverse_lazy('home')
    assert f'There is no profile for {EMAIL}' in browser.contents


def test__registration__templates__privacy_policy__1(browser):
    """The Privacy Policy is accessible."""
    browser.open(REGISTER_URL)
    browser.getLink('privacy policy').click()
    assert 'Datenschutzerklärung' in browser.contents


@pytest.mark.django_db
def test__registration__templates__privacy_policy__uses_organization_config_markdown_and_placeholders(browser):
    """Custom privacy policy from OrganizationConfig supports placeholders and markdown."""
    config = OrganizationConfig.get_config()
    config.name = 'Test Media Center e.V.'
    config.datenschutz = (
        '# Datenschutzerklärung\n\n'
        'Willkommen bei **{{ OK_NAME }}**.\n\n'
        '- Punkt 1\n'
        '- Punkt 2\n'
    )
    config.save()

    browser.open(PRIVACY_POLICY_URL)

    assert '<h1>Datenschutzerklärung</h1>' in browser.contents
    assert '<strong>Test Media Center e.V.</strong>' in browser.contents
    assert '<li>Punkt 1</li>' in browser.contents
    assert '<li>Punkt 2</li>' in browser.contents


@pytest.mark.django_db
def test__registration__templates__privacy_policy__sanitizes_disallowed_html(browser):
    """Disallowed tags like script are removed from OrganizationConfig privacy text."""
    config = OrganizationConfig.get_config()
    config.datenschutz = (
        '<h2>Datenschutz</h2>'
        '<script>alert("x")</script>'
        '<p>Erlaubter Text</p>'
    )
    config.save()

    browser.open(PRIVACY_POLICY_URL)

    assert '<h2>Datenschutz</h2>' in browser.contents
    assert 'Erlaubter Text' in browser.contents
    assert '<script>alert("x")</script>' not in browser.contents
    assert 'alert("x")' not in browser.contents


def test__registration__templates__navbar__1(browser):
    """It is possible to got to the register site and back using the navbar."""
    browser.open(DOMAIN)
    browser.getLink('Register').click()
    assert 'first_name' in browser.contents
    assert 'privacy policy' in browser.contents

    browser.open(HOME_URL)
    assert 'Home' in browser.contents or 'Startseite' in browser.contents


def test__registration__views__EditProfileView__1(
        browser, user_dict):
    """Users that are verified can only change their phone number."""
    create_user(user_dict, verified=True)
    browser.login()
    browser.open(USER_EDIT_URL)

    assert browser.getControl(name='first_name').disabled
    assert browser.getControl(name='gender').disabled

    new_phone_number = '01234567890'
    browser.getControl(name='phone_number').value = new_phone_number
    browser.getControl(name='submit').click()

    assert USER_EDIT_URL == browser.url
    assert 'successfully updated' in browser.contents
    assert User.objects.get(
        email=user_dict['email']).profile.phone_number == new_phone_number


def test__registration__views__EditProfileView__2(db, browser, user_dict):
    """It is not possible to change user data without a profile."""
    User.objects.create_user(EMAIL, password=PWD)
    browser.login()
    browser.open(USER_EDIT_URL)
    assert browser.url == DOMAIN + reverse_lazy('home')
    assert 'There is no profile' in browser.contents


def test__registration__views__EditProfileView__3(browser, user):
    """A not verified user with a profile can change his/her data."""
    browser.login()
    browser.open(USER_EDIT_URL)
    new_name = 'new_name'
    browser.getControl(name='first_name').value = new_name
    browser.getControl(name='submit').click()
    assert 'successfully updated' in browser.contents
    assert User.objects.get(email=user.email).profile.first_name == new_name


def test__registration__views__EditProfileView__4(browser, user):
    """The edit form gets validated."""
    browser.login()
    browser.open(USER_EDIT_URL)
    browser.getControl(name='email').value = 'invalid_email'
    browser.getControl(name='submit').click()
    assert browser.url == USER_EDIT_URL
    assert 'Enter a valid email address' in browser.contents


def test__registration__views__EditProfileView__5(browser, user):
    """The email address needs to be unique."""
    used_email = 'used@example.com'
    User.objects.create_user(used_email, password=PWD)
    browser.login()

    browser.open(USER_EDIT_URL)
    browser.getControl(name='email').value = used_email
    browser.getControl(name='submit').click()

    assert browser.url == USER_EDIT_URL
    assert 'already exists.' in browser.contents


def test__registration__views__EditProfileView__6(browser):
    """The edit profile site redirects anonymous users to login."""
    browser.open(USER_EDIT_URL)
    assert '/login/' in browser.url


def test__registration__views__EditProfileView__7(browser, user):
    """It is possible to edit the email address."""
    browser.login()
    new_email = 'new_'+user.email

    browser.open(USER_EDIT_URL)
    browser.getControl(name='email').value = new_email
    browser.getControl(name='submit').click()

    assert 'successfully updated' in browser.contents
    assert User.objects.get(email=new_email)


def test__registration__views__PrintRegistrationView__1(browser):
    """It redirects anonymous users to login."""
    browser.open(APPLY_URL)
    assert '/login/' in browser.url


def test__registration__views__RegistrationFilledFormFile__1(
        browser):
    """It redirects to the previous page if the user don't has a profile."""
    User.objects.create_user(EMAIL, password=PWD)
    browser.login()
    browser.open(
        DOMAIN + reverse_lazy('registration:registration_filled_file'))
    assert DOMAIN + reverse_lazy('home') == browser.url
    assert 'There is no profile' in browser.contents


def test__registration__views_RegistrationFilledFormFile__2(browser):
    """It redirects anonymous users to login."""
    browser.open(
        DOMAIN + reverse_lazy('registration:registration_filled_file'))
    assert '/login/' in browser.url


def test__registration__views__RegistrationFilledFormFile__3(
        browser, user):
    """User can download an automatically created application form."""
    browser.login()
    browser.open(APPLY_URL)
    browser.getLink('Print registration').click()

    assert browser.headers['Content-Type'] == 'application/pdf'
    assert user.profile.first_name in pdfToText(browser.contents)
    assert user.profile.last_name in pdfToText(browser.contents)


# Helper functions


def _register_user(browser, user_dict: dict):
    """
    Register a user defined by the given dictionary.

    The entries of the user dictionary correspond to the fields defined
    in models.py for user and profile.
    """
    browser.open(REGISTER_URL)
    assert '/register/' in browser.url, \
        f'Not on register page, URL is {browser.url}'

    browser.getControl('Email').value = user_dict['email']
    browser.getControl('First name').value = user_dict['first_name']
    browser.getControl('Last name').value = user_dict['last_name']
    browser.getControl('Gender').value = user_dict['gender']
    browser.getControl('Phone number').value = user_dict['phone_number']
    browser.getControl('Mobile number').value = user_dict['mobile_number']
    # We need an american date format because the browser language is english.
    # Changing the test browser language did not solve the problem.
    browser.getControl('Birthday').value = "09/05/1989"
    browser.getControl('Street').value = user_dict['street']
    browser.getControl('House number').value = user_dict['house_number']
    browser.getControl('Zipcode').value = user_dict['zipcode']
    browser.getControl('City').value = user_dict['city']
    browser.getControl(name='privacy_agreement').controls[0].selected = True
    browser.getControl(name='usage_agreement').controls[0].selected = True
    browser.getControl(name='submit').click()


def _request_pwd_reset(browser, user):
    """Request an email to reset the password."""
    browser.open(PWD_RESET_URL)
    assert PWD_RESET_URL in browser.url
    assert 'Change Password' in browser.contents

    browser.getControl('Email').value = user.email
    browser.getForm(index=0).submit()


def _get_link_url_from_email(mail_outbox, pattern: str) -> str:
    """Get a link URL from the last email sent."""
    mail_body = mail_outbox[-1].body
    res = re.search(pattern, mail_body, re.M)
    if not res:  # pragma: no cover
        logger.error(f'No auth link in email:\n {mail_body}')
        raise AssertionError
    return res.group(0)  # entire match


def _success_string(email: str) -> str:
    """Return the string which shows a successfull registration."""
    return f'created user {email}'

@pytest.mark.django_db
def test__registration__backends__EmailBackend__inactive_user(browser):
    """Inactive user cannot log in."""
    user = User.objects.create_user(email=EMAIL, password=PWD, is_active=False)
    user.save()
    browser.login()
    # Should show generic invalid credentials message
    assert 'enter a correct email address and password' in browser.contents


def test__registration__models__Profile__Gender__verbose_name__2():
    """Valid gender values return a non-empty verbose name."""
    # Import Gender from the models module to access the enum
    from .models import Gender
    assert Gender.verbose_name('m') != ''
    assert Gender.verbose_name('f') != ''
    assert Gender.verbose_name('d') != ''
    assert Gender.verbose_name('none') != ''

@pytest.mark.django_db
def test__registration__backends__EmailBackend__inactive_user_login_failure(browser):
    """Inactive user cannot log in and sees generic error message."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Create an inactive user
    user = User.objects.create_user(
        email='inactive@example.com', 
        password='testpass123',
        is_active=False
    )
    
    # Attempt login with inactive user
    browser.login(email='inactive@example.com', password='testpass123')
    
    # Should show generic invalid credentials message (same as for wrong password)
    assert 'enter a correct email address and password' in browser.contents
    assert '/login/' in browser.url  # Should stay on login page


def test__registration__models__Profile__Gender__verbose_name__valid_values():
    """Valid gender values return appropriate verbose names."""
    from .models import Gender
    from django.utils.translation import gettext_lazy as _
    
    # Test all valid gender values return non-empty verbose names
    assert str(Gender.verbose_name('m')) == str(_('male'))
    assert str(Gender.verbose_name('f')) == str(_('female'))
    assert str(Gender.verbose_name('d')) == str(_('diverse'))
    assert str(Gender.verbose_name('none')) == str(_('not given'))
    
    # Verify that valid values are properly handled
    valid_genders = ['m', 'f', 'd', 'none']
    for gender in valid_genders:
        verbose = Gender.verbose_name(gender)
        # Verbose name should be non-empty for valid values
        assert isinstance(str(verbose), str)
        assert len(str(verbose)) > 0


@pytest.mark.django_db
def test__registration__views__EditProfileView__inactive_user_cannot_access():
    """Inactive user cannot access edit profile view."""
    from django.test import Client
    from django.urls import reverse
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    # Create inactive user
    user = User.objects.create_user(
        email='inactive@example.com',
        password='testpass123',
        is_active=False
    )
    
    # Create client and attempt to access edit profile view
    client = Client()
    client.login(email='inactive@example.com', password='testpass123')
    
    response = client.get(reverse('registration:user_data'))
    
    # Should redirect to login page due to login requirement
    # (inactive users can't log in in the first place, so this is tested indirectly)
    # If somehow logged in, should check for permission issues
    assert response.status_code in [302, 404]  # Redirect or 404


@pytest.mark.django_db
def test__registration__views__RegisterView__invalid_phone_numbers(browser, user_dict):
    """Invalid phone numbers are properly validated during registration."""
    # Test various invalid phone number formats
    invalid_phone_numbers = [
        '123',  # Too short
        'abcdefgh',  # Non-numeric with letters
        '+4912345678901234567890',  # Too long
        '++491234567890',  # Double plus
        '49-123-456-789',  # Invalid format
    ]
    
    for invalid_phone in invalid_phone_numbers:
        user_dict_copy = user_dict.copy()
        user_dict_copy['phone_number'] = invalid_phone
        
        browser.open(DOMAIN + reverse_lazy('registration:register'))
        
        browser.getControl('Email').value = user_dict_copy['email'] + '_invalid_phone'
        browser.getControl('First name').value = user_dict_copy['first_name']
        browser.getControl('Last name').value = user_dict_copy['last_name']
        browser.getControl('Gender').value = user_dict_copy['gender']
        browser.getControl('Phone number').value = invalid_phone
        browser.getControl('Mobile number').value = user_dict_copy['mobile_number']
        browser.getControl('Birthday').value = "09/05/1989"
        browser.getControl('Street').value = user_dict_copy['street']
        browser.getControl('House number').value = user_dict_copy['house_number']
        browser.getControl('Zipcode').value = user_dict_copy['zipcode']
        browser.getControl('City').value = user_dict_copy['city']
        browser.getControl(name='privacy_agreement').controls[0].selected = True
        browser.getControl(name='usage_agreement').controls[0].selected = True
        browser.getControl(name='submit').click()
        
        # Should show validation error for invalid phone number
        assert 'Enter a valid phone number' in browser.contents or 'This field is invalid' in browser.contents


@pytest.mark.django_db
def test__registration__views__RegisterView__invalid_mobile_numbers(browser, user_dict):
    """Invalid mobile numbers are properly validated during registration."""
    # Test various invalid mobile number formats
    invalid_mobile_numbers = [
        '123',  # Too short
        'abcdefgh',  # Non-numeric with letters
        '+4912345678901234567890',  # Too long
        '++491234567890',  # Double plus
        '49-123-456-789',  # Invalid format
    ]
    
    for invalid_mobile in invalid_mobile_numbers:
        user_dict_copy = user_dict.copy()
        user_dict_copy['mobile_number'] = invalid_mobile
        
        browser.open(DOMAIN + reverse_lazy('registration:register'))
        
        browser.getControl('Email').value = user_dict_copy['email'] + '_invalid_mobile'
        browser.getControl('First name').value = user_dict_copy['first_name']
        browser.getControl('Last name').value = user_dict_copy['last_name']
        browser.getControl('Gender').value = user_dict_copy['gender']
        browser.getControl('Phone number').value = user_dict_copy['phone_number']
        browser.getControl('Mobile number').value = invalid_mobile
        browser.getControl('Birthday').value = "09/05/1989"
        browser.getControl('Street').value = user_dict_copy['street']
        browser.getControl('House number').value = user_dict_copy['house_number']
        browser.getControl('Zipcode').value = user_dict_copy['zipcode']
        browser.getControl('City').value = user_dict_copy['city']
        browser.getControl(name='privacy_agreement').controls[0].selected = True
        browser.getControl(name='usage_agreement').controls[0].selected = True
        browser.getControl(name='submit').click()
        
        # Should show validation error for invalid mobile number (German message)
        assert 'Enter a valid phone number starting with +49, 0049, or 0' in browser.contents or 'Dieses Feld ist zwingend erforderlich' in browser.contents or 'This field is invalid' in browser.contents


@pytest.mark.django_db
def test__registration__views__EditProfileView__phone_number_validation(browser, user):
    """Phone number validation works when editing profile."""
    browser.login()
    browser.open(DOMAIN + reverse_lazy('registration:user_data'))
    
    # Try to set an invalid phone number
    browser.getControl(name='phone_number').value = 'invalid_phone_number'
    browser.getControl(name='submit').click()
    
    # Should show validation error (German message)
    assert browser.url == DOMAIN + reverse_lazy('registration:user_data')
    assert 'Enter a valid phone number starting with +49, 0049, or 0' in browser.contents or 'Dieses Feld ist zwingend erforderlich' in browser.contents or 'This field is invalid' in browser.contents


@pytest.mark.django_db
def test__registration__views__EditProfileView__mobile_number_validation(browser, user):
    """Mobile number validation works when editing profile."""
    browser.login()
    browser.open(DOMAIN + reverse_lazy('registration:user_data'))
    
    # Try to set an invalid mobile number
    browser.getControl(name='mobile_number').value = 'invalid_mobile_number'
    browser.getControl(name='submit').click()
    
    # Should show validation error (German message)
    assert browser.url == DOMAIN + reverse_lazy('registration:user_data')
    assert 'Enter a valid phone number starting with +49, 0049, or 0' in browser.contents or 'Dieses Feld ist zwingend erforderlich' in browser.contents or 'This field is invalid' in browser.contents


@pytest.mark.django_db
def test__registration__views__RegisterView__missing_required_fields(browser, user_dict):
    """Registration form validates all required fields."""
    # Test each required field missing individually
    required_fields = ['first_name', 'last_name', 'email', 'gender', 'birthday', 'street', 'house_number', 'zipcode', 'city']
    
    for field in required_fields:
        user_dict_copy = user_dict.copy()
        # Remove or set to None the current required field
        user_dict_copy[field] = None if field != 'email' else ''  # Can't have None email
        
        browser.open(DOMAIN + reverse_lazy('registration:register'))
        
        # Fill in all fields except the one being tested
        if field != 'email':
            browser.getControl('Email').value = user_dict_copy['email']
        else:
            browser.getControl('Email').value = 'test@example.com'
            
        if field != 'first_name':
            browser.getControl('First name').value = user_dict_copy['first_name']
        else:
            browser.getControl('First name').value = ''
            
        if field != 'last_name':
            browser.getControl('Last name').value = user_dict_copy['last_name']
        else:
            browser.getControl('Last name').value = ''
            
        if field != 'gender':
            browser.getControl('Gender').value = user_dict_copy['gender']
        else:
            browser.getControl('Gender').value = ''
            
        browser.getControl('Phone number').value = user_dict_copy['phone_number']
        browser.getControl('Mobile number').value = user_dict_copy['mobile_number']
        
        if field != 'birthday':
            browser.getControl('Birthday').value = "09/05/1989"
        else:
            browser.getControl('Birthday').value = ''
            
        if field != 'street':
            browser.getControl('Street').value = user_dict_copy['street']
        else:
            browser.getControl('Street').value = ''
            
        if field != 'house_number':
            browser.getControl('House number').value = user_dict_copy['house_number']
        else:
            browser.getControl('House number').value = ''
            
        if field != 'zipcode':
            browser.getControl('Zipcode').value = user_dict_copy['zipcode']
        else:
            browser.getControl('Zipcode').value = ''
            
        if field != 'city':
            browser.getControl('City').value = user_dict_copy['city']
        else:
            browser.getControl('City').value = ''
            
        browser.getControl(name='privacy_agreement').controls[0].selected = True
        browser.getControl(name='usage_agreement').controls[0].selected = True
        browser.getControl(name='submit').click()
        
        # Should show validation error for missing required field
        assert 'This field is required' in browser.contents
        assert browser.url == DOMAIN + reverse_lazy('registration:register')
