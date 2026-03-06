from .models import License
from .models import YouthProtectionCategory
from datetime import date
from django.conf import settings
from django.http import FileResponse
from django.utils.translation import gettext as _
from fdfgen import forge_fdf
from PIL import Image, ImageOps, ImageChops, ImageEnhance, ImageDraw, ImageFilter, ImageFont
from PyPDF2 import PdfReader
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


def _legacy_signature_to_image(signature_value):
    """Decode legacy data-url/base64 signature into RGBA image."""
    if not signature_value:
        return None

    if ',' in signature_value:
        _, encoded = signature_value.split(',', 1)
    else:
        encoded = signature_value

    signature_data = base64.b64decode(encoded)
    image = Image.open(io.BytesIO(signature_data))
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    return image


def _signature_points_to_image(signature_points, width=1000, height=375):
    """Render signature_pad point groups to transparent image."""
    if not signature_points or not isinstance(signature_points, list):
        return None

    image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)

    for group in signature_points:
        points = group.get('points', []) if isinstance(group, dict) else []
        if len(points) == 1:
            p = points[0]
            x = int(float(p.get('x', 0)))
            y = int(float(p.get('y', 0)))
            draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=(0, 0, 0, 255))
            continue

        for idx in range(1, len(points)):
            p1 = points[idx - 1]
            p2 = points[idx]
            x1 = int(float(p1.get('x', 0)))
            y1 = int(float(p1.get('y', 0)))
            x2 = int(float(p2.get('x', 0)))
            y2 = int(float(p2.get('y', 0)))
            pressure = p2.get('pressure', 0.5)
            try:
                width_px = max(3, min(8, int(pressure * 7)))
            except (TypeError, ValueError):
                width_px = 4
            draw.line((x1, y1, x2, y2), fill=(0, 0, 0, 255), width=width_px)

    return image


def _svg_signature_to_image(signature_svg):
    """Convert SVG signature to RGBA image using cairosvg if available."""
    if not signature_svg or not isinstance(signature_svg, str):
        return None
    if '<svg' not in signature_svg:
        return None

    try:
        from cairosvg import svg2png
    except Exception:
        return None

    try:
        png_bytes = svg2png(bytestring=signature_svg.encode('utf-8'))
        image = Image.open(io.BytesIO(png_bytes))
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        return image
    except Exception:
        return None


def _resolve_signature_image(lr):
    """Return best available signature image, preferring SVG and biometric points."""
    image = _svg_signature_to_image(getattr(lr, 'signature_svg', None))
    if image:
        return image

    image = _signature_points_to_image(getattr(lr, 'signature_points', None))
    if image:
        return image

    return _legacy_signature_to_image(getattr(lr, 'signature', None))


def _enhance_signature_visibility(signature_img):
    """Make signature strokes darker and a bit thicker for PDF readability."""
    if signature_img.mode != 'RGBA':
        signature_img = signature_img.convert('RGBA')

    alpha = signature_img.split()[3]
    if alpha.getbbox() is None:
        return signature_img

    boosted_alpha = alpha.point(lambda a: 0 if a < 6 else min(255, int(a * 2.8)))
    boosted_alpha = boosted_alpha.filter(ImageFilter.MaxFilter(3))

    strong_black = Image.new('RGBA', signature_img.size, (0, 0, 0, 0))
    strong_black.putalpha(boosted_alpha)
    return strong_black


def _detect_signature_position(pdf_path, scale):
    """Detect signature widget rectangle and return paste coordinates for PIL.

    Returns tuple (x, y, width, height) in scaled pixels or None.
    """
    try:
        reader = PdfReader(pdf_path)
        if len(reader.pages) < 2:
            return None

        page = reader.pages[1]
        annots = page.get('/Annots')
        if not annots:
            return None

        for annot_ref in annots:
            annot = annot_ref.get_object()
            field_type = str(annot.get('/FT', ''))
            field_name = str(annot.get('/T', '')).lower()
            if field_type != '/Sig' and 'sign' not in field_name and 'unterschrift' not in field_name:
                continue

            rect = annot.get('/Rect')
            if not rect or len(rect) != 4:
                continue

            x0 = float(rect[0])
            y0 = float(rect[1])
            x1 = float(rect[2])
            y1 = float(rect[3])
            width_pt = max(1.0, x1 - x0)
            height_pt = max(1.0, y1 - y0)

            page_height_pt = float(page.mediabox.top - page.mediabox.bottom)
            top_y_pt = page_height_pt - y1

            return (
                int(round(x0 * scale)),
                int(round(top_y_pt * scale)),
                int(round(width_pt * scale)),
                int(round(height_pt * scale)),
            )
    except Exception:
        return None

    return None


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
        
        # Add signature if present (SVG/points preferred, legacy PNG fallback)
        signature_img = _resolve_signature_image(lr)
        if signature_img:
            try:
                # Trim whitespace around signature
                # Create a box around non-transparent pixels
                bbox = signature_img.getbbox()
                if bbox:
                    signature_img = signature_img.crop(bbox)
                
                signature_img = _enhance_signature_visibility(signature_img)
                
                # Try AcroForm signature field placement first (if available)
                detected_position = _detect_signature_position(
                    os.path.join(tmpdirname, 'filled.pdf'),
                    scale,
                )

                # Resize signature to fit in form field right of "Unterschrift"
                # Calculate new size maintaining aspect ratio
                sig_width, sig_height = signature_img.size
                aspect_ratio = sig_width / sig_height
                if detected_position:
                    _, _, detected_width, detected_height = detected_position
                    target_width = max(1, detected_width)
                    max_height = max(1, detected_height)
                else:
                    target_width = int(round(125 * scale))
                    max_height = int(round(50 * scale))

                target_height = int(target_width / aspect_ratio)
                if target_height > max_height:
                    target_height = max_height
                    target_width = int(target_height * aspect_ratio)
                signature_img = signature_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                
                # Position signature: detected field first, fallback to legacy fixed coordinates.
                if detected_position:
                    detected_x, detected_y, _, _ = detected_position
                    paste_x = detected_x
                    paste_y = detected_y
                else:
                    paste_x = int(round(360 * scale))
                    paste_y = int(round(590 * scale))

                page2.paste(
                    signature_img,
                    (paste_x, paste_y),
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
