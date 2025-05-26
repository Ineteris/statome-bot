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

# Соответствие username -> имя сотрудника
USER_MAP = {
    'CarlosPastorSempere': '00001-PASTOR SEMPERE, CARLOS',
    'DanAkcerman': '00003-MONIN, DANILL',
    'Oleg_dokukin': '00004-DOKUKIN, OLEH',
    'ViktorTiko': 'A00008-VIKTOR TIKHONYCHEV'
}

# Хранилища
last_report_time = {}  # {user_id: datetime}
message_ids_by_group = []

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

# Получить имя сотрудника по username
def resolve_employee_name(username, full_name):
    return USER_MAP.get(username, full_name)

# Обновить сообщение со списком отчётов
async def update_report_list(context: ContextTypes.DEFAULT_TYPE):
    members = list(last_report_time.items())
    if not members:
        return
    lines = ["🟢 Последние отчёты:"]
    for uid, dt in sorted(members, key=lambda x: x[1], reverse=True):
        try:
            user = await context.bot.get_chat(uid)
            name = resolve_employee_name(user.username, user.full_name)
            lines.append(f"{name} — {dt.strftime('%d.%m %H:%M')} UTC")
        except:
            continue
    text = "\n".join(lines)
    msg = await context.bot.send_message(chat_id=GROUP_ID, text=text)
    message_ids_by_group.append(msg.message_id)
    await context.bot.send_message(chat_id=CHANNEL_ID, text=text)

# Обработка медиа и текста
async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != int(GROUP_ID):
        return

    user = update.effective_user
    username = user.username or "нет username"
    employee_name = resolve_employee_name(username, user.full_name)
    caption = update.message.caption or ""
    message_type = ""

    if update.message.video or (update.message.document and update.message.document.mime_type.startswith('video')):
        message_type = "Отчёт (видео)"
        video = update.message.video or update.message.document
        await context.bot.send_video(chat_id=CHANNEL_ID, video=video.file_id, caption=f"{message_type} от {employee_name}\n\n{caption}")
    elif update.message.photo:
        message_type = "Фотоотчёт"
        photo = update.message.photo[-1]
        await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo.file_id, caption=f"{message_type} от {employee_name}\n\n{caption}")
    elif update.message.text:
        message_type = "Текстовый отчёт"
        await context.bot.send_message(chat_id=CHANNEL_ID, text=f"{message_type} от {employee_name}:\n{update.message.text}")
    else:
        return

    last_report_time[user.id] = datetime.utcnow()
    await update_report_list(context)

# Очистка сообщений
async def cleanup_group(context: ContextTypes.DEFAULT_TYPE):
    logging.info("🧹 Очистка сообщений в группе")
    for msg_id in message_ids_by_group:
        try:
            await context.bot.delete_message(chat_id=GROUP_ID, message_id=msg_id)
        except Exception as e:
            logging.warning(f"Не удалось удалить сообщение: {e}")
    message_ids_by_group.clear()
    await update_report_list(context)

# Планировщик
scheduler = AsyncIOScheduler()
scheduler.add_job(cleanup_group, trigger='cron', hour=0, minute=0, args=[telegram_app])

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
telegram_app.add_handler(MessageHandler(filters.ALL, handle_report))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app_fastapi, host="0.0.0.0", port=port)
