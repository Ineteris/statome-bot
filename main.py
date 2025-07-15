from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from fastapi.responses import Response
from fastapi import FastAPI, Request
from telegram.constants import ParseMode
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
    "@OlegDokukin": "00004-DOKUKIN, OLEH",
    "@ViktorTiko": "A00008-VIKTOR TIKHONYCHEV"
}

last_message_ids = {}         # user_id: message_id
report_users_today = {}       # user_id: (name, time)

app_fastapi = FastAPI()
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# HEAD-запрос для Render мониторинга
@app_fastapi.head("/webhook")
async def webhook_head():
    return Response(status_code=200)

# Healthcheck
@app_fastapi.get("/")
async def healthcheck():
    return {"status": "ok"}

@app_fastapi.post("/webhook")
async def telegram_webhook(request: Request):
    update_dict = await request.json()
    update = Update.de_json(update_dict, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"status": "ok"}

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    lang = update.effective_user.language_code
    text = (
        "Здравствуйте, отправьте ваше видео, фото или текстовый отчёт по работе.\nКоманды:\n• /last — последний отчёт"
        if lang != 'es' else
        "Hola, envíame tu video, foto o informe escrito de trabajo.\nComandos:\n• /last — último informe"
    )
    await update.message.reply_text(text)

# Команда /last
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
        logging.error(f"Ошибка при пересылке отчёта: {e}")
        await update.message.reply_text("⚠️ Не удалось получить отчёт.")

# Универсальный обработчик медиа
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE, media_type: str):
    user = update.effective_user
    username = f"@{user.username}" if user.username else None
    custom_name = USER_MAP.get(username, user.full_name)
    caption_text = update.message.caption or update.message.text or ""
    # Экранируем символы Markdown
    safe_caption = caption_text.replace("(", "\\(").replace(")", "\\)")
    final_caption = f"*{custom_name}* ({username or '-'})\n{safe_caption}"

    try:
        if media_type == "video":
            video = update.message.video or update.message.document
            sent = await context.bot.send_video(chat_id=CHANNEL_ID, video=video.file_id, caption=final_caption, parse_mode=ParseMode.MARKDOWN_V2)

        elif media_type == "photo":
            photo = update.message.photo[-1]
            sent = await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo.file_id, caption=final_caption, parse_mode=ParseMode.MARKDOWN_V2)

        elif media_type == "text":
            sent = await context.bot.send_message(chat_id=CHANNEL_ID, text=final_caption, parse_mode=ParseMode.MARKDOWN_V2)

        if sent:
            user_id = update.effective_user.id
            last_message_ids[user_id] = sent.message_id
            report_users_today[user_id] = (custom_name, datetime.now().strftime("%H:%M"))
            await update.message.reply_text("✅ Отчёт получен. Спасибо!")

    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при пересылке. Попробуйте позже.")

# Очистка чата ежедневно
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

@telegram_app.on_startup
async def on_startup(application):
    scheduler.start()
    logging.info("🕛 Планировщик задач запущен.")
    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

# Обработчики
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("last", last_report))
telegram_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, lambda u, c: handle_media(u, c, "video")))
telegram_app.add_handler(MessageHandler(filters.PHOTO, lambda u, c: handle_media(u, c, "photo")))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: handle_media(u, c, "text")))

# Запуск
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app_fastapi, host="0.0.0.0", port=port)
