from .models import OKUser as User
from .models import Profile
from datetime import date
from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.template.loader import render_to_string
from django.utils.translation import gettext as _
from fdfgen import forge_fdf
import io
import logging
import os
import subprocess
import tempfile


# Search for the pdftk executable among possible candidates
PDFTK_CANDIDATES = ['/opt/homebrew/bin/pdftk', '/usr/bin/pdftk', 'C:\\Program Files (x86)\\PDFtk Server\\bin\\pdftk.exe']
PDFTK = next((c for c in PDFTK_CANDIDATES if os.path.isfile(c)), None)
if not PDFTK:
    raise RuntimeError(f'pdftk not found in {PDFTK_CANDIDATES}')

def val(value):
    """Return the value if set, otherwise an empty string."""
    if value:
        return value
    return ''

def _f_number(p):
    """Return a string representation of a number or a placeholder if the value is missing."""
    return str(p) if p else '     -     '

def generate_registration_form_html(user: User, profile: Profile) -> HttpResponse:
    """Generate a registration form in HTML format.
    
    This function generates an HTML registration form based on the
    Nutzerkartei template and fills it with user data.
    
    Returns:
        HttpResponse: A response containing the filled-out HTML form.
    """
    # Get media authority name
    media_authority_name = 'Offenen Kanals Magdeburg'
    if profile.media_authority:
        if profile.media_authority.full_name:
            media_authority_name = profile.media_authority.full_name
        elif profile.media_authority.name:
            media_authority_name = profile.media_authority.name
    
    # Format date
    today = date.today()
    date_str = today.strftime('%d.%m.%Y')
    
    # Format birthday
    birthday_str = profile.birthday.strftime('%d.%m.%Y') if profile.birthday else ''
    
    # Format phone numbers
    phone_private = val(profile.phone_number)
    phone_service = val(profile.mobile_number)
    
    # Format address
    zip_city = f'{val(profile.zipcode)} {val(profile.city)}'
    street = f'{val(profile.street)} {val(profile.house_number)}'
    
    # Format email
    email = getattr(user, 'email', '') or ''
    
    # Format ID number
    ausweisnr = val(profile.ausweisnummer)
    
    # Context for template
    context = {
        'first_name': val(profile.first_name),
        'last_name': val(profile.last_name),
        'street': street,
        'zip_city': zip_city,
        'phone_private': phone_private,
        'phone_service': phone_service,
        'email': email,
        'ausweisnr': ausweisnr,
        'birthday': birthday_str,
        'media_authority_name': media_authority_name,
        'city': val(profile.city),
        'date': date_str,
    }
    
    # Render template
    html_content = render_to_string('registration/nutzerkartei_form.html', context)
    
    # Return HTML response
    response = HttpResponse(html_content, content_type='text/html; charset=utf-8')
    return response

def generate_registration_form_text(user: User, profile: Profile) -> FileResponse:
    """Generate a registration form in text format.
    
    This function generates a plain text registration form based on the
    Nutzerkartei template and fills it with user data.
    
    Returns:
        FileResponse: A response containing the filled-out text form.
    """
    # Get media authority name
    media_authority_name = 'Offenen Kanals Magdeburg'
    if profile.media_authority:
        if profile.media_authority.full_name:
            media_authority_name = profile.media_authority.full_name
        elif profile.media_authority.name:
            media_authority_name = profile.media_authority.name
    
    # Format date
    today = date.today()
    date_str = today.strftime('%d.%m.%Y')
    
    # Format birthday
    birthday_str = profile.birthday.strftime('%d.%m.%Y') if profile.birthday else ''
    
    # Format phone numbers
    phone_private = val(profile.phone_number)
    phone_service = val(profile.mobile_number)
    
    # Format address
    zip_city = f'{val(profile.zipcode)} {val(profile.city)}'
    street = f'{val(profile.street)} {val(profile.house_number)}'
    
    # Format email
    email = getattr(user, 'email', '') or ''
    
    # Format ID number
    ausweisnr = val(profile.ausweisnummer)
    
    # Build the text form - matching the original format
    form_text = f"""Nutzerkartei (Die mit einem * versehen Angaben sind freiwillig und dienen uns zu statistischen Zwecken)
Vorname: {val(profile.first_name):<15} Straße: {street:<15} Tel.privat: {phone_private:<15} E-mail: {email:<20} Ausweisnr: {ausweisnr}
Name: {val(profile.last_name):<15} PLZ/Ort: {zip_city:<15} Tel.dienstlich: {phone_service:<15} Beruf*: {'':<20} Geb.Datum: {birthday_str}

Mit der Speicherung der auf der Nutzerkartei angegebenen personenbezogenen Daten in die Nutzerkartei des {media_authority_name} bin ich einverstanden. Mit ist bekannt, dass ich die erteilte Einwilligung ohne Angabe von Gründen jederzeit widerrufen kann. Die Speicherung der personenbezogenen Daten erfolgt lediglich zur Sicherung und Vereinfachung des Informationsaustausches zwischen Offenem Kanal und Nutzer. Die gespeicherten Daten unterliegen dem Datenschutz nach den Bestimmungen des Landesschutzgesetzes. Eine Weiterleitung der Daten an Dritte ist ausgeschlossen.  Ich bin darauf hingewiesen worden, dass eine Ablehnung des Einverständnisses zur Speicherung der angegebenen personenbezogenen Daten keine Nachteile für den gleichberechtigten Zugang zum {media_authority_name} entstehen lässt.

Ort: {val(profile.city):<15} Datum: {date_str:<15} Unterschrift: 

Mit der Archivierung meiner Beiträge im {media_authority_name} und der Verwendung der Beiträge zum Zwecke der Öffentlichkeitsarbeit bin ich einverstanden: ja    nein 

Folgend aufgeführte Formblätter habe ich zur Kenntnis genommen: Nutzungsordnung  Zitatrecht, Werbeverbot 

Ort: {val(profile.city):<15} Datum: {date_str:<15} Unterschrift: 
"""
    
    # Return the text as a FileResponse
    text_bytes = form_text.encode('utf-8')
    text_stream = io.BytesIO(text_bytes)
    text_stream.seek(0)
    return FileResponse(text_stream, filename=str(_('registration_form.txt')), content_type='text/plain; charset=utf-8')

def _get_pdf_field_mapping(user: User, profile: Profile, pdf_filename: str) -> list:
    """Get field mapping for the specified PDF template.
    
    Args:
        user: User instance
        profile: Profile instance
        pdf_filename: Name of the PDF template file
        
    Returns:
        List of (field_name, value) tuples for PDF form filling
    """
    today = date.today()
    today_str = today.strftime('%d.%m.%Y')
    birthday_str = profile.birthday.strftime('%d.%m.%Y') if profile.birthday else ''
    
    # Format address fields
    zip_city = f'{val(profile.zipcode)} {val(profile.city)}'
    street_full = f'{val(profile.street)} {val(profile.house_number)}'
    
    # Determine template type and create appropriate mapping
    if pdf_filename == 'Nutzerkartei.pdf':
        # German field names (original template)
        fields = [
            ('Vorname', val(profile.first_name)),
            ('Name', val(profile.last_name)),
            ('Straße', street_full),
            ('PLZOrt', zip_city),
            ('Telpriv', _f_number(profile.phone_number)),
            ('Teldienst', _f_number(profile.mobile_number)),
            ('Email', getattr(user, 'email', '') or ''),
            ('Ausweisnr', val(profile.ausweisnummer)),
            ('GebDatum', birthday_str),
            ('Ort1', val(profile.city)),
            ('Datum1', today_str),
            ('Unterschrift1', ''),
            ('Ort2', val(profile.city)),
            ('Datum2', today_str),
            ('Unterschrift2', ''),
            ('Beruf', ''),  # Optional field, usually empty
        ]
    elif pdf_filename == 'Nutzerkartei_Anmeldung_2022_n.pdf':
        # English field names (newer template)
        fields = [
            ('first_name', val(profile.first_name)),
            ('last_name', val(profile.last_name)),
            ('street', street_full),
            ('zip_city', zip_city),
            ('phone', _f_number(profile.phone_number)),
            ('mobile', _f_number(profile.mobile_number)),
            ('email', getattr(user, 'email', '') or ''),
            ('birthday', birthday_str),
            ('city_date_member', f'{val(profile.city)} {today_str}'),
            ('anrede', ''),  # Optional: salutation (Mr/Mrs)
            ('titel', ''),   # Optional: title
            ('Signatur3', ''),  # Signature field
        ]
    else:
        # Default: try English field names (backwards compatible)
        # This handles any other templates that might use English names
        fields = [
            ('first_name', val(profile.first_name)),
            ('last_name', val(profile.last_name)),
            ('zip_city', zip_city),
            ('street', street_full),
            ('birthday', birthday_str),
            ('phone', _f_number(profile.phone_number)),
            ('mobile', _f_number(profile.mobile_number)),
            ('email', getattr(user, 'email', '') or ''),
            ('city_date_member', f'{val(profile.city)} {today_str}')
        ]
    
    return fields

def generate_registration_form(user: User, profile: Profile) -> FileResponse:
    """Generate a registration form in PDF format.

    This function uses the PDF template specified in REGISTRATION_FORM_PDF
    setting and fills it with user data. Supports multiple PDF templates:
      - Nutzerkartei.pdf (German field names)
      - Nutzerkartei_Anmeldung_2022_n.pdf (English field names)

    Returns:
        FileResponse: A response containing the filled-out PDF form.
    """
    # Path to the PDF template - use config or fallback to env/default
    from .config import get_registration_form_pdf
    pdf_filename = str(get_registration_form_pdf())
    template_pdf = os.path.join(str(settings.BASE_DIR), 'files', pdf_filename)
    if not os.path.isfile(template_pdf):
        raise FileNotFoundError(f'PDF template not found: {template_pdf}')

    # Get field mapping based on template
    fields = _get_pdf_field_mapping(user, profile, pdf_filename)

    # Create a temporary directory for the FDF file and output PDF
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Generate FDF data
        fdf_data = forge_fdf("", fields, [], [], [])
        fdf_path = os.path.join(tmpdirname, "data.fdf")
        with open(fdf_path, "wb") as fdf_file:
            fdf_file.write(fdf_data)

        # Define the path for the output PDF
        output_pdf = os.path.join(tmpdirname, "output.pdf")

        # Run pdftk to fill out the form
        try:
            result = subprocess.run(
                [PDFTK, template_pdf, 'fill_form', fdf_path, 'output', output_pdf, 'flatten'],
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            # If pdftk fails, it might be because the PDF doesn't have form fields
            # In this case, fall back to HTML form
            error_msg = e.stderr if e.stderr else str(e)
            logger = logging.getLogger(__name__)
            logger.warning(f'pdftk failed: {error_msg}. Falling back to HTML form.')
            # Return HTML form instead
            return generate_registration_form_html(user, profile)

        # Read the completed PDF file
        with open(output_pdf, "rb") as pdf_file:
            pdf_result = pdf_file.read()

    # Return the PDF as a FileResponse
    pdf_stream = io.BytesIO(pdf_result)
    pdf_stream.seek(0)
    return FileResponse(pdf_stream, filename=str(_('registration_form.pdf')))
