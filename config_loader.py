# config_loader.py
import os
import json

def load_json(path):
    """Carga un archivo JSON y devuelve un dict."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def merge_dict(base, override):
    """
    Mezcla dos diccionarios de forma recursiva.
    - base: dict original
    - override: dict con valores que sobrescriben
    """
    result = base.copy()
    for k, v in override.items():
        if isinstance(v, dict) and k in result and isinstance(result[k], dict):
            result[k] = merge_dict(result[k], v)
        else:
            result[k] = v
    return result

def apply_env_overrides(config):
    """
    Reemplaza valores de config con variables de entorno si existen.
    Ejemplo:
      config["whatsapp"]["access_token"] = os.getenv("WHATSAPP_TOKEN", valor_actual)
    """
    whatsapp = config.get("whatsapp", {})
    whatsapp["access_token"] = os.getenv("WHATSAPP_TOKEN", whatsapp.get("access_token"))
    whatsapp["phone_number_id"] = os.getenv("WHATSAPP_PHONE_ID", whatsapp.get("phone_number_id"))
    whatsapp["verify_token"] = os.getenv("WHATSAPP_VERIFY_TOKEN", whatsapp.get("verify_token"))
    config["whatsapp"] = whatsapp
    return config

def load_config(settings_path="settings.json", override_path=None):
    """
    Carga la configuración completa:
      1. settings.json
      2. override (si se pasa)
      3. variables de entorno
    """
    config = load_json(settings_path)

    if override_path:
        override = load_json(override_path)
        config = merge_dict(config, override)

    config = apply_env_overrides(config)
    return config
