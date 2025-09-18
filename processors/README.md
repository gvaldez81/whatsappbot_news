# Procesadores de imágenes

Este directorio contiene los módulos **plug‑and‑play** que transforman imágenes o extraen metadatos según el tipo de entrada.  
Todos comparten utilidades comunes definidas en `__init__.py` (`ensure_rgba`, `ensure_rgb`, `open_image`, `clamp`).

---

## 📌 Lista de procesadores

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

### 5. `article7.py`
- **Rol:** Extrae metadatos de un link de Artículo 7.
- **Acciones:**
  - Descarga HTML.
  - Obtiene `og:image`, `og:title`, sección/categoría.
  - Respeta `use_static_category` y `default_category` en config.
- **Activación:** cuando el `source_type` es `"articulo7"`.

---

## 🔄 Flujo típico

1. El bot recibe un mensaje (link o imagen con caption).
2. `generate_image.py` determina el `source_type` y carga el config (merge de `defaults.json` + override).
3. Si es imagen con caption → `captions.process_caption` decide:
   - Procesador especial (`watermark`, `logo`, `big_text`).
   - O texto libre → se dibuja como título.
4. Si es link de Artículo 7 → `article7.apply` devuelve metadatos para renderizar.
5. El motor aplica filtros, tipografía y guarda la imagen final.

---

## 🛠️ Extender

Para agregar un nuevo procesador:
1. Crear `processors/nuevo.py` con una función `apply(img, caption_text, config)`.
2. Importarlo en `captions.py` y definir la regla de activación (ej. caption `"nuevo"`).
3. Añadir un override en `configs/media/nuevo.json` si requiere parámetros propios.
