from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

import logging
logging.basicConfig(level=logging.INFO)

# 👉 Ваши переменные
import os
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")  # Например: -1002503054673

# 🟢 Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = update.effective_user.language_code
    message = "Здравствуйте, отправьте ваше видео или текстовый отчёт по работе." \
        if lang != 'es' else "Hola, envíame tu video o informe escrito de trabajo."
    await update.message.reply_text(message)

# 🟡 Обработка видео
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    video = update.message.video or update.message.document
    username = user.username or "нет username"
    caption = f"Отчёт от {user.full_name} (@{username})"
    await context.bot.send_video(
        chat_id=CHANNEL_ID,
        video=video.file_id,
        caption=caption
    )
    lang = user.language_code
    reply = "Отчёт получен. Спасибо!" if lang != 'es' else "Informe recibido. ¡Gracias!"
    await update.message.reply_text(reply)

# 🔵 Обработка текста
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = user.username or "нет username"
    text = update.message.text
    message = f"Текстовый отчёт от {user.full_name} (@{username}):\n{text}"
    await context.bot.send_message(chat_id=CHANNEL_ID, text=message)
    reply = "Текст получен. Спасибо!" if user.language_code != 'es' else "Texto recibido. ¡Gracias!"
    await update.message.reply_text(reply)

# 🚀 Запуск
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.run_polling()
