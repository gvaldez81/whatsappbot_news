from PIL import Image

def crop_center_aspect(img: Image.Image, target_ratio: float) -> Image.Image:
    w, h = img.size
    current_ratio = w / h
    if current_ratio > target_ratio:
        # Imagen demasiado ancha → recortar lados
        new_width = int(h * target_ratio)
        left = (w - new_width) // 2
        return img.crop((left, 0, left + new_width, h))
    else:
        # Imagen demasiado alta → recortar arriba/abajo
        new_height = int(w / target_ratio)
        top = (h - new_height) // 2
        return img.crop((0, top, w, top + new_height))
