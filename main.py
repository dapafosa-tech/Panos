import os
import logging
import requests
from io import BytesIO
from PIL import Image
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Зчитуємо змінні з Railway
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
WATERMARK_URL = os.environ.get('WATERMARK_URL')
WATERMARK_OPACITY = float(os.environ.get('WATERMARK_OPACITY', '0.5'))
WATERMARK_SIZE = int(os.environ.get('WATERMARK_SIZE', '100'))

watermark_image = None

async def load_watermark():
    """Завантажує водяний знак з URL"""
    global watermark_image
    try:
        if WATERMARK_URL:
            response = requests.get(WATERMARK_URL)
            watermark_image = Image.open(BytesIO(response.content)).convert('RGBA')
            logger.info("Водяний знак завантажено з URL")
    except Exception as e:
        logger.error(f"Не вдалося завантажити водяний знак: {e}")

async def add_watermark(image_bytes: bytes) -> BytesIO:
    global watermark_image
    
    if watermark_image is None:
        await load_watermark()
        if watermark_image is None:
            raise Exception("Водяний знак не завантажено")
    
    img = Image.open(BytesIO(image_bytes)).convert('RGBA')
    watermark = watermark_image.copy()
    
    watermark.thumbnail((WATERMARK_SIZE, WATERMARK_SIZE), Image.Resampling.LANCZOS)
    
    if WATERMARK_OPACITY < 1.0:
        pixels = watermark.load()
        for i in range(watermark.width):
            for j in range(watermark.height):
                r, g, b, a = pixels[i, j]
                pixels[i, j] = (r, g, b, int(a * WATERMARK_OPACITY))
    
    padding = 20
    x = img.width - watermark.width - padding
    y = padding
    
    img.paste(watermark, (x, y), watermark)
    result = img.convert('RGB')
    
    output = BytesIO()
    result.save(output, format='JPEG', quality=95)
    output.seek(0)
    
    return output

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if watermark_image is None:
            await load_watermark()
        
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        
        watermarked_image = await add_watermark(image_bytes)
        
        await update.message.reply_photo(
            photo=watermarked_image,
            caption="✅ Водяний знак додано!"
        )
        
    except Exception as e:
        logger.error(f"Помилка: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")

def main():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не знайдено")
        return
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    logger.info("Бот запущено")
    app.run_polling()

if __name__ == '__main__':
    main()