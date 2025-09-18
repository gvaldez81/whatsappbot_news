# processors/articulo7.py
import requests
from bs4 import BeautifulSoup

def apply(url, config):
    """
    Procesa un link de Artículo 7 y devuelve metadatos útiles
    para el motor gráfico.

    Config soportada:
      - use_static_category: si True, fuerza default_category
      - default_category: etiqueta fija (ej. "ARTÍCULO 7")
    """
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return {
            "title": None,
            "image_url": None,
            "category": config.get("default_category", "ARTÍCULO 7"),
            "error": f"Error al descargar: {e}"
        }

    soup = BeautifulSoup(resp.text, "html.parser")

    # Extraer metadatos Open Graph
    og_title = soup.find("meta", property="og:title")
    og_image = soup.find("meta", property="og:image")

    title = og_title["content"].strip() if og_title and og_title.get("content") else None
    image_url = og_image["content"].strip() if og_image and og_image.get("content") else None

    # Categoría: estática o dinámica
    if config.get("use_static_category", False):
        category = config.get("default_category", "ARTÍCULO 7")
    else:
        # Buscar categoría en HTML (ejemplo: <meta property="article:section">)
        section = soup.find("meta", property="article:section")
        category = section["content"].strip() if section and section.get("content") else config.get("default_category", "ARTÍCULO 7")

    return {
        "title": title,
        "image_url": image_url,
        "category": category,
        "error": None
    }
