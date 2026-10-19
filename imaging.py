"""Photo previews and the details cameras record in photos (when and where they were taken)."""
import io
from datetime import datetime

from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 400_000_000   # phone panoramas can be huge; these are the owner's own files
THUMB_SIZE = 800

_EXIF_IFD, _GPS_IFD = 0x8769, 0x8825
_DATETIME_ORIGINAL, _DATETIME = 36867, 306


def _gps_to_deg(value, ref):
    d, m, s = (float(x) for x in value)
    deg = d + m / 60 + s / 3600
    return -deg if ref in ('S', 'W') else deg


def read_exif(img):
    """Return (taken_at, lat, lng) from an opened image; any of them may be None."""
    taken_at = lat = lng = None
    try:
        exif = img.getexif()
    except Exception:
        return None, None, None
    raw = exif.get_ifd(_EXIF_IFD).get(_DATETIME_ORIGINAL) or exif.get(_DATETIME)
    if raw:
        try:
            taken_at = datetime.strptime(str(raw).strip('\x00 '), '%Y:%m:%d %H:%M:%S')
        except ValueError:
            pass
    gps = exif.get_ifd(_GPS_IFD)
    try:
        if gps.get(2) and gps.get(4):
            lat = _gps_to_deg(gps[2], gps.get(1, 'N'))
            lng = _gps_to_deg(gps[4], gps.get(3, 'E'))
            if lat == 0 and lng == 0:
                lat = lng = None
    except (TypeError, ValueError, ZeroDivisionError):
        lat = lng = None
    return taken_at, lat, lng


def exif_from_bytes(data):
    """Read photo details from the first part of a file (they sit near the start of a JPEG)."""
    try:
        return read_exif(Image.open(io.BytesIO(data)))
    except Exception:
        return None, None, None


def make_thumb(source, dest_path):
    """Save a small JPEG preview of `source` (a path or file object). Returns (taken_at, lat, lng)."""
    with Image.open(source) as img:
        details = read_exif(img)
        img.draft('RGB', (THUMB_SIZE * 2, THUMB_SIZE * 2))   # lets big JPEGs decode at reduced size
        img = ImageOps.exif_transpose(img)
        img.thumbnail((THUMB_SIZE, THUMB_SIZE))
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        img.save(dest_path, 'JPEG', quality=82, optimize=True, progressive=True)
    return details
