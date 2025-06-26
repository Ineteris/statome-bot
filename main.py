from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from telegram.constants import ParseMode
from fastapi import FastAPI, Request
from telegram.helpers import escape_markdown
import logging
import asyncio
import os

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")     # STATOME | ADMINISTRACION | PARTES
GROUP_ID = os.environ.get("GROUP_ID")         # STATOME | PARTES DE TRABAJO | BOT
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# Пользователи (username -> ФИО)
USER_MAP = {
    "@CarlosPastorSempere": "00001-PASTOR SEMPERE, CARLOS",
    "@DanAkcerman": "00003-MONIN, DANILL",
    "@Oleg_dokukin": "00004-DOKUKIN, OLEH",
    "@OlegDokukin": "00004-DOKUKIN, OLEH",
    "@ViktorTiko": "A00008-VIKTOR TIKHONYCHEV"
}

# Хранилища отчётов
last_message_ids = {}      # user_id -> message_id
report_users_today = {}    # user_id -> (имя, время)

# Telegram + FastAPI
app_fastapi = FastAPI()
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# Приветствие
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    lang = update.effective_user.language_code or "ru"
    message = (
        "Здравствуйте, отправьте ваше видео, фото или текстовый отчёт по работе.\nКоманды:\n• /last — последний отчёт"
        if lang != 'es' else
        "Hola, envíame tu video, foto o informe escrito de trabajo.\nComandos:\n• /last — último informe"
    )
    await update.message.reply_text(message)

# Обработка отчётов
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE, media_type: str):
    user = update.effective_user
    username = f"@{user.username}" if user.username else ""
    full_name = user.full_name
    custom_name = USER_MAP.get(username, full_name)

    # Экранирование
    safe_name = escape_markdown(custom_name, version=2)
    safe_user = escape_markdown(username, version=2)
    caption_text = update.message.caption or update.message.text or ""
    safe_caption = escape_markdown(caption_text, version=2)

    caption = f"*{safe_name}* \\({safe_user}\\)\n{safe_caption}"

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
            user_id = user.id
            last_message_ids[user_id] = sent.message_id
            now = datetime.now()
            report_users_today[user_id] = (custom_name, now.strftime("%H:%M"))
            await update.message.reply_text("✅ Отчёт получен. Спасибо!")

    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        await update.message.reply_text("⚠️ Ошибка при отправке отчёта. Проверьте содержимое.")

# Обработчики
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_media(update, context, "video")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_media(update, context, "photo")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_media(update, context, "text")

# Команда /last
async def last_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg_id = last_message_ids.get(user_id)

    if not msg_id:
        await update.message.reply_text("❌ Ваш последний отчёт не найден.")
        return

    try:
        await context.bot.copy_message(chat_id=user_id, from_chat_id=CHANNEL_ID, message_id=msg_id)
    except Exception as e:
        logger.warning(f"Не удалось переслать отчёт: {e}")
        await update.message.reply_text("⚠️ Не удалось получить отчёт.")

# Очистка чата в 00:00
async def daily_clear_chat(context: ContextTypes.DEFAULT_TYPE):
    logger.info("🧹 Запуск ежедневной очистки сообщений группы")
    try:
        async for msg in context.bot.get_chat_history(GROUP_ID):
            try:
                await context.bot.delete_message(chat_id=GROUP_ID, message_id=msg.message_id)
            except:
                continue
    except Exception as e:
        logger.warning(f"Ошибка при очистке чата: {e}")
    finally:
        report_users_today.clear()

# Планировщик
scheduler = AsyncIOScheduler()
scheduler.add_job(daily_clear_chat, 'cron', hour=0, minute=0, args=[telegram_app])

# FastAPI
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
    logger.info("🕛 Планировщик задач запущен.")
    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

# Регистрация хендлеров
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("last", last_report))
telegram_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

# Запуск
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app_fastapi, host="0.0.0.0", port=port)
