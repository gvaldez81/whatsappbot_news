def generate_all_from_link(url: str, base_settings: Dict[str, Any],
                           editions_dir: str = "configs/articulo7/editions", effect: Optional[str] = None) -> List[Dict[str, Any]]:
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

    # FILTRO POR effect
    if effect:
        filtered = [e for e in editions if (e.get("mode") or "").lower() == effect.lower()]
        if not filtered:
            return [f"No hay configuración para el efecto solicitado: {effect}"]
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
