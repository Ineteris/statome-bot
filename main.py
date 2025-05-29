from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import asyncio
import logging
import os

from telegram.constants import ParseMode
from fastapi import FastAPI, Request

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
GROUP_ID = os.environ.get("GROUP_ID")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

USER_MAP = {
    "@CarlosPastorSempere": "00001-PASTOR SEMPERE, CARLOS",
    "@DanAkcerman": "00003-MONIN, DANILL",
    "@Oleg_dokukin": "00004-DOKUKIN, OLEH",
    "@ViktorTiko": "A00008-VIKTOR TIKHONYCHEV"
}

last_report_time = {}  # {user_id: datetime}
last_report_message_id = None

app_fastapi = FastAPI()
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    lang = update.effective_user.language_code
    message = "Здравствуйте, отправьте ваше видео, фото или текстовый отчёт по работе." \
        if lang != 'es' else "Hola, envíame tu video, foto o informe escrito de trabajo."
    await update.message.reply_text(message)

async def update_last_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_report_message_id
    user = update.effective_user
    last_report_time[user.id] = datetime.utcnow()
    lines = ["🟢 Последние отчёты сотрудников:"]
    for uid, dt in sorted(last_report_time.items(), key=lambda x: x[1], reverse=True):
        try:
            user_obj = await context.bot.get_chat(uid)
            username = f"@{user_obj.username}" if user_obj.username else None
            custom_name = USER_MAP.get(username, user_obj.full_name)
            lines.append(f"{custom_name} — {dt.strftime('%d.%m %H:%M')} UTC")
        except:
            continue
    status_message = "\n".join(lines)
    msg = await context.bot.send_message(chat_id=GROUP_ID, text=status_message)
    last_report_message_id = msg.message_id

async def daily_clear_chat(context: ContextTypes.DEFAULT_TYPE):
    global last_report_message_id
    logging.info("🧹 Запуск ежедневной очистки сообщений группы")
    await context.bot.send_message(GROUP_ID, "Очистка завершена. Обновлён список отчётности сотрудников.")
    if last_report_message_id:
        await context.bot.pin_chat_message(chat_id=GROUP_ID, message_id=last_report_message_id, disable_notification=True)

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE, media_type: str):
    user = update.effective_user
    username = f"@{user.username}" if user.username else None
    custom_name = USER_MAP.get(username, user.full_name)
    caption_text = update.message.caption or update.message.text or ""
    caption = f"**{custom_name}** ({username})\n{caption_text}"

    if media_type == "video":
        video = update.message.video or update.message.document
        await context.bot.send_video(chat_id=CHANNEL_ID, video=video.file_id, caption=caption, parse_mode=ParseMode.MARKDOWN)
    elif media_type == "photo":
        photo = update.message.photo[-1]
        await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo.file_id, caption=caption, parse_mode=ParseMode.MARKDOWN)
    elif media_type == "text":
        await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode=ParseMode.MARKDOWN)

    await update_last_report(update, context)

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_media(update, context, "video")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_media(update, context, "photo")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_media(update, context, "text")

scheduler = AsyncIOScheduler()
scheduler.add_job(daily_clear_chat, 'cron', hour=0, minute=0, args=[telegram_app])

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
