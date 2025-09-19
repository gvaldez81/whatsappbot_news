"""
Universal Media Processing CLI

This CLI tool supports processing both images and videos with various effects:
- Logo overlay
- Watermark
- Big text overlay  
- Custom text rendering
- Editions and filters

Usage:
  python generate_image.py --image photo.jpg --caption "logo"
  python generate_image.py --video clip.mp4 --caption "big Hello World!"
  python generate_image.py --link https://example.com/news

The tool automatically detects media type (image vs video) and applies effects
using the universal processor (processors/universal.py).
"""
import io
import os
import json
import glob
import uuid
import datetime
import logging
import argparse
from typing import Tuple, Optional, Dict, Any, List

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

from processors import articulo7, captions, logo, watermark, big_text
from processors import text_render, filters, crop
from processors.universal import process_media

logger = logging.getLogger("generate_image")

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def _unique_suffix() -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    rand = uuid.uuid4().hex[:6]
    return f"{ts}-{rand}"

def _safe_truetype(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception as e:
        logger.warning("No se pudo cargar fuente %s (%s). Usando default.", path, e)
        return ImageFont.load_default()

def _save_to_bytes(img: Image.Image, format_hint: str = "JPEG") -> bytes:
    fmt = (format_hint or "JPEG").upper()
    if img.mode in ("RGBA", "LA"):
        fmt = "PNG"
    buf = io.BytesIO()
    if fmt == "JPEG":
        img = img.convert("RGB")
        img.save(buf, format=fmt, quality=95, optimize=True)
    else:
        img.save(buf, format=fmt, optimize=True)
    return buf.getvalue()

def _load_image_from_url(url: str) -> Image.Image:
    import requests
    logger.warning("Deshabilitando verificación SSL para %s", url)
    r = requests.get(url, timeout=15, verify=False)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content))
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    return img

# ------------------------------------------------------------------------------
# Configuración
# ------------------------------------------------------------------------------

def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _list_jsons(directory: str) -> List[str]:
    return sorted(glob.glob(os.path.join(directory, "*.json")))

def load_base_settings(defaults_path: str = "configs/defaults.json",
                       settings_path: str = "configs/settings.json") -> Dict[str, Any]:
    base: Dict[str, Any] = {}
    if os.path.exists(defaults_path):
        try:
            base = _load_json(defaults_path)
        except Exception as e:
            logger.warning("No se pudo cargar defaults.json (%s): %s", defaults_path, e)
    if os.path.exists(settings_path):
        try:
            sett = _load_json(settings_path)
            base = _deep_merge(base, sett)
        except Exception as e:
            logger.warning("No se pudo cargar settings.json (%s): %s", settings_path, e)
    return base

def _load_variant_confs_from_dir(base_settings: Dict[str, Any], variants_dir: str) -> List[Dict[str, Any]]:
    if not os.path.isdir(variants_dir):
        return []
    results: List[Dict[str, Any]] = []
    for path in _list_jsons(variants_dir):
        try:
            override = _load_json(path)
            merged = _deep_merge(base_settings, override)
            merged["_variant"] = os.path.splitext(os.path.basename(path))[0]
            merged["_variant_path"] = path
            results.append(merged)
        except Exception as e:
            logger.warning("No se pudo cargar override %s: %s", path, e)
    return results

# ------------------------------------------------------------------------------
# Aplicación de ediciones
# ------------------------------------------------------------------------------
def create_blurred_background(fg_img, size, blur_radius=25):
    target_w, target_h = size
    bg = fg_img.copy().resize(size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(blur_radius))

    w, h = fg_img.size
    scale = min(target_w / w, target_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    fg_resized = fg_img.resize((new_w, new_h), Image.LANCZOS)

    x = (target_w - new_w) // 2
    y = (target_h - new_h) // 2
    bg.paste(fg_resized, (x, y))
    return bg


def _apply_edition(base_img: Image.Image, title: str, category: str, edition_cfg: Dict[str, Any]) -> Image.Image:
    mode = (edition_cfg.get("mode") or "recorte").lower()
    text_cfg = edition_cfg.get("text", {})
    assets_cfg = edition_cfg.get("assets", {})

    # --- Salida target ---
    target_w = int(edition_cfg.get("output", {}).get("width", 1080))
    target_h = int(edition_cfg.get("output", {}).get("height", 1350))
    target_ratio = target_w / target_h

    # --- Fondo base por mode ---
    if mode == "blur":
        radius = int(edition_cfg.get("blur", {}).get("radius", 25))
        canvas = create_blurred_background(base_img, (target_w, target_h), blur_radius=radius)
        # Fondo blur reescalado para tamaño final
        #canvas = base_img.resize((target_w, target_h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(radius=radius))
    elif mode == "recorte":
        cropped = crop.crop_center_aspect(base_img, target_ratio)
        canvas = cropped.resize((target_w, target_h), Image.LANCZOS)
    else:
        # Fallback: adaptar imagen manteniendo relación con letterbox simple
        canvas = base_img.copy().resize((target_w, target_h), Image.LANCZOS)

    # --- Filtros opcionales ---
    filters_cfg = edition_cfg.get("filters", {})
    if filters_cfg.get("vignette"):
        intensity = float(filters_cfg["vignette"].get("intensity", 0.5))
        canvas = filters.apply_vignette(canvas, intensity)

    if filters_cfg.get("bottom_shadow"):
        fcfg = filters_cfg["bottom_shadow"]
        intensity = float(fcfg.get("intensity", 0.5))
        ratio = float(fcfg.get("height_ratio", 0.4))
        canvas = filters.apply_bottom_shadow(canvas, intensity, ratio)

    # --- Texto: título + categoría con render avanzado ---
    # Título
    # Título
    lines = text_render.get_title_lines(
        title,
        text_cfg["title_font"],
        int(text_cfg["title_size"]),
        int(text_cfg.get("tracking", -25)),
        int(canvas.width * float(text_cfg.get("max_width_ratio", 0.85))),
        int(text_cfg.get("max_lines", 3))
    )
    text_render.draw_title_lines(
        canvas, lines,
        int(text_cfg.get("title_x", 50)),
        int(text_cfg.get("title_y", 700)),
        text_cfg["title_font"],
        int(text_cfg["title_size"]),
        int(text_cfg.get("tracking", -25)),
        int(text_cfg.get("line_spacing", 96)),
        (2, 2),
        float(text_cfg.get("shadow_opacity", 0.5))
    )

    # Categoría
    text_render.draw_category_text(
        canvas, category,
        text_cfg["category_font"],
        int(text_cfg["category_size"]),
        int(text_cfg.get("category_padding", 30)),
        text_cfg.get("category_border_color", "#FF6000"),
        (2, 2),
        int(text_cfg.get("border_thickness", 4)),
        int(text_cfg.get("category_x", 50)),
        int(text_cfg.get("category_y", 650))
    )

    return canvas

# ------------------------------------------------------------------------------
# API pública
# ------------------------------------------------------------------------------

def generate_all_from_link(url: str, base_settings: Dict[str, Any],
                           editions_dir: str = "configs/articulo7/editions", effect: Optional[str] = None) -> List[Dict[str, Any]]:
    logger.info("Procesando link con ediciones: %s", url)

    meta = articulo7.apply(url, base_settings)
    if meta.get("error"):
        raise RuntimeError(meta["error"])

    title = meta.get("title") or "Sin título"
    category = meta.get("category")
    image_url = meta.get("image_url")
    if not image_url:
        raise RuntimeError("No se encontró imagen en el enlace.")

    base_img = _load_image_from_url(image_url)

    editions = _load_variant_confs_from_dir(base_settings, editions_dir)
    if not editions:
        tmp = dict(base_settings)
        tmp["_variant"] = "default"
        tmp["mode"] = tmp.get("mode", "recorte")
        editions = [tmp]

    # FILTRO POR effect
    if effect:
        filtered = [e for e in editions if (e.get("mode") or "").lower() == effect.lower()]
        if not filtered:
            #return [f"No hay configuración para el efecto solicitado: {effect}"]
            raise RuntimeError(f"No hay configuración para el efecto solicitado: {effect}")
        editions = filtered

    results: List[Dict[str, Any]] = []
    for ed_cfg in editions:
        variant_name = ed_cfg.get("_variant", "variant")
        try:
            img = _apply_edition(base_img, title, category, ed_cfg)
            fmt = ed_cfg.get("output", {}).get("format", "JPEG")
            out_bytes = _save_to_bytes(img, fmt)
            fname = f"{variant_name}-{_unique_suffix()}.jpg"
            results.append({"variant": variant_name, "bytes": out_bytes, "filename": fname})
        except Exception as e:
            logger.exception("Error en edición '%s': %s", variant_name, e)
    return results

def generate_from_link(url: str, base_settings: Dict[str, Any]) -> Tuple[bytes, str]:
    all_res = generate_all_from_link(url, base_settings, editions_dir="configs/articulo7/editions")
    if not all_res:
        raise RuntimeError("No se generó ninguna edición.")
    first = all_res[0]
    return first["bytes"], first["filename"]

def generate_from_media(image_bytes: bytes, caption: Optional[str], base_settings: Dict[str, Any]) -> Tuple[bytes, str]:
    """
    Captions soportados:
      - "logo"       -> overlay de logo
      - "watermark"  -> marca de agua
      - "big"        -> bigtext (el resto del caption es el texto)
      - "recorte"    -> usa primera edición con mode=recorte
      - "blur"       -> usa primera edición con mode=blur
      - Texto libre  -> si classify lo identifica como 'text'
    """
    logger.info("Procesando media con caption: %s", caption)
    
    # Use the universal processor for all media processing
    return process_media(image_bytes, caption, base_settings)

# ------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Motor gráfico (links generan todas las ediciones; media por caption). Soporta imágenes y videos."
    )
    parser.add_argument("--link", help="Procesar un enlace (genera todas las ediciones en configs/articulo7/editions)")
    parser.add_argument("--image", help="Ruta a una imagen local")
    parser.add_argument("--video", help="Ruta a un video local")
    parser.add_argument("--caption", help="Caption para la imagen/video (logo, watermark, big [TEXTO], recorte, blur)")
    parser.add_argument("--output", help="Archivo o prefijo de salida", default="output.jpg")
    parser.add_argument("--editions-dir", help="Directorio de ediciones para links/captions", default="configs/articulo7/editions")
    parser.add_argument("--defaults", help="Ruta a defaults.json", default="configs/defaults.json")
    parser.add_argument("--settings", help="Ruta a settings.json", default="configs/settings.json")
    parser.add_argument("--log", help="Nivel de log (DEBUG, INFO, WARNING, ERROR)", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log.upper(), logging.INFO))

    cfg = load_base_settings(defaults_path=args.defaults, settings_path=args.settings)

    if args.link:
        results = generate_all_from_link(args.link, cfg, editions_dir=args.editions_dir)
        base, ext = os.path.splitext(args.output)
        ext = ext or ".jpg"
        written = []
        for r in results:
            out_path = f"{base}-{r['variant']}{ext}"
            with open(out_path, "wb") as f:
                f.write(r["bytes"])
            written.append(out_path)
        print("Generadas:", ", ".join(written))
        return

    if args.image:
        with open(args.image, "rb") as f:
            media_bytes = f.read()
        out_bytes, name = process_media(media_bytes, args.caption, cfg)
        
        # Set appropriate output extension based on detected media type
        if name.endswith('.mp4'):
            base, _ = os.path.splitext(args.output)
            out_path = base + '.mp4'
        else:
            out_path = args.output
            
        with open(out_path, "wb") as f:
            f.write(out_bytes)
        print(f"Procesada imagen: {out_path} (sugerido: {name})")
        return

    if args.video:
        with open(args.video, "rb") as f:
            media_bytes = f.read()
        out_bytes, name = process_media(media_bytes, args.caption, cfg)
        
        # Set appropriate output extension for video
        base, _ = os.path.splitext(args.output)
        out_path = base + '.mp4'
            
        with open(out_path, "wb") as f:
            f.write(out_bytes)
        print(f"Procesado video: {out_path} (sugerido: {name})")
        return

    parser.error("Debes especificar --link, --image o --video")


if __name__ == "__main__":
    main()
