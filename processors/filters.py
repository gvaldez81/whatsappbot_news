from PIL import Image, ImageDraw, ImageFilter

def apply_vignette(img: Image.Image, intensity: float = 0.5) -> Image.Image:
    w, h = img.size
    vignette = Image.new('L', (w, h), color=0)
    draw = ImageDraw.Draw(vignette)

    max_radius = int((min(w, h) / 2) * 1.5)
    for i in range(max_radius, 0, -1):
        opacity = int(255 * (i / max_radius) * intensity)
        bbox = [w // 2 - i, h // 2 - i, w // 2 + i, h // 2 + i]
        draw.ellipse(bbox, fill=opacity)

    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=100))
    black_overlay = Image.new('RGB', (w, h), 'black')
    return Image.composite(black_overlay, img, vignette)

def apply_bottom_shadow(img: Image.Image, intensity: float = 0.5, height_ratio: float = 0.4) -> Image.Image:
    w, h = img.size
    overlay = Image.new('L', (w, h), color=0)
    draw = ImageDraw.Draw(overlay)

    start_y = int(h * (1 - height_ratio))
    end_y = h

    for y in range(start_y, end_y):
        fade = (y - start_y) / (end_y - start_y if end_y - start_y else 1)
        opacity = int(255 * intensity * fade)
        draw.line([(0, y), (w, y)], fill=opacity)

    black_overlay = Image.new('RGB', (w, h), 'black')
    return Image.composite(black_overlay, img, overlay)
