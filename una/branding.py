"""Logo softvera (ugrađuje se u HTML vožnje kao data-URI)."""
import base64, io, os

_CACHE = {}


def logo_uri(width=560):
    if width in _CACHE: return _CACHE[width]
    p = os.path.join(os.path.dirname(__file__), "webui", "static", "logo_full.png")
    try:
        from PIL import Image
        im = Image.open(p).convert("RGB"); h = int(im.height * width / im.width); im = im.resize((width, h), Image.LANCZOS)
        b = io.BytesIO(); im.save(b, "PNG", optimize=True); data = b.getvalue()
    except Exception:
        data = open(p, "rb").read()
    _CACHE[width] = "data:image/png;base64," + base64.b64encode(data).decode()
    return _CACHE[width]
