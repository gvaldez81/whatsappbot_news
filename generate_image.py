# generate_image.py
# Motor gráfico con:
# - Ediciones automáticas para links (recorte, blur, etc.) en configs/articulo7/editions/*.json
# - Ediciones por petición (logo, watermark, bigtext, recorte, blur) vía caption
# - Nombres de archivo AUTO-generados con sufijo único (timestamp + UUID corto)
# - CLI para probar links (multivariantes) e imágenes con caption
#
# Requisitos esperados del proyecto:
# - processors/articulo7.py -> apply(url, config) -> dict(title, image_url, category, error?)
# - processors/captions.py  -> classify(caption) -> (kind, extra)
# - processors/logo.py      -> apply(image, cfg) -> image
# - processors/watermark.py -> apply(image, cfg) -> image
# - processors/big_text.py  -> apply(image, text, cfg) -> image
#
# Configuración:
# - configs/defaults.json  (estilos editoriales y parámetros gráficos por defecto)
# - configs/settings.json  (parámetros operativos; se fusiona sobre defaults)
# - configs/articulo7/editions/*.json (cada una es una edición editorial)
#
# Nota: NO es necesario definir "filename" en los JSON. Se genera automáticamente:
#   - Para ediciones: <variant>-<timestamp>-<uuid6>.jpg
#   - Para captions:  <kind>-<timestamp>-<uuid6>.jpg
# Donde <variant> es el nombre del archivo JSON de la edición (sin .json).
#
# El caption para big text es "big" (sin signos).

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

from processors import captions, logo, watermark, big_text, articulo7

logger = logging.getLogger("generate_image")


# ------------------------------------------------------------------------------
# Helpers genéricos
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

def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    return draw.textsize(text, font=font)

def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> str:
    words = text.split()
    if not words:
        return ""
    lines, current = [], words[0]
    for w in words[1:]:
        test = f"{current} {w}"
        w_px, _ = _text_size(draw, test, font)
        if w_px <= max_width:
            current = test
        else:
            lines.append(current)
            current = w
    lines.append(current)
    return "\n".join(lines)

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
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content))
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    return img


# ------------------------------------------------------------------------------
# Renderizado de título/categoría
# ------------------------------------------------------------------------------

def _compose_title_and_category(base: Image.Image, title: str, category: str,
                                cfg_assets: Dict[str, Any], cfg_text: Dict[str, Any]) -> Image.Image:
    img = base.copy()
    draw = ImageDraw.Draw(img)

    fonts_dir = cfg_assets.get("fonts_dir", "assets/fonts")
    title_font = _safe_truetype(cfg_text.get("title_font", f"{fonts_dir}/Montserrat-Light.ttf"),
                                int(cfg_text.get("title_size", 56)))
    category_font = _safe_truetype(cfg_text.get("category_font", f"{fonts_dir}/Montserrat-Light.ttf"),
                                   int(cfg_text.get("category_size", 36)))

    title_color = tuple(cfg_text.get("title_color", [255, 255, 255]))
    category_color = tuple(cfg_text.get("category_color", [255, 200, 0]))

    margin_x = int(cfg_text.get("margin_x", 50))
    margin_y = int(cfg_text.get("margin_y", 50))
    line_spacing = int(cfg_text.get("line_spacing", 8))
    max_width_ratio = float(cfg_text.get("max_width_ratio", 0.8))
    gap = int(cfg_text.get("gap_title_category", 10))

    max_text_width = int(img.width * max_width_ratio)
    wrapped = _wrap_text(title.strip(), title_font, max_text_width, draw)

    y = margin_y
    for line in wrapped.split("\n"):
        draw.text((margin_x, y), line, font=title_font, fill=title_color)
        _, h = _text_size(draw, line, title_font)
        y += h + line_spacing

    y += gap
    if category:
        draw.text((margin_x, y), category.strip(), font=category_font, fill=category_color)

    return img


# ------------------------------------------------------------------------------
# Carga de configuración (defaults + settings + overrides de edición)
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
# Variantes de edición (recorte, blur, etc.)
# ------------------------------------------------------------------------------

def _apply_edition(base_img: Image.Image, title: str, category: str, edition_cfg: Dict[str, Any]) -> Image.Image:
    mode = (edition_cfg.get("mode") or "recorte").lower()
    text_cfg = edition_cfg.get("text", {})
    assets_cfg = edition_cfg.get("assets", {})

    if mode == "blur":
        radius = int(edition_cfg.get("blur", {}).get("radius", 25))
        canvas = base_img.filter(ImageFilter.GaussianBlur(radius=radius))
        out = _compose_title_and_category(canvas, title, category, assets_cfg, text_cfg)
    else:
        out = _compose_title_and_category(base_img, title, category, assets_cfg, text_cfg)

    return out


# ------------------------------------------------------------------------------
# API pública
# ------------------------------------------------------------------------------

def generate_all_from_link(url: str, base_settings: Dict[str, Any],
                           editions_dir: str = "configs/articulo7/editions") -> List[Dict[str, Any]]:
    logger.info("Procesando link con ediciones: %s", url)

    meta = articulo7.apply(url, base_settings)
    if meta.get("error"):
        raise RuntimeError(meta["error"])

    title = meta.get("title") or "Sin título"
    category = meta.get("category") or "ARTÍCULO 7"
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
    """
    Compatibilidad: devuelve solo la PRIMERA edición generada.
    """
    all_res = generate_all_from_link(url, base_settings, editions_dir="configs/articulo7/editions")
    if not all_res:
        raise RuntimeError("No se generó ninguna edición.")
    first = all_res[0]
    return first["bytes"], first["filename"]

def generate_from_media(image_bytes: bytes, caption: Optional[str], base_settings: Dict[str, Any]) -> Tuple[bytes, str]:
    """
    Procesa una imagen enviada con caption.
    Captions soportados:
      - "logo"       -> overlay de logo (desde base_settings['logo'])
      - "watermark"  -> marca de agua (desde base_settings['watermark'])
      - "big"        -> bigtext (desde base_settings['bigtext'])
      - "recorte"    -> usa la primera edición con mode=recorte
      - "blur"       -> usa la primera edición con mode=blur
      - Texto libre  -> si classify lo identifica como 'text'
    """
    logger.info("Procesando media con caption: %s", caption)

    base = Image.open(io.BytesIO(image_bytes))
    base = ImageOps.exif_transpose(base)
    if base.mode not in ("RGB", "RGBA"):
        base = base.convert("RGB")

    # Normaliza 'big' sin signos
    raw_caption = (caption or "").strip()
    kind, extra = captions.classify(raw_caption)
    if raw_caption.lower().startswith("big"):
        kind = "bigtext"
        # el resto del caption (si existe) después de 'big ' se usa como texto
        parts = raw_caption.split(maxsplit=1)
        extra = {"text": parts[1].strip()} if len(parts) > 1 else {"text": ""}

    if kind == "logo":
        img = logo.apply(base, base_settings.get("logo", {}))
        fname = f"logo-{_unique_suffix()}.jpg"
        return _save_to_bytes(img, base_settings.get("output", {}).get("format", "JPEG")), fname

    if kind == "watermark":
        img = watermark.apply(base, base_settings.get("watermark", {}))
        fname = f"watermark-{_unique_suffix()}.jpg"
        return _save_to_bytes(img, base_settings.get("output", {}).get("format", "JPEG")), fname

    if kind == "bigtext":
        text = (extra.get("text") or "").strip()
        img = big_text.apply(base, text, base_settings.get("bigtext", {}))
        fname = f"bigtext-{_unique_suffix()}.jpg"
        return _save_to_bytes(img, base_settings.get("output", {}).get("format", "JPEG")), fname

    if kind in ("recorte", "blur"):
        editions_dir = "configs/articulo7/editions"
        editions = _load_variant_confs_from_dir(base_settings, editions_dir)
        chosen = None
        for ed in editions:
            if (ed.get("mode") or "").lower() == kind:
                chosen = ed
                break
        if not chosen:
            raise RuntimeError(f"No existe una edición con mode='{kind}' en {editions_dir}")

        # Para media no hay metadatos; usa el caption completo como título si hay texto, o un placeholder
        title = extra.get("text") or raw_caption or "Sin título"
        category = "EDICIÓN"
        img = _apply_edition(base, title, category, chosen)
        fname = f"{kind}-{_unique_suffix()}.jpg"
        return _save_to_bytes(img, chosen.get("output", {}).get("format", "JPEG")), fname

    if kind == "text":
        text = (extra.get("text") or "").strip()
        fonts_dir = base_settings.get("assets", {}).get("fonts_dir", "assets/fonts")
        text_cfg = base_settings.get("text", {})
        font_path = text_cfg.get("free_text_font", f"{fonts_dir}/Impact.ttf")
        size = int(text_cfg.get("free_text_size", 64))
        color = tuple(text_cfg.get("free_text_color", [255, 255, 255]))
        margin_x = int(text_cfg.get("free_text_margin_x", 50))
        margin_y = int(text_cfg.get("free_text_margin_y", 50))
        max_width_ratio = float(text_cfg.get("free_text_max_width_ratio", 0.85))
        line_spacing = int(text_cfg.get("free_text_line_spacing", 10))

        font = _safe_truetype(font_path, size)
        draw = ImageDraw.Draw(base)
        max_w = int(base.width * max_width_ratio)
        wrapped = _wrap_text(text, font, max_w, draw)

        y = margin_y
        for line in wrapped.split("\n"):
            draw.text((margin_x, y), line, font=font, fill=color)
            _, h = _text_size(draw, line, font)
            y += h + line_spacing

        fname = f"text-{_unique_suffix()}.jpg"
        return _save_to_bytes(base, base_settings.get("output", {}).get("format", "JPEG")), fname

    # Fallback: devolver original
    fname = f"original-{_unique_suffix()}.jpg"
    return image_bytes, fname


# ------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Motor gráfico (links generan todas las ediciones; media por caption)."
    )
    parser.add_argument("--link", help="Procesar un enlace (genera todas las ediciones en configs/articulo7/editions)")
    parser.add_argument("--image", help="Ruta a una imagen local")
    parser.add_argument("--caption", help="Caption para la imagen (logo, watermark, big [TEXTO], recorte, blur)")
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
            img_b = f.read()
        out_bytes, name = generate_from_media(img_b, args.caption, cfg)
        out_path = args.output
        with open(out_path, "wb") as f:
            f.write(out_bytes)
        print(f"Generada: {out_path} (sugerido: {name})")
        return

    parser.error("Debes especificar --link o --image")


if __name__ == "__main__":
    main()
