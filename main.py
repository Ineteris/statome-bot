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
last_message_ids = {}  # {user_id: message_id}
report_users_today = set()

app_fastapi = FastAPI()
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    lang = update.effective_user.language_code
    message = "Здравствуйте, отправьте ваше видео, фото или текстовый отчёт по работе." \
        if lang != 'es' else "Hola, envíame tu video, foto o informe escrito de trabajo."
    await update.message.reply_text(message)

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE, media_type: str):
    user = update.effective_user
    username = f"@{user.username}" if user.username else None
    custom_name = USER_MAP.get(username, user.full_name)
    caption_text = update.message.caption or update.message.text or ""
    caption = f"**{custom_name}** ({username})\n{caption_text}"

    sent = None
    if media_type == "video":
        video = update.message.video or update.message.document
        sent = await context.bot.send_video(chat_id=CHANNEL_ID, video=video.file_id, caption=caption, parse_mode=ParseMode.MARKDOWN)

    elif media_type == "photo":
        photo = update.message.photo[-1]
        sent = await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo.file_id, caption=caption, parse_mode=ParseMode.MARKDOWN)

    elif media_type == "text":
        sent = await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode=ParseMode.MARKDOWN)

    if sent:
        last_message_ids[update.effective_user.id] = sent.message_id
        report_users_today.add(update.effective_user.id)

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_media(update, context, "video")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_media(update, context, "photo")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_media(update, context, "text")

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

async def daily_clear_chat(context: ContextTypes.DEFAULT_TYPE):
    logging.info("🧹 Запуск ежедневной очистки сообщений группы")
    async for msg in context.bot.get_chat_history(GROUP_ID):
        try:
            await context.bot.delete_message(chat_id=GROUP_ID, message_id=msg.message_id)
        except:
            continue
    report_users_today.clear()
    await context.bot.send_message(GROUP_ID, "✅ Чат очищен. Отчёты можно продолжать отправлять.")

async def daily_report_reminder(context: ContextTypes.DEFAULT_TYPE):
    all_user_ids = list(USER_MAP.keys())
    notified = []
    for tg_name, full_name in USER_MAP.items():
        user = next((u for u in context.bot_data.values() if u.username and f"@{u.username}" == tg_name), None)
        if user and user.id not in report_users_today:
            try:
                await context.bot.send_message(user.id, "⚠️ Напоминание: вы не отправили отчёт сегодня. Пожалуйста, не забудьте.")
                notified.append(tg_name)
            except:
                continue
    logging.info(f"🔔 Уведомления отправлены: {notified}")

scheduler = AsyncIOScheduler()
scheduler.add_job(daily_clear_chat, 'cron', hour=0, minute=0, args=[telegram_app])
scheduler.add_job(daily_report_reminder, 'cron', hour=21, minute=0, args=[telegram_app])

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
telegram_app.add_handler(CommandHandler("last", last_report))
telegram_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app_fastapi, host="0.0.0.0", port=port)
