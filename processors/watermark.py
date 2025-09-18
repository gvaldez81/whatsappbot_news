from PIL import Image, ImageEnhance

def apply(base_img, cfg):
    watermark_path = cfg.get("watermark_file", "assets/overlays/watermark.png")
    opacity = float(cfg.get("watermark_opacity", 0.12))
    tile = bool(cfg.get("watermark_tile", True))
    scale_ratio = float(cfg.get("watermark_scale_ratio", 0.25))
    position = cfg.get("watermark_position", "center")  # Supports: center, top-left, top-right, bottom-left, bottom-right
    margin = int(cfg.get("watermark_margin", 16))

    watermark_img = Image.open(watermark_path).convert("RGBA")
    # Scale watermark relative to base image width
    wm_width = int(base_img.width * scale_ratio)
    scale = wm_width / watermark_img.width
    wm_height = int(watermark_img.height * scale)
    watermark_img = watermark_img.resize((wm_width, wm_height), Image.Resampling.LANCZOS)

    # Apply opacity
    if opacity < 1:
        alpha = watermark_img.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
        watermark_img.putalpha(alpha)

    result = base_img.convert("RGBA")
    if tile:
        # Tiled pattern fill
        for y in range(0, base_img.height, wm_height):
            for x in range(0, base_img.width, wm_width):
                result.alpha_composite(watermark_img, dest=(x, y))
    else:
        # Single watermark: support center and corners
        if position == "center":
            x = (base_img.width - wm_width) // 2
            y = (base_img.height - wm_height) // 2
        elif position == "top-left":
            x, y = margin, margin
        elif position == "top-right":
            x = base_img.width - wm_width - margin
            y = margin
        elif position == "bottom-left":
            x = margin
            y = base_img.height - wm_height - margin
        elif position == "bottom-right":
            x = base_img.width - wm_width - margin
            y = base_img.height - wm_height - margin
        else:
            # Default to center
            x = (base_img.width - wm_width) // 2
            y = (base_img.height - wm_height) // 2
        result.alpha_composite(watermark_img, dest=(int(x), int(y)))
    return result.convert(base_img.mode)