from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import asyncio
import logging
import os

from telegram.constants import ParseMode
from fastapi import FastAPI, Request

# Настройка логгирования
logging.basicConfig(level=logging.INFO)

# Получение токенов и ID канала и группы из переменных окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")     # Админ-канал для пересылки
GROUP_ID = os.environ.get("GROUP_ID")           # Группа, где бот работает
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# Хранилища
message_log = {}  # {chat_id: [message_id, ...]}
last_report_time = {}  # {user_id: datetime}

app_fastapi = FastAPI()
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    lang = update.effective_user.language_code
    message = "Здравствуйте, отправьте ваше видео, фото или текстовый отчёт по работе." \
        if lang != 'es' else "Hola, envíame tu video, foto o informe escrito de trabajo."
    await update.message.reply_text(message)

# Хелперы
async def store_message(chat_id: int, message_id: int):
    message_log.setdefault(chat_id, []).append(message_id)

async def update_last_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    last_report_time[user.id] = datetime.utcnow()
    await update_status_message(context)

async def update_status_message(context: ContextTypes.DEFAULT_TYPE):
    lines = ["🟢 Последние отчёты:"]
    to_delete = []
    for uid, dt in last_report_time.items():
        try:
            user_obj = await context.bot.get_chat(uid)
            lines.append(f"{user_obj.full_name} — {dt.strftime('%d.%m %H:%M')} UTC")
        except:
            to_delete.append(uid)
    for uid in to_delete:
        del last_report_time[uid]
    status_message = "\n".join(lines)
    await context.bot.send_message(chat_id=GROUP_ID, text=status_message)

# Обработчики
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    video = update.message.video or update.message.document
    username = user.username or "нет username"
    user_caption = update.message.caption or ""

    caption = f"Отчёт от {user.full_name} (@{username})"
    if user_caption:
        caption += f"\n\n{user_caption}"

    await context.bot.send_video(chat_id=CHANNEL_ID, video=video.file_id, caption=caption)
    await store_message(update.effective_chat.id, update.message.message_id)
    await update_last_report(update, context)
    reply = "Отчёт получен. Спасибо!" if user.language_code != 'es' else "Informe recibido. ¡Gracias!"
    await update.message.reply_text(reply)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    photo = update.message.photo[-1]
    username = user.username or "нет username"
    user_caption = update.message.caption or ""

    caption = f"Фотоотчёт от {user.full_name} (@{username})"
    if user_caption:
        caption += f"\n\n{user_caption}"

    await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo.file_id, caption=caption)
    await store_message(update.effective_chat.id, update.message.message_id)
    await update_last_report(update, context)
    reply = "Фото получено. Спасибо!" if user.language_code != 'es' else "Foto recibida. ¡Gracias!"
    await update.message.reply_text(reply)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = user.username or "нет username"
    text = update.message.text
    message = f"Текстовый отчёт от {user.full_name} (@{username}):\n{text}"

    await context.bot.send_message(chat_id=CHANNEL_ID, text=message)
    await store_message(update.effective_chat.id, update.message.message_id)
    await update_last_report(update, context)
    reply = "Текст получен. Спасибо!" if user.language_code != 'es' else "Texto recibido. ¡Gracias!"
    await update.message.reply_text(reply)

# Очистка сообщений в группе
async def cleanup_messages():
    logging.info("🧹 Ежедневная очистка сообщений в группе")
    try:
        async for message in telegram_app.bot.get_chat_history(chat_id=GROUP_ID, limit=100):
            if not message.pinned:
                try:
                    await telegram_app.bot.delete_message(chat_id=GROUP_ID, message_id=message.message_id)
                except:
                    continue
    except Exception as e:
        logging.warning(f"Ошибка при очистке: {e}")
    await update_status_message(telegram_app)

# Планировщик
scheduler = AsyncIOScheduler()
scheduler.add_job(cleanup_messages, trigger='cron', hour=0, minute=0)

@app_fastapi.get("/")
async def healthcheck():
    return {"status": "ok"}

@app_fastapi.post("/webhook")
async def telegram_webhook(request: Request):
    update_dict = await request.json()
    update = Update.de_json(update_dict, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"status": "ok"}

@app_fastapi.on_event("startup")
async def on_startup():
    scheduler.start()
    logging.info("🕛 Планировщик задач запущен.")
    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app_fastapi, host="0.0.0.0", port=port)
