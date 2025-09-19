# processors/captions.py
from . import watermark, logo, big_text

def classify(caption: str):
    """
    Clasifica un caption en (kind, extra).
    kind puede ser: logo, watermark, bigtext, recorte, blur, text, unknown.
    extra es un dict con datos adicionales (ej. {"text": "..."}).
    """
    if not caption:
        return "unknown", {}

    cap = caption.strip().lower()

    if cap == "logo":
        return "logo", {}
    if cap == "watermark":
        return "watermark", {}
    if cap.startswith("big"):
        # lo manejamos también aquí por compatibilidad
        parts = caption.split(maxsplit=1)
        return "bigtext", {"text": parts[1].strip() if len(parts) > 1 else ""}
    if cap.startswith("recorte"):
        return "recorte", {}
    if cap.startswith("blur"):
        return "blur", {}

    # Si no coincide con comandos conocidos, lo tratamos como texto libre
    return "text", {"text": caption}

def process_caption(img, caption_text, config):
    """
    Decide cómo procesar el caption de una imagen.

    - Si el caption es "watermark" → aplica el procesador de marca de agua.
    - Si el caption es "logo" → aplica el procesador de logo.
    - Si el caption empieza con "!big " → aplica el procesador de texto grande.
    - Si es texto libre → no altera la imagen y devuelve ese texto como título.
    - Si no hay caption → no hace nada.
    
    Retorna:
      (imagen_procesada, titulo_opcional)
    """
    if caption_text is None:
        return img, None

    key = caption_text.strip()

    # Procesadores especiales
    if key.lower() == "marca":
        return watermark.apply(img, config), None

    if key.lower() == "logo":
        return logo.apply(img, config), None

    if key.lower().startswith("grande "):
        text = key[7:].strip()
        return bigtext.apply(img, text, config), None

    # Texto libre → se usará como título en generate_image
    if key == "":
        return img, None

    return img, key
