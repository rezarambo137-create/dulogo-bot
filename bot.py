import os
import json
import logging
from io import BytesIO

from PIL import Image

from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "logo.png")
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")

DEFAULT_SIZE_PERCENT = 18  # logo width as a % of the photo's width


# ---------- persisted per-chat settings ----------
def load_settings():
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, "r") as f:
            return json.load(f)
    return {}


def save_settings(data):
    with open(SETTINGS_PATH, "w") as f:
        json.dump(data, f)


settings = load_settings()


def get_size_percent(chat_id):
    return settings.get(str(chat_id), {}).get("size_percent", DEFAULT_SIZE_PERCENT)


def set_size_percent(chat_id, value):
    settings.setdefault(str(chat_id), {})["size_percent"] = value
    save_settings(settings)


# ---------- fixed placements ----------
# always place the logo in exactly these 3 spots, in this order
FIXED_PLACEMENTS = [
    ("top-center", 0.5, 0.08),
    ("middle-left", 0.08, 0.5),
    ("bottom-center", 0.5, 0.92),
]


def composite_logo(base_img, logo_img, fx, fy, size_percent):
    base = base_img.convert("RGBA")
    w, h = base.size
    logo_w = int(w * size_percent / 100)
    logo_h = int(logo_w * logo_img.height / logo_img.width)
    logo_resized = logo_img.resize((logo_w, logo_h), Image.LANCZOS)

    cx, cy = fx * w, fy * h
    x = int(cx - logo_w / 2)
    y = int(cy - logo_h / 2)
    x = max(0, min(w - logo_w, x))
    y = max(0, min(h - logo_h, y))

    out = base.copy()
    out.alpha_composite(logo_resized, (x, y))
    return out.convert("RGB")


# ---------- telegram handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        "Send me a photo and I'll return 3 versions: logo at top-center, "
        "middle-left, and bottom-center.\n\n"
        f"Current logo size: {get_size_percent(chat_id)}% of photo width.\n"
        "Change it any time with /setsize 20 (logo width as % of photo width, 5-60)."
    )


async def setsize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text(f"Current size: {get_size_percent(chat_id)}%. Usage: /setsize 20")
        return
    try:
        value = float(context.args[0])
        value = max(5, min(60, value))
    except ValueError:
        await update.message.reply_text("Please send a number, e.g. /setsize 20")
        return
    set_size_percent(chat_id, value)
    await update.message.reply_text(f"Standard logo size set to {value}% of photo width.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    size_percent = get_size_percent(chat_id)

    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    base_img = Image.open(BytesIO(bytes(photo_bytes)))

    logo_img = Image.open(LOGO_PATH)

    media = []
    for i, (name, fx, fy) in enumerate(FIXED_PLACEMENTS):
        result = composite_logo(base_img, logo_img, fx, fy, size_percent)
        buf = BytesIO()
        result.save(buf, format="JPEG", quality=95)
        buf.seek(0)
        buf.name = f"{name}.jpg"
        media.append(InputMediaPhoto(buf, caption=f"Placement: {name}" if i == 0 else name))

    await update.message.reply_media_group(media)


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Set the TELEGRAM_BOT_TOKEN environment variable")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setsize", setsize))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.run_polling()


if __name__ == "__main__":
    main()
