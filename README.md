# whatsappbot_news

A WhatsApp bot that automatically generates and sends news-style images from links or user-uploaded images, tailored for Article 7 workflows. Built for ease of newsroom automation, it leverages the WhatsApp Cloud API, modular image processors, and flexible configuration to streamline the creation of shareable graphics.

---

## 🚀 What Does It Do?

- **WhatsApp Integration:** Listens for incoming messages (either links or images) and responds with a generated image.
- **Automatic News Image Generation:** Given a news link (especially Article 7), it fetches metadata (title, image, category) and creates branded images using customizable templates.
- **Image Caption Commands:** Users can send images with captions like "logo", "watermark", "big [text]", "recorte", or "blur" to trigger specific graphic transformations.
- **Flexible Processors:** Easily extend or adjust image processing by editing or adding Python modules in the `processors/` directory.
- **Easy Configuration:** Control styles, branding, and processing logic with JSON files—no code changes required for most updates.
- **CLI for Testing:** Try image generation locally via command line before deploying.

---

## 🗂️ File & Directory Structure

```
whatsappbot_news/
├── whatsapp_bot.py         # Main WhatsApp bot, Flask API endpoints
├── generate_image.py       # Image generation engine and CLI
├── processors/             # Modular image and metadata processors
│   ├── captions.py         # Caption classification logic
│   ├── logo.py, watermark.py, big_text.py, articulo7.py
│   └── README.md           # Processor documentation
├── configs/                # Editable JSON style/config presets
├── requirements.txt        # Python dependencies
└── ...
```

---

## 📝 Example Usage

### 1. Send a Link

- User: Sends a news link (e.g., from Article 7) to the bot via WhatsApp.
- Bot: Fetches the link, extracts metadata, applies one or more graphic styles, and replies with a generated image.

### 2. Send an Image with Caption

- User: Sends an image with a caption (e.g., "logo" or "big ¡Última Hora!").
- Bot: Applies the specified transformation (adds logo, watermark, big centered text, etc.) and returns the new image.

### 3. Test Locally with CLI

```bash
python generate_image.py --link "https://articulo7.com/noticia" --output test.jpg
python generate_image.py --image sample.jpg --caption "logo" --output branded.jpg
```

---

## ⚙️ Configuration

- Edit `configs/defaults.json` and `configs/settings.json` to change default styles, logo/watermark paths, fonts, and more.
- Define edition variants in `configs/articulo7/editions/*.json` for different news templates.

---

## 🔌 Extending Processing

To add or modify how images are processed:
- Add a new Python module in `processors/`, following the documented interface.
- Update `processors/README.md` to describe your new processor and usage.
- Adjust `generate_image.py` or `captions.py` if you want new caption commands.

---

## 🏗️ Requirements

- Python 3.8+
- WhatsApp Cloud API credentials (see Meta's documentation)
- `pip install -r requirements.txt`

---

## 📚 References & Documentation

- [processors/README.md](processors/README.md): In-depth documentation for each processor and how to extend the system.
- WhatsApp Cloud API: [Meta Docs](https://developers.facebook.com/docs/whatsapp/cloud-api/)
- Article 7: https://articulo7.com/

---

## 🙋 FAQ

**Q:** _Can I add my own image styles or templates?_  
**A:** Yes! Create/edit config files in `configs/` or add new processors in `processors/`.

**Q:** _What captions are supported?_  
**A:** "logo", "watermark", "big [text]", "recorte", "blur", or any free text, which will be rendered as a title.

**Q:** _How do I deploy this bot?_  
**A:** Host the Flask app (`whatsapp_bot.py`) and configure your webhook with WhatsApp Cloud API. Set environment variables for your credentials.

---

## 📝 License

[Add your license here]

---

## 👏 Credits

Created by [gvaldez81](https://github.com/gvaldez81) and contributors.  
Built for newsroom automation and rapid news sharing.
