"""Logo softvera (ugrađuje se u HTML vožnje kao data-URI)."""
import base64, io, os

_CACHE = {}


def logo_uri(width=560, name="logo_full.png"):
    if (width, name) in _CACHE: return _CACHE[(width, name)]
    p = os.path.join(os.path.dirname(__file__), "webui", "static", name)
    try:
        from PIL import Image
        im = Image.open(p).convert("RGBA" if name.endswith("alpha.png") else "RGB"); h = int(im.height * width / im.width); im = im.resize((width, h), Image.LANCZOS)
        b = io.BytesIO(); im.save(b, "PNG", optimize=True); data = b.getvalue()
    except Exception:
        data = open(p, "rb").read()
    _CACHE[(width, name)] = "data:image/png;base64," + base64.b64encode(data).decode()
    return _CACHE[(width, name)]


def logo_alpha_uri(width=640):
    return logo_uri(width, "logo_alpha.png")
