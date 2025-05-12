import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = update.effective_user.language_code
    if lang == 'es':
        await update.message.reply_text("Hola, envíame tu video informe de trabajo.")
    else:
        await update.message.reply_text("Здравствуйте, отправьте ваше видео с отчётом по работе.")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    video = update.message.video or update.message.document
    caption = f"Отчёт от {user.full_name} (@{user.username or 'нет username'})"
    await context.bot.send_video(chat_id=CHANNEL_ID, video=video.file_id, caption=caption)

    lang = user.language_code
    if lang == 'es':
        await update.message.reply_text("Informe recibido. ¡Gracias!")
    else:
        await update.message.reply_text("Отчёт получен. Спасибо!")

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
app.run_polling()
