# processors/__init__.py
from PIL import Image

def ensure_rgba(img: Image.Image) -> Image.Image:
    """
    Asegura que la imagen esté en modo RGBA.
    """
    return img if img.mode == "RGBA" else img.convert("RGBA")

def ensure_rgb(img: Image.Image) -> Image.Image:
    """
    Asegura que la imagen esté en modo RGB.
    """
    return img if img.mode == "RGB" else img.convert("RGB")

def open_image(path: str) -> Image.Image:
    """
    Abre una imagen desde disco.
    """
    return Image.open(path)

def clamp(val: float, lo: float, hi: float) -> float:
    """
    Restringe un valor entre un mínimo y un máximo.
    """
    return max(lo, min(hi, val))
