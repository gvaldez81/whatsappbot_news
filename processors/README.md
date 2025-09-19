# Procesadores de imágenes y videos

Este directorio contiene los módulos **plug‑and‑play** que transforman imágenes y videos o extraen metadatos según el tipo de entrada.  
Todos comparten utilidades comunes definidas en `__init__.py` (`ensure_rgba`, `ensure_rgb`, `open_image`, `clamp`).

---

## 📌 Lista de procesadores

### 0. `universal.py` ⭐ **NUEVO**
- **Rol:** Procesador universal para imágenes y videos con soporte completo de efectos.
- **Características:**
  - Detección automática del tipo de media (imagen vs video)
  - Soporte completo para logo, watermark, bigtext y otros efectos
  - Usa PIL para efectos de imagen
  - Usa ffmpeg-python para composición de video
- **Entrada:** `process_media(media_bytes, caption, config)`
- **Salida:** `(media_procesada_bytes, filename_sugerido)`
- **Activación:** Usado automáticamente por WhatsApp bot y CLI

### 1. `captions.py`
- **Rol:** Dispatcher central para captions de imágenes.
- **Lógica:**
  - `"watermark"` → llama a `watermark.apply`.
  - `"logo"` → llama a `logo.apply`.
  - `"!big ..."` → llama a `big_text.apply` con el resto del caption.
  - Texto libre → se devuelve como título para que el motor lo dibuje.
- **Entrada:** `(img, caption_text, config)`
- **Salida:** `(img_procesada, titulo_opcional)`

---

### 2. `watermark.py`
- **Rol:** Superpone una marca de agua sobre la imagen.
- **Config soportada:**
  - `watermark_file` → ruta al PNG.
  - `watermark_opacity` → opacidad global (0.0–1.0).
  - `watermark_tile` → si `true`, repite en mosaico; si `false`, centra.
  - `watermark_scale_ratio` → escala relativa al ancho de la imagen base.
- **Activación:** caption `"watermark"`.

---

### 3. `logo.py`
- **Rol:** Inserta un logo en la imagen.
- **Config soportada:**
  - `logo_file` → ruta al PNG.
  - `logo_position` → `top-left`, `top-right`, `bottom-left`, `bottom-right`, `center`.
  - `logo_scale_ratio` → escala relativa al ancho de la imagen base.
  - `logo_margin` → margen desde el borde.
- **Activación:** caption `"logo"`.

---

### 4. `big_text.py`
- **Rol:** Renderiza un bloque de texto grande centrado (flyer express).
- **Config soportada:**
  - `bigtext_font_path`, `bigtext_font_size`, `bigtext_color`.
  - `bigtext_shadow`, `bigtext_shadow_offset`, `bigtext_shadow_color`.
  - `bigtext_max_width_ratio`, `bigtext_line_spacing`.
- **Activación:** caption que empiece con `!big ...`.

---

### 5. `newsname.py`
- **Rol:** Extrae metadatos de un link del sitio de noticias.
- **Acciones:**
  - Descarga HTML.
  - Obtiene `og:image`, `og:title`, sección/categoría.
  - Respeta `use_static_category` y `default_category` en config.
- **Activación:** cuando el `source_type` es `"newsname"`.

---

## 🔄 Flujo típico

1. El bot recibe un mensaje (link, imagen o video con caption).
2. `generate_image.py` y el bot de WhatsApp usan el procesador universal (`universal.py`) para:
   - Detectar automáticamente si el media es imagen o video
   - Aplicar efectos apropiados según el caption
3. Para imágenes: se aplican efectos directamente usando PIL
4. Para videos: se crean overlays con PIL y se componen con ffmpeg-python
5. Efectos soportados para ambos tipos de media:
   - `"logo"` → overlay de logo
   - `"watermark"` → marca de agua (solo imágenes por ahora)
   - `"big TEXTO"` → texto grande
   - Texto libre → se renderiza como bigtext

---

## 🛠️ Extender

Para agregar un nuevo procesador:
1. Crear `processors/nuevo.py` con una función `apply(img, caption_text, config)`.
2. Importarlo en `captions.py` y definir la regla de activación (ej. caption `"nuevo"`).
3. Añadir un override en `configs/media/nuevo.json` si requiere parámetros propios.
