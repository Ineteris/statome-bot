from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import time
import asyncio
import logging
import os

from telegram.constants import ParseMode
from fastapi import FastAPI, Request
from telegram.ext import WebhookHandler

# Настройка логгирования
logging.basicConfig(level=logging.INFO)

# Получение токенов и ID канала из переменных окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # например, https://statome-bot.onrender.com

# Хранилище для удаления сообщений
message_log = {}  # {chat_id: [message_id, ...]}

app_fastapi = FastAPI()

# Telegram Application
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = update.effective_user.language_code
    message = "Здравствуйте, отправьте ваше видео, фото или текстовый отчёт по работе." \
        if lang != 'es' else "Hola, envíame tu video, foto o informe escrito de trabajo."
    sent = await update.message.reply_text(message)
    await store_message(update.effective_chat.id, sent.message_id)

# Хелпер: сохранить message_id
async def store_message(chat_id: int, message_id: int):
    message_log.setdefault(chat_id, []).append(message_id)

# Обработка видео и видео-документов с подписью
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    video = update.message.video or update.message.document
    username = user.username or "нет username"
    user_caption = update.message.caption or ""

    caption = f"Отчёт от {user.full_name} (@{username})"
    if user_caption:
        caption += f"\n\n{user_caption}"

    await context.bot.send_video(
        chat_id=CHANNEL_ID,
        video=video.file_id,
        caption=caption
    )
    reply = "Отчёт получен. Спасибо!" if user.language_code != 'es' else "Informe recibido. ¡Gracias!"
    sent = await update.message.reply_text(reply)
    await store_message(update.effective_chat.id, update.message.message_id)
    await store_message(update.effective_chat.id, sent.message_id)

# Обработка текста
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = user.username or "нет username"
    text = update.message.text
    message = f"Текстовый отчёт от {user.full_name} (@{username}):\n{text}"

    await context.bot.send_message(chat_id=CHANNEL_ID, text=message)
    reply = "Текст получен. Спасибо!" if user.language_code != 'es' else "Texto recibido. ¡Gracias!"
    sent = await update.message.reply_text(reply)
    await store_message(update.effective_chat.id, update.message.message_id)
    await store_message(update.effective_chat.id, sent.message_id)

# Обработка фото с подписью
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    photo = update.message.photo[-1]  # самое большое качество
    username = user.username or "нет username"
    user_caption = update.message.caption or ""

    caption = f"Фотоотчёт от {user.full_name} (@{username})"
    if user_caption:
        caption += f"\n\n{user_caption}"

    await context.bot.send_photo(
        chat_id=CHANNEL_ID,
        photo=photo.file_id,
        caption=caption
    )
    reply = "Фото получено. Спасибо!" if user.language_code != 'es' else "Foto recibida. ¡Gracias!"
    sent = await update.message.reply_text(reply)
    await store_message(update.effective_chat.id, update.message.message_id)
    await store_message(update.effective_chat.id, sent.message_id)

# Задача на очистку сообщений
async def cleanup_messages(context: ContextTypes.DEFAULT_TYPE):
    logging.info("🧹 Запуск очистки сообщений")
    for chat_id, message_ids in message_log.items():
        for msg_id in message_ids:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception as e:
                logging.warning(f"⚠️ Не удалось удалить сообщение {msg_id} в чате {chat_id}: {e}")
    message_log.clear()

# Обработчики
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

# Планировщик на 00:00 UTC
scheduler = AsyncIOScheduler()
scheduler.add_job(cleanup_messages, trigger='cron', hour=0, minute=0, args=[telegram_app])

@telegram_app.post_init
async def on_startup(app):
    scheduler.start()
    logging.info("🕛 Планировщик задач запущен.")
    await app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

@app_fastapi.get("/")
async def healthcheck():
    return {"status": "ok"}

@app_fastapi.post("/webhook")
async def telegram_webhook(request: Request):
    update = await request.json()
    await telegram_app.update_queue.put(Update.de_json(update, telegram_app.bot))
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app_fastapi, host="0.0.0.0", port=port)


