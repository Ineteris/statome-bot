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
    lines = [f"🟢 Последние отчёты:"]
    for uid, dt in last_report_time.items():
        try:
            user_obj = await context.bot.get_chat(uid)
            lines.append(f"{user_obj.full_name} — {dt.strftime('%d.%m %H:%M')} UTC")
        except:
            continue
    status_message = "\n".join(lines)
    pinned = await context.bot.send_message(chat_id=GROUP_ID, text=status_message)
    await context.bot.pin_chat_message(chat_id=GROUP_ID, message_id=pinned.message_id, disable_notification=True)

# Обработчики
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != int(GROUP_ID): return

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
    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != int(GROUP_ID): return

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
    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != int(GROUP_ID): return

    user = update.effective_user
    username = user.username or "нет username"
    text = update.message.text
    message = f"Текстовый отчёт от {user.full_name} (@{username}):\n{text}"

    await context.bot.send_message(chat_id=CHANNEL_ID, text=message)
    await store_message(update.effective_chat.id, update.message.message_id)
    await update_last_report(update, context)
    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)

# Планировщик
scheduler = AsyncIOScheduler()

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
