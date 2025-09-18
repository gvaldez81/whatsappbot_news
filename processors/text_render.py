from PIL import Image, ImageDraw, ImageFont

def get_title_lines(title_text, font_path, font_size, tracking, max_width, max_lines):
    # print ("texto = "+title_text)
    # print ("font_path = "+font_path)
    # print ("font_size = "+str(font_size))
    # print ("tracking = "+str(tracking))
    # print ("max_width = "+str(max_width))
    # print ("max_lines = "+str(max_lines))

    font = ImageFont.truetype(font_path, font_size)
    words = title_text.upper().split()

    lines = []
    current_line = ""
    index = 0

    def char_width(c):
        bbox = font.getbbox(c)
        return (bbox[2] - bbox[0]) if c != " " else (font.getbbox(" ")[2] - font.getbbox(" ")[0])

    def text_width(text):
        width = 0
        for c in text:
            if c != " ":
                width += max(char_width(c) + tracking, 1)
            else:
                width += char_width(" ")
        return width

    while index < len(words) and len(lines) < max_lines - 1:
        word = words[index]
        test_line = (current_line + " " + word).strip() if current_line else word
        if text_width(test_line) <= max_width:
            current_line = test_line
            index += 1
        else:
            if current_line:
                lines.append(current_line)
            else:
                # Palabra más larga que el ancho: forzar truncado
                lines.append(word)
                index += 1
            current_line = ""
    if current_line:
        lines.append(current_line)

    remaining_words = words[index:]
    last_line = " ".join(remaining_words)

    if len(lines) == max_lines - 1:
        if text_width(last_line) <= max_width:
            lines.append(last_line)
        else:
            for i in range(len(remaining_words)):
                candidate = " ".join(remaining_words[:i + 1]) + "..."
                if text_width(candidate) > max_width:
                    lines.append(" ".join(remaining_words[:i]) + "...")
                    break
            else:
                lines.append(last_line)
    elif len(lines) < max_lines:
        lines.append("")

    return lines

def draw_title_lines(img, lines, x, y, font_path, font_size, tracking, line_spacing, shadow_offset, shadow_opacity):
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)

    current_y = y
    for line in lines:
        current_x = x
        # sombra
        for char in line:
            if char != ' ':
                bbox = font.getbbox(char)
                char_width = bbox[2] - bbox[0] + tracking
                draw.text(
                    (current_x + shadow_offset[0], current_y + shadow_offset[1]),
                    char, font=font, fill=(0, 0, 0, int(255 * shadow_opacity))
                )
                current_x += max(char_width, 1)
            else:
                current_x += font.getbbox(' ')[2] - font.getbbox(' ')[0]

        # texto principal
        current_x = x
        for char in line:
            if char != ' ':
                bbox = font.getbbox(char)
                char_width = bbox[2] - bbox[0] + tracking
                draw.text((current_x, current_y), char, font=font, fill="white")
                current_x += max(char_width, 1)
            else:
                current_x += font.getbbox(' ')[2] - font.getbbox(' ')[0]

        # avanzar Y según altura de línea + espaciado
        _, _, _, line_h = font.getbbox(line)
        current_y += (line_h - font.getbbox("A")[1]) + line_spacing


def draw_category_text(img, category_text, font_path, font_size, padding, border_color, shadow_offset, border_thickness, x, y):
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)
    category_text = category_text.upper()

    bbox = font.getbbox(category_text)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Sombra
    draw.text((x + shadow_offset[0], y + shadow_offset[1]), category_text, font=font, fill="black")
    # Texto
    draw.text((x, y), category_text, font=font, fill="white")

    # Bordes decorativos
    draw.line(
        [(x, y + text_height + padding), (x + text_width + padding, y + text_height + padding)],
        fill=border_color, width=border_thickness
    )
    draw.line(
        [(x + text_width + padding, y), (x + text_width + padding, y + text_height + padding)],
        fill=border_color, width=border_thickness
    )
