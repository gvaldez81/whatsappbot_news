# processors/watermark.py
from PIL import Image, ImageEnhance
from . import ensure_rgba, ensure_rgb, open_image

def _apply_opacity(img: Image.Image, opacity: float) -> Image.Image:
    """
    Ajusta la opacidad de una imagen RGBA.
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    alpha = img.split()[3]
    alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
    img.putalpha(alpha)
    return img

def apply(img, config):
    """
    Superpone una marca de agua sobre la imagen base.

    Config soportada:
      - watermark_file: ruta del PNG de la marca de agua (default: assets/overlays/watermark.png)
      - watermark_opacity: opacidad global (0.0–1.0, default: 0.3)
      - watermark_tile: si True, repite en mosaico; si False, centra
      - watermark_scale_ratio: factor relativo al ancho de la imagen base (default: 0.25)
    """
    wm_path = config.get("watermark_file", "assets/overlays/watermark.png")
    opacity = float(config.get("watermark_opacity", 0.3))
    tile = bool(config.get("watermark_tile", False))
    scale_ratio = float(config.get("watermark_scale_ratio", 0.25))

    base = ensure_rgba(img)
    wm = open_image(wm_path).convert("RGBA")

    # Escalado relativo al ancho de la imagen base
    bw, bh = base.size
    target_w = max(1, int(bw * scale_ratio))
    target_h = int(wm.height * (target_w / wm.width))
    wm = wm.resize((target_w, target_h), Image.LANCZOS)

    # Aplicar opacidad
    wm = _apply_opacity(wm, opacity)

    out = base.copy()

    if tile:
        # Repetir en mosaico
        for y in range(0, bh, wm.height + 50):
            for x in range(0, bw, wm.width + 50):
                out.alpha_composite(wm, (x, y))
    else:
        # Centrado
        x = (bw - wm.width) // 2
        y = (bh - wm.height) // 2
        out.alpha_composite(wm, (x, y))

    return ensure_rgb(out)
