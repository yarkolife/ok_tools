from .models import License
from .models import YouthProtectionCategory
from datetime import date
from django.conf import settings
from django.http import FileResponse
from django.utils.translation import gettext as _
from fdfgen import forge_fdf
from PIL import Image, ImageOps, ImageChops, ImageEnhance, ImageDraw, ImageFont
import base64
import io
import os
import re
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


def normalize_filename(title):
    """Normalize title for use in filename.
    
    Replaces spaces with _, converts umlauts to digraphs (ü→ue, ö→oe, ä→ae),
    and removes all non-alphanumeric characters except _.
    
    Args:
        title: Title string to normalize.
        
    Returns:
        str: Normalized filename-safe string.
    """
    if not title:
        return ''
    
    # Convert to string
    text = str(title)
    
    # Replace umlauts with digraphs
    text = text.replace('ü', 'ue').replace('Ü', 'Ue')
    text = text.replace('ö', 'oe').replace('Ö', 'Oe')
    text = text.replace('ä', 'ae').replace('Ä', 'Ae')
    text = text.replace('ß', 'ss')
    
    # Replace spaces with underscores
    text = text.replace(' ', '_')
    
    # Remove all non-alphanumeric characters except underscores
    text = re.sub(r'[^a-zA-Z0-9_]', '', text)
    
    # Remove multiple consecutive underscores
    text = re.sub(r'_+', '_', text)
    
    # Remove leading/trailing underscores
    text = text.strip('_')
    
    return text


def generate_license_pdf_bytes(lr: License) -> bytes:
    """Generate license PDF as bytes (no HTTP response).

    Reuses the same logic as generate_license_file. Use for uploads or
    programmatic access. Assumes the license has a profile.
    """
    return _build_license_pdf_bytes(lr)


def _build_license_pdf_bytes(lr: License) -> bytes:
    """Build license PDF bytes. Used by generate_license_file and generate_license_pdf_bytes."""
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
        
        # Create A4 pages for stamp PDF with license number
        # Use higher DPI to avoid pixelation when stamping into the PDF
        STAMP_DPI = 144  # 2x of 72 DPI (faster, still smoother than 72)
        scale = STAMP_DPI / 72.0
        a4_width, a4_height = int(round(595 * scale)), int(round(842 * scale))
        
        # Page 1: Transparent with license number
        page1 = Image.new('RGBA', (a4_width, a4_height), (255, 255, 255, 0))
        draw1 = ImageDraw.Draw(page1)
        
        # Page 2: Transparent with license number
        page2 = Image.new('RGBA', (a4_width, a4_height), (255, 255, 255, 0))
        draw2 = ImageDraw.Draw(page2)
        
        # Add license number at the top of pages 1 and 2
        license_number_text = str(lr.number)
        font_size = int(round(18 * scale))
        
        # Try to use a default font, fallback to default if not available
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except (OSError, IOError):
                font = ImageFont.load_default()
        
        # Get text dimensions for positioning
        bbox1 = draw1.textbbox((0, 0), license_number_text, font=font)
        text_width = bbox1[2] - bbox1[0]
        text_height = bbox1[3] - bbox1[1]
        
        # Padding around text for frame
        padding = int(round(8 * scale))
        
        # Position at top center with small margin
        x_pos = int((a4_width - text_width) / 2)
        y_pos = int(round(20 * scale))
        
        # Frame coordinates
        frame_x1 = x_pos - padding
        frame_y1 = y_pos - padding
        frame_x2 = x_pos + text_width + padding
        frame_y2 = y_pos + text_height + padding
        
        # Draw frame and license number on page 1
        draw1.rectangle([frame_x1, frame_y1, frame_x2, frame_y2], outline=(0, 0, 0, 255), width=int(round(2 * scale)))
        draw1.text((x_pos, y_pos), license_number_text, fill=(0, 0, 0, 255), font=font)
        
        # Draw frame and license number on page 2
        draw2.rectangle([frame_x1, frame_y1, frame_x2, frame_y2], outline=(0, 0, 0, 255), width=int(round(2 * scale)))
        draw2.text((x_pos, y_pos), license_number_text, fill=(0, 0, 0, 255), font=font)
        
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
                
            except Exception as e:
                # If signature processing fails, continue without signature
                print(f"Signature processing failed: {e}")
        
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

        with open(os.path.join(tmpdirname, "output.pdf"), "rb") as output:
            result = output.read()

    return result


def generate_license_file(lr: License, filename=None, as_attachment=False) -> FileResponse:
    """Generate a License as pdf file.

    As template the '2017_Antrag_Einzelgenehmigung_ausfuellbar.pdf' from
    https://www.okmq.de/images/Formulare/2017_Antrag_Einzelgenehmigung_ausfuellbar.pdf
    is used. The function assumes that the License has a user with profile.
    """
    result = _build_license_pdf_bytes(lr)
    apl_stream = io.BytesIO(result)
    apl_stream.seek(0)
    if filename:
        return FileResponse(apl_stream, filename=filename, as_attachment=as_attachment)
    return FileResponse(apl_stream, filename=_('license.pdf'), as_attachment=as_attachment)
