"""Lightweight transport images, never used to calculate desktop coordinates."""
import base64
import io
from PIL import Image


def jpeg_url(image, max_edge=None):
    if max_edge and max(image.size) > max_edge:
        image = image.copy()
        image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    image.convert('RGB').save(buf, 'JPEG', quality=88, subsampling=0)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
