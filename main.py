from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import logging
import os

from telegram.constants import ParseMode
from fastapi import FastAPI, Request

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
GROUP_ID = int(os.environ.get("GROUP_ID"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

last_report_time = {}  # {user_id: datetime}

app_fastapi = FastAPI()
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    lang = update.effective_user.language_code
    message = "Здравствуйте, отправьте ваше видео, фото или текстовый отчёт по работе.\nПосле отправки он будет автоматически переслан администрации. Спасибо!" \
        if lang != 'es' else "Hola, envíame tu video, foto o informe escrito de trabajo.\nSerá reenviado automáticamente a la administración. ¡Gracias!"
    await update.message.reply_text(message)

async def update_last_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    last_report_time[user.id] = datetime.utcnow()
    lines = [f"🟢 Последние отчёты / Últimos informes:"]
    for uid, dt in sorted(last_report_time.items(), key=lambda x: x[1], reverse=True):
        try:
            user_obj = await context.bot.get_chat(uid)
            lines.append(f"{user_obj.full_name} — {dt.strftime('%d.%m %H:%M')} UTC")
        except:
            continue
    status_message = "\n".join(lines)
    await context.bot.send_message(chat_id=GROUP_ID, text=status_message)

async def process_report(update: Update, context: ContextTypes.DEFAULT_TYPE, media_type: str):
    user = update.effective_user
    username = user.username or "нет username"
    caption = f"Отчёт от {user.full_name} (@{username})"
    user_caption = update.message.caption or ""
    if user_caption:
        caption += f"\n\n{user_caption}"

    if media_type == "video":
        video = update.message.video or update.message.document
        await context.bot.send_video(chat_id=CHANNEL_ID, video=video.file_id, caption=caption)
    elif media_type == "photo":
        photo = update.message.photo[-1]
        await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo.file_id, caption=caption)
    elif media_type == "text":
        text = update.message.text
        message = f"Текстовый отчёт от {user.full_name} (@{username}):\n{text}"
        await context.bot.send_message(chat_id=CHANNEL_ID, text=message)

    reply = "Спасибо, отчёт получен." if user.language_code != 'es' else "Gracias, informe recibido."
    await update.message.reply_text(reply)

    await update_last_report(update, context)
    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID: return
    await process_report(update, context, media_type="video")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID: return
    await process_report(update, context, media_type="photo")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID: return
    await process_report(update, context, media_type="text")

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
