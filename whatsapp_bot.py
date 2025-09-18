def handle_text_link(link):
    # Lógica existente para manejar el link
    images = generate_all_from_link(link)  # Generar todas las imágenes
    for image in images:
        send_image(image)  # Enviar cada imagen generada

# Resto del código...