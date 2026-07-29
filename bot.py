import os
import json
import logging
from io import BytesIO

import numpy as np
from PIL import Image
import cv2

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


# ---------- smart placement ----------
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# candidate placements as fractional centers (dead-center deliberately excluded)
CANDIDATES = [
    ("top-left", 0.08, 0.08),
    ("top-right", 0.92, 0.08),
    ("bottom-left", 0.08, 0.92),
    ("bottom-right", 0.92, 0.92),
    ("top-center", 0.5, 0.08),
    ("bottom-center", 0.5, 0.92),
    ("middle-left", 0.08, 0.5),
    ("middle-right", 0.92, 0.5),
]


def detect_faces(gray):
    return face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))


def region_busyness(gray, cx, cy, half_w, half_h):
    """Lower score = plainer/quieter background, better place for a logo."""
    h, w = gray.shape
    x0 = max(0, int(cx - half_w))
    x1 = min(w, int(cx + half_w))
    y0 = max(0, int(cy - half_h))
    y1 = min(h, int(cy + half_h))
    if x1 <= x0 or y1 <= y0:
        return 1e9
    crop = gray[y0:y1, x0:x1]
    lap = cv2.Laplacian(crop, cv2.CV_64F)
    return float(np.std(lap))


def overlaps_face(cx, cy, half_w, half_h, faces, pad=0.25):
    for (fx, fy, fw, fh) in faces:
        fx0, fy0 = fx - fw * pad, fy - fh * pad
        fx1, fy1 = fx + fw * (1 + pad), fy + fh * (1 + pad)
        bx0, bx1 = cx - half_w, cx + half_w
        by0, by1 = cy - half_h, cy + half_h
        if bx0 < fx1 and bx1 > fx0 and by0 < fy1 and by1 > fy0:
            return True
    return False


def rank_placements(pil_img, logo_w, logo_h):
    gray = cv2.cvtColor(np.array(pil_img.convert("RGB")), cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    faces = detect_faces(gray)

    scored = []
    for name, fx, fy in CANDIDATES:
        cx, cy = fx * w, fy * h
        half_w, half_h = logo_w / 2, logo_h / 2
        face_penalty = 1e6 if overlaps_face(cx, cy, half_w, half_h, faces) else 0
        busy = region_busyness(gray, cx, cy, half_w, half_h)
        scored.append((busy + face_penalty, name, fx, fy))

    scored.sort(key=lambda t: t[0])
    return scored


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
        "Send me a photo and I'll return 3 versions with your logo placed in the "
        "spots that best fit that image.\n\n"
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

    w, _ = base_img.size
    approx_logo_w = w * size_percent / 100
    approx_logo_h = approx_logo_w * logo_img.height / logo_img.width

    ranked = rank_placements(base_img, approx_logo_w, approx_logo_h)
    top3 = ranked[:3]

    media = []
    for i, (score, name, fx, fy) in enumerate(top3):
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
