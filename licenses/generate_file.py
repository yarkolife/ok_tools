from .models import License
from .models import YouthProtectionCategory
from datetime import date
from django.conf import settings
from django.http import FileResponse
from django.utils.translation import gettext as _
from fdfgen import forge_fdf
from PIL import Image, ImageOps, ImageChops, ImageEnhance
import base64
import io
import os
import subprocess
import tempfile


# find out fields using
# pdftk ./licenses/files/2017_Antrag_Einzelgenehmigung_ausfuellbar.pdf dump_data_fields

PDFTK_CANDIDATES = ['/opt/homebrew/bin/pdftk', '/usr/bin/pdftk']
PDFTK = None

for candidate in PDFTK_CANDIDATES:
    if os.path.isfile(candidate):
        PDFTK = candidate

if PDFTK is None:
    raise SystemError(f'pdftk not found in {PDFTK_CANDIDATES}')


def choose(value):
    """Convert boolean-like value into 'yes', 'no', or 'unbekannt'.

    Args:
        value: Any input value to evaluate.

    Returns:
        str: 'yes' if truthy, 'no' if falsy, 'unbekannt' if None.
    """
    if value is None:
        return 'unbekannt'
    if value:
        return 'yes'
    return 'no'


def val(value):
    """Return the value if not empty, otherwise an empty string.

    Args:
        value: Any input value.

    Returns:
        str: The input value or an empty string.
    """
    if value:
        return value
    return ''


def generate_license_file(lr: License) -> FileResponse:
    """Generate a License as pdf file.

    As template the '2017_Antrag_Einzelgenehmigung_ausfuellbar.pdf' from
    https://www.okmq.de/images/Formulare/2017_Antrag_Einzelgenehmigung_ausfuellbar.pdf
    is used.
    The function assumes that the License has a user with profile.
    """
    user = lr.profile.okuser
    profile = lr.profile

    # Get email safely - user or user.email can be None
    email = ''
    if user and user.email:
        email = user.email

    # Get media authority full name safely (fallback to name if full_name is not set)
    media_authority_name = ''
    if profile.media_authority:
        if profile.media_authority.full_name:
            media_authority_name = profile.media_authority.full_name
        elif profile.media_authority.name:
            media_authority_name = profile.media_authority.name

    # Get license creation date (fallback to today if not set)
    license_date = lr.created_at.date() if lr.created_at else date.today()

    fields = [
        ('name', f'{val(profile.first_name)} {val(profile.last_name)}'),
        ('street', f'{val(profile.street)} {val(profile.house_number)}'),
        ('zip_city', f'{val(profile.zipcode)} {val(profile.city)}'),
        ('phone', f'{val(profile.phone_number)} {val(profile.mobile_number)}'),
        ('email', val(email)),
        ('ok_name', val(media_authority_name)),
        ('title', val(lr.title)),
        ('subtitle', val(lr.subtitle)),
        ('length', val(lr.duration)),
        ('repetitions_allowed', choose(lr.repetitions_allowed)),
        ('media_authority_exchange_allowed', choose(lr.media_authority_exchange_allowed)),
        ('media_authority_exchange_allowed_other_states', choose(lr.media_authority_exchange_allowed_other_states)),
        ('store_in_ok_media_library', choose(lr.store_in_ok_media_library)),
        ('youth_protection_necessary', choose(lr.youth_protection_necessary)),
        ('youth_protection_category', str(lr.youth_protection_category)),
        ('city_date_member', f'{val(profile.city)} {license_date.strftime(settings.DATE_INPUT_FORMATS)}')
    ]

    with tempfile.TemporaryDirectory() as tmpdirname:
        fdf = forge_fdf("", fields, [], [], [])
        with open(os.path.join(tmpdirname, "data.fdf"), "wb") as fdf_file:
            fdf_file.write(fdf)
        
        # Fill the form
        subprocess.run(
            [PDFTK,
            'licenses/files/2017_Antrag_Einzelgenehmigung_ausfuellbar.pdf',
            'fill_form',
            os.path.join(tmpdirname, "data.fdf"),
            'output',
            os.path.join(tmpdirname, "filled.pdf")])
        
        # Add signature if present
        if lr.signature:
            try:
                # Decode signature image
                # Remove header if present (e.g. "data:image/png;base64,")
                if ',' in lr.signature:
                    header, encoded = lr.signature.split(',', 1)
                else:
                    encoded = lr.signature
                
                signature_data = base64.b64decode(encoded)
                signature_img = Image.open(io.BytesIO(signature_data))
                
                # Convert to RGBA if needed
                if signature_img.mode != 'RGBA':
                    signature_img = signature_img.convert('RGBA')
                
                # Trim whitespace around signature
                # Create a box around non-transparent pixels
                bbox = signature_img.getbbox()
                if bbox:
                    signature_img = signature_img.crop(bbox)
                
                # Keep the signature image as-is for PDF insertion (no additional strokes/guide artifacts).
                # If needed, only a mild contrast boost can be applied here without introducing extra lines.
                # Convert to grayscale for contrast boost, then restore original alpha.
                alpha = signature_img.split()[3] if signature_img.mode == 'RGBA' else None
                gray = signature_img.convert('L')
                enhancer = ImageEnhance.Contrast(gray)
                gray = enhancer.enhance(1.2)
                if alpha:
                    signature_img = Image.merge('RGBA', (gray, gray, gray, alpha))
                else:
                    signature_img = gray.convert('RGBA')
                
                # Create A4 pages for stamp PDF.
                # Use higher DPI to avoid pixelation when stamping the signature into the PDF.
                # PDF points are based on 72 DPI. We render at STAMP_DPI and save with that resolution
                # so the physical page size stays A4 while raster detail increases.
                STAMP_DPI = 144  # 2x of 72 DPI (faster, still smoother than 72)
                scale = STAMP_DPI / 72.0
                a4_width, a4_height = int(round(595 * scale)), int(round(842 * scale))
                
                # Page 1: Transparent
                page1 = Image.new('RGBA', (a4_width, a4_height), (255, 255, 255, 0))
                
                # Page 2: Transparent with signature
                page2 = Image.new('RGBA', (a4_width, a4_height), (255, 255, 255, 0))
                
                # Resize signature to fit in form field right of "Unterschrift"
                # Calculate new size maintaining aspect ratio
                sig_width, sig_height = signature_img.size
                aspect_ratio = sig_width / sig_height
                # Width to fit in form field without exceeding boundaries (in PDF points)
                target_width = int(round(125 * scale))
                target_height = int(target_width / aspect_ratio)
                # Limit height to prevent signature from being too tall (in PDF points)
                max_height = int(round(40 * scale))
                if target_height > max_height:
                    target_height = max_height
                    target_width = int(target_height * aspect_ratio)
                signature_img = signature_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                
                # Position signature right of "Unterschrift" on page 2
                # X: positioned to the right of "Unterschrift" text, Y: aligned with date line
                # Adjusted coordinates to fit within form boundaries
                page2.paste(
                    signature_img,
                    (int(round(360 * scale)), int(round(590 * scale))),
                    signature_img,
                )
                
                # Page 3: Transparent
                page3 = Image.new('RGBA', (a4_width, a4_height), (255, 255, 255, 0))
                
                # Save as PDF
                stamp_path = os.path.join(tmpdirname, "stamp.pdf")
                page1.save(
                    stamp_path,
                    save_all=True,
                    append_images=[page2, page3],
                    resolution=STAMP_DPI,
                )
                
                # Stamp the filled PDF
                subprocess.run(
                    [PDFTK,
                    os.path.join(tmpdirname, "filled.pdf"),
                    'multistamp',
                    stamp_path,
                    'output',
                    os.path.join(tmpdirname, "output.pdf")])
                
            except Exception as e:
                # If signature processing fails, just return the filled PDF
                print(f"Signature processing failed: {e}")
                # Copy filled.pdf to output.pdf
                import shutil
                shutil.copy(os.path.join(tmpdirname, "filled.pdf"), os.path.join(tmpdirname, "output.pdf"))
        else:
            # No signature, just rename filled to output
            os.rename(os.path.join(tmpdirname, "filled.pdf"), os.path.join(tmpdirname, "output.pdf"))

        with open(os.path.join(tmpdirname, "output.pdf"), "rb") as output:
            result = output.read()

    apl_stream = io.BytesIO()
    apl_stream.write(result)
    apl_stream.seek(0)

    return FileResponse(apl_stream, filename=_('license.pdf'))
