# processors/big_text.py
# Renderiza texto grande sobre una imagen (caption "big ...")

from PIL import Image, ImageDraw, ImageFont

def _safe_truetype(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont):
    """Devuelve (ancho, alto) de un texto con la fuente dada."""
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    return font.getsize(text)

def _wrap_text(text: str, font, max_width: int, draw: ImageDraw.ImageDraw) -> str:
    words = text.split()
    if not words:
        return ""
    lines, current = [], words[0]
    for w in words[1:]:
        test_line = f"{current} {w}"
        w_width, _ = _text_size(draw, test_line, font)
        if w_width <= max_width:
            current = test_line
        else:
            lines.append(current)
            current = w
    lines.append(current)
    return "\n".join(lines)

def apply(base_img, caption_text: str, cfg: dict):
    """
    Aplica texto grande sobre la imagen base.
    cfg puede incluir:
      - font: ruta a la fuente
      - size: tamaño de fuente
      - color: [r,g,b]
      - stroke_color: [r,g,b]
      - stroke_width: int
      - align: "center"|"left"|"right"
      - margin_x, margin_y
      - max_width_ratio
      - line_spacing
    """
    img = base_img.copy()
    draw = ImageDraw.Draw(img)

    font_path = cfg.get("font", "assets/fonts/Impact.ttf")
    size = int(cfg.get("size", 96))
    font = _safe_truetype(font_path, size)

    color = tuple(cfg.get("color", [255, 255, 255]))
    stroke_color = tuple(cfg.get("stroke_color", [0, 0, 0]))
    stroke_width = int(cfg.get("stroke_width", 3))
    align = cfg.get("align", "center")

    margin_x = int(cfg.get("margin_x", 50))
    margin_y = int(cfg.get("margin_y", 50))
    max_width_ratio = float(cfg.get("max_width_ratio", 0.9))
    line_spacing = int(cfg.get("line_spacing", 10))

    max_width = int(img.width * max_width_ratio)
    wrapped = _wrap_text(caption_text.strip(), font, max_width, draw)

    # Calcular altura total
    lines = wrapped.split("\n")
    total_h = 0
    for line in lines:
        _, h = _text_size(draw, line, font)
        total_h += h + line_spacing
    total_h -= line_spacing

    # Posición inicial
    y = margin_y + (img.height - 2*margin_y - total_h) // 2

    for line in lines:
        w, h = _text_size(draw, line, font)
        if align == "center":
            x = (img.width - w) // 2
        elif align == "right":
            x = img.width - margin_x - w
        else:
            x = margin_x
        draw.text((x, y), line, font=font, fill=color,
                  stroke_width=stroke_width, stroke_fill=stroke_color)
        y += h + line_spacing

    return img
