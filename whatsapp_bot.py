# whatsapp_bot.py
"""
WhatsApp Bot for Image and Video Processing

This bot supports receiving and processing both images and videos with various effects:
- Logo overlay
- Watermark (images only)
- Big text overlay
- Custom text rendering

Supported media types:
- Images: JPEG, PNG, etc.
- Videos: MP4, MOV, AVI, MKV, etc.

All processing is handled by the universal processor (processors/universal.py) which
automatically detects media type and applies appropriate effects using PIL for images
and ffmpeg-python for video composition.
"""
import os
import re
import json
import logging
from typing import Any, Dict, Optional, Tuple, List
import requests
from flask import Flask, request, jsonify

from config_loader import load_config
from dotenv import load_dotenv
load_dotenv()  # take environment variables from .env.

# Import universal processor for both images and videos
try:
    from processors.universal import process_media
except ImportError:
    def process_media(media_bytes: bytes, caption: Optional[str], config: Dict[str, Any]) -> Tuple[bytes, str]:
        raise NotImplementedError("Universal processor not available")

# Opcional: adapta estos imports a tus funciones reales en generate_image.py
# Debes implementar estas funciones en tu motor gráfico según tu diseño.
# - generate_from_link(url, config) -> (bytes, filename)   # retorna bytes de imagen y nombre sugerido
# - generate_from_media(image_bytes, caption, config) -> (bytes, filename)
# - generate_all_from_link(url, config, effect=None) -> List[Tuple[bytes, filename]]
try:
    from generate_image import generate_from_link, generate_from_media, generate_all_from_link
except Exception:
    # Fallback para evitar crash si aún no implementas `generate_image.py`
    def generate_from_link(url: str, config: Dict[str, Any]) -> Tuple[bytes, str]:
        raise NotImplementedError("Implementa generate_from_link(url, config) en generate_image.py")

    def generate_from_media(image_bytes: bytes, caption: Optional[str], config: Dict[str, Any]) -> Tuple[bytes, str]:
        raise NotImplementedError("Implementa generate_from_media(image_bytes, caption, config) en generate_image.py")

    def generate_all_from_link(url: str, config: Dict[str, Any], effect: Optional[str] = None) -> List[Tuple[bytes, str]]:
        raise NotImplementedError("Implementa generate_all_from_link(url, config, effect) en generate_image.py")

# ------------------------------------------------------------------------------
# Configuración básica
# ------------------------------------------------------------------------------
#print("Verify_token= "+os.getenv("WHATSAPP_VERIFY_TOKEN"))
config = load_config()
WA = config.get("whatsapp", {})
SERVER = config.get("server", {})

ACCESS_TOKEN = WA.get("access_token") or os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = WA.get("phone_number_id") or os.getenv("WHATSAPP_PHONE_ID")
VERIFY_TOKEN = WA.get("verify_token") or os.getenv("WHATSAPP_VERIFY_TOKEN")
GRAPH_BASE = WA.get("api_url", "https://graph.facebook.com/v17.0")

LOG_LEVEL = (config.get("logging", {}) or {}).get("level", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("whatsapp_bot")

# ------------------------------------------------------------------------------
# App
# ------------------------------------------------------------------------------
app = Flask(__name__)

# ------------------------------------------------------------------------------
# Utilidades WhatsApp Cloud API
# ------------------------------------------------------------------------------
def wa_send_text(to: str, body: str) -> None:
    url = f"{GRAPH_BASE}/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body}
    }
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    if r.status_code >= 300:
        logger.error("Error al enviar texto: %s %s", r.status_code, r.text)

def wa_upload_media(media_bytes: bytes, filename: str = "media.jpg", mime: str = "image/jpeg") -> Optional[str]:
    """
    Sube un archivo binario (imagen o video) a la API y devuelve media_id.
    """
    url = f"{GRAPH_BASE}/{PHONE_NUMBER_ID}/media"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    files = {
        "file": (filename, media_bytes, mime)
    }
    
    # Determine media type based on MIME type
    media_type = "video" if mime.startswith("video/") else "image"
    
    data = {
        "messaging_product": "whatsapp",
        "type": media_type
    }
    r = requests.post(url, headers=headers, files=files, data=data, timeout=60)  # Increased timeout for videos
    if r.status_code >= 300:
        logger.error("Error al subir media: %s %s", r.status_code, r.text)
        return None
    media_id = r.json().get("id")
    return media_id

def wa_send_image_by_media_id(to: str, media_id: str, caption: Optional[str] = None) -> None:
    url = f"{GRAPH_BASE}/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    image_obj: Dict[str, Any] = {"id": media_id}
    if caption:
        image_obj["caption"] = caption
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": image_obj
    }
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    if r.status_code >= 300:
        logger.error("Error al enviar imagen: %s %s", r.status_code, r.text)

def wa_send_video_by_media_id(to: str, media_id: str, caption: Optional[str] = None) -> None:
    url = f"{GRAPH_BASE}/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    video_obj: Dict[str, Any] = {"id": media_id}
    if caption:
        video_obj["caption"] = caption
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "video",
        "video": video_obj
    }
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    if r.status_code >= 300:
        logger.error("Error al enviar video: %s %s", r.status_code, r.text)

def wa_get_media_url(media_id: str) -> Optional[str]:
    """
    Obtiene la URL temporal de descarga para un media_id.
    """
    url = f"{GRAPH_BASE}/{media_id}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code >= 300:
        logger.error("Error al obtener URL de media: %s %s", r.status_code, r.text)
        return None
    return r.json().get("url")

def wa_download_media(media_url: str) -> Optional[bytes]:
    """
    Descarga el binario de la imagen desde la URL temporal.
    """
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    r = requests.get(media_url, headers=headers, timeout=30)
    if r.status_code >= 300:
        logger.error("Error al descargar media: %s %s", r.status_code, r.text)
        return None
    return r.content

# ------------------------------------------------------------------------------
# Parsing del webhook
# ------------------------------------------------------------------------------

URL_RE = re.compile(r"https?://[^\s]+")

def extract_message_entry(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extrae el primer objeto 'messages' válido del webhook.
    """
    try:
        entry = payload["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages", [])
        if not messages:
            return None
        msg = messages[0]
        contacts = value.get("contacts", [])
        from_wa = msg.get("from")  # número del usuario
        contact_name = contacts[0]["profile"]["name"] if contacts else None
        return {"message": msg, "from": from_wa, "name": contact_name}
    except Exception as e:
        logger.warning("No se pudo extraer mensaje: %s", e)
        return None

def classify_message(msg: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Clasifica el mensaje:
      - ('text_link', {'url': ..., 'effect': ...})
      - ('image', {'media_id': ..., 'caption': ...})
      - ('text', {'body': ...})
    """
    msg_type = msg.get("type")
    if msg_type == "text":
        body = (msg.get("text") or {}).get("body", "").strip()
        url_match = URL_RE.search(body)
        if url_match:
            parts = body.split()
            url = parts[0]
            effect = parts[1] if len(parts) > 1 else None
            return "text_link", {"url": url, "effect": effect, "full_text": body}
        return "text", {"body": body}

    if msg_type == "image":
        image = msg.get("image") or {}
        media_id = image.get("id")
        caption = image.get("caption")
        return "image", {"media_id": media_id, "caption": caption}

    if msg_type == "video":
        video = msg.get("video") or {}
        media_id = video.get("id")
        caption = video.get("caption")
        return "video", {"media_id": media_id, "caption": caption}

    # Otros tipos (audio, docs, interactive, etc.)
    return "unsupported", {"raw": msg}

# ------------------------------------------------------------------------------
# Handlers de negocio
# ------------------------------------------------------------------------------
def handle_text_link(to: str, url: str, effect: Optional[str] = None) -> None:
    try:
        wa_send_text(to, "Procesando tu enlace…")
        all_images_or_msg = generate_all_from_link(url, config, effect=effect)
        if isinstance(all_images_or_msg, str):
            wa_send_text(to, all_images_or_msg)
            return
        for image_info in all_images_or_msg:
            image_bytes = image_info["bytes"]
            filename = image_info.get("filename", "image.jpg")
            media_id = wa_upload_media(image_bytes, filename=filename)
            if not media_id:
                wa_send_text(to, f"No pude subir la imagen {filename}. Inténtalo de nuevo más tarde.")
                continue
            wa_send_image_by_media_id(to, media_id)
    except NotImplementedError as e:
        logger.error("Función no implementada: %s", e)
        wa_send_text(to, "Esta función aún no está disponible en el bot.")
    except Exception as e:
        logger.exception("Error procesando link: %s", e)
        wa_send_text(to, f"Hubo un error procesando el enlace. {e}")

def handle_image(to: str, media_id: str, caption: Optional[str]) -> None:
    try:
        wa_send_text(to, "Procesando tu imagen…")
        media_url = wa_get_media_url(media_id)
        if not media_url:
            wa_send_text(to, "No pude obtener el archivo de imagen. Inténtalo de nuevo.")
            return
        img_bytes = wa_download_media(media_url)
        if not img_bytes:
            wa_send_text(to, "No pude descargar la imagen. Inténtalo de nuevo.")
            return

        # Use universal processor for image processing
        image_bytes, filename = process_media(img_bytes, caption, config)
        upload_id = wa_upload_media(image_bytes, filename=filename)
        if not upload_id:
            wa_send_text(to, "No pude subir la imagen generada. Inténtalo de nuevo más tarde.")
            return
        wa_send_image_by_media_id(to, upload_id)
    except NotImplementedError as e:
        logger.error("Función no implementada: %s", e)
        wa_send_text(to, "Esta función aún no está disponible en el bot.")
    except Exception as e:
        logger.exception("Error procesando imagen: %s", e)
        wa_send_text(to, f"Hubo un error procesando tu imagen. {e}")

def handle_video(to: str, media_id: str, caption: Optional[str]) -> None:
    try:
        wa_send_text(to, "Procesando tu video…")
        media_url = wa_get_media_url(media_id)
        if not media_url:
            wa_send_text(to, "No pude obtener el archivo de video. Inténtalo de nuevo.")
            return
        video_bytes = wa_download_media(media_url)
        if not video_bytes:
            wa_send_text(to, "No pude descargar el video. Inténtalo de nuevo.")
            return

        # Use universal processor for video processing
        processed_bytes, filename = process_media(video_bytes, caption, config)
        upload_id = wa_upload_media(processed_bytes, filename=filename, mime="video/mp4")
        if not upload_id:
            wa_send_text(to, "No pude subir el video procesado. Inténtalo de nuevo más tarde.")
            return
        wa_send_video_by_media_id(to, upload_id)
    except NotImplementedError as e:
        logger.error("Función no implementada: %s", e)
        wa_send_text(to, "Esta función aún no está disponible en el bot.")
    except Exception as e:
        logger.exception("Error procesando video: %s", e)
        wa_send_text(to, f"Hubo un error procesando tu video. {e}")

# ------------------------------------------------------------------------------
# Webhook endpoints
# ------------------------------------------------------------------------------

@app.route("/webhook", methods=["GET"])
def verify():
    """
    Verificación del webhook (modo suscripción).
    GitHub/Meta llamará con query params:
      - 'hub.mode', 'hub.verify_token', 'hub.challenge'
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def inbound():
    payload = request.get_json(force=True, silent=True) or {}
    logger.debug("Webhook payload: %s", json.dumps(payload)[:1000])

    entry = extract_message_entry(payload)
    if not entry:
        # Podría ser un evento de estado (message status) o typing, etc.
        return jsonify({"status": "ignored"}), 200

    msg = entry["message"]
    to = entry["from"]

    kind, data = classify_message(msg)
    logger.info("Mensaje clasificado: %s", kind)

    if kind == "text_link":
        handle_text_link(to, data["url"], data.get("effect"))
    elif kind == "image":
        handle_image(to, data["media_id"], data.get("caption"))
    elif kind == "video":
        handle_video(to, data["media_id"], data.get("caption"))
    elif kind == "text":
        wa_send_text(to, "Envíame un enlace, una imagen o un video con caption (logo, watermark, big [TEXTO], etc.).")
    else:
        wa_send_text(to, "Tipo de mensaje no soportado por ahora.")

    return jsonify({"status": "ok"}), 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    host = SERVER.get("host", "0.0.0.0")
    port = int(SERVER.get("port", 8000))
    debug = bool(SERVER.get("debug", False))

    required = {
        "ACCESS_TOKEN": ACCESS_TOKEN,
        "PHONE_NUMBER_ID": PHONE_NUMBER_ID,
        "VERIFY_TOKEN": VERIFY_TOKEN
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        logger.warning("Faltan variables sensibles: %s", ", ".join(missing))

    app.run(host=host, port=port, debug=debug)
