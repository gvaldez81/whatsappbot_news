# processors/logo.py
from PIL import Image
from . import ensure_rgba, ensure_rgb, open_image

def _place_position(base_size, overlay_size, position, margin):
    """
    Calcula la posición (x, y) donde colocar el logo según config.
    """
    bw, bh = base_size
    ow, oh = overlay_size
    m = margin
    pos = position.lower()

    if pos == "top-left":
        return (m, m)
    if pos == "top-right":
        return (bw - ow - m, m)
    if pos == "bottom-left":
        return (m, bh - oh - m)
    if pos == "bottom-right":
        return (bw - ow - m, bh - oh - m)
    # fallback → centro
    return ((bw - ow) // 2, (bh - oh) // 2)

def apply(img, config):
    """
    Superpone un logo sobre la imagen base.

    Config soportada:
      - logo_file: ruta del PNG del logo (default: assets/overlays/logo.png)
      - logo_position: top-left | top-right | bottom-left | bottom-right | center
      - logo_scale_ratio: factor relativo a la altura de la imagen base (default: 0.2)
      - logo_margin: margen en px desde el borde (default: 20)
    """
    logo_path = config.get("logo_file", "assets/overlays/logo.png")
    position = config.get("logo_position", "bottom-right")
    scale_ratio = float(config.get("logo_scale_ratio", 0.2))
    margin = int(config.get("logo_margin", 20))

    base = ensure_rgba(img)
    overlay = open_image(logo_path).convert("RGBA")

    # Escalado relativo a la ALTURA de la imagen base
    bw, bh = base.size
    target_h = max(1, int(bh * scale_ratio))
    target_w = int(overlay.width * (target_h / overlay.height))
    overlay = overlay.resize((target_w, target_h), Image.LANCZOS)

    # Posición calculada
    x, y = _place_position((bw, bh), (overlay.width, overlay.height), position, margin)

    out = base.copy()
    out.alpha_composite(overlay, (x, y))
    return ensure_rgb(out)