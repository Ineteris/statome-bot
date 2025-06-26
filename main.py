from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from datetime import datetime
import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
GROUP_ID = os.environ.get("GROUP_ID")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

USER_MAP = {
    "@CarlosPastorSempere": "00001-PASTOR SEMPERE, CARLOS",
    "@DanAkcerman": "00003-MONIN, DANILL",
    "@Oleg_dokukin": "00004-DOKUKIN, OLEH",
    "@ViktorTiko": "A00008-VIKTOR TIKHONYCHEV",
    "@OlegDokukin": "00004-DOKUKIN, OLEH"
}

last_report_time = {}
last_message_ids = {}
report_users_today = {}

app_fastapi = FastAPI()
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    lang = update.effective_user.language_code
    message = (
        "Здравствуйте, отправьте ваше видео, фото или текстовый отчёт по работе.\nКоманды:\n• /last — последний отчёт"
        if lang != 'es' else
        "Hola, envíame tu video, foto o informe escrito de trabajo.\nComandos:\n• /last — último informe"
    )
    await update.message.reply_text(message)

# Обработка любого медиа/текста
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE, media_type: str):
    user = update.effective_user
    username = f"@{user.username}" if user.username else ""
    custom_name = USER_MAP.get(username, user.full_name)

    # Экранирование всех частей
    safe_name = escape_markdown(custom_name, version=2)
    safe_user = escape_markdown(username, version=2) if username else ""
    caption_text = update.message.caption or update.message.text or ""
    safe_caption = escape_markdown(caption_text, version=2)

    caption = f"*{safe_name}* ({safe_user})\n{safe_caption}"

    sent = None
    try:
        if media_type == "video":
            video = update.message.video or update.message.document
            sent = await context.bot.send_video(chat_id=CHANNEL_ID, video=video.file_id, caption=caption, parse_mode=ParseMode.MARKDOWN_V2)

        elif media_type == "photo":
            photo = update.message.photo[-1]
            sent = await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo.file_id, caption=caption, parse_mode=ParseMode.MARKDOWN_V2)

        elif media_type == "text":
            sent = await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode=ParseMode.MARKDOWN_V2)

        if sent:
            last_message_ids[update.effective_user.id] = sent.message_id
            now = datetime.now()
            report_users_today[update.effective_user.id] = (custom_name, now.strftime("%H:%M"))
            await update.message.reply_text("✅ Отчёт получен. Спасибо!")

    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения: {e}")
        await update.message.reply_text("❌ Не удалось отправить отчёт. Проверьте формат или содержимое.")

# Обработчики по типу
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_media(update, context, "video")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_media(update, context, "photo")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_media(update, context, "text")

# Последний отчёт
async def last_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg_id = last_message_ids.get(user_id)

    if not msg_id:
        await update.message.reply_text("❌ Ваш последний отчёт не найден.")
        return

    try:
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=CHANNEL_ID,
            message_id=msg_id
        )
    except Exception as e:
        logging.warning(f"Не удалось переслать отчёт: {e}")
        await update.message.reply_text("⚠️ Не удалось получить отчёт.")

# Очистка чата
async def daily_clear_chat(context: ContextTypes.DEFAULT_TYPE):
    logging.info("🧹 Запуск ежедневной очистки сообщений группы")
    try:
        async for msg in context.bot.get_chat_history(GROUP_ID):
            try:
                await context.bot.delete_message(chat_id=GROUP_ID, message_id=msg.message_id)
            except:
                continue
    except Exception as e:
        logging.warning(f"Ошибка при очистке чата: {e}")
    finally:
        report_users_today.clear()

# Планировщик
scheduler = AsyncIOScheduler()
scheduler.add_job(daily_clear_chat, 'cron', hour=0, minute=0, args=[telegram_app])

# FastAPI endpoints
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

# Обработчики
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("last", last_report))
telegram_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app_fastapi, host="0.0.0.0", port=port)
