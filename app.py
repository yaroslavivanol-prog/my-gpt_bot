import os
import logging
from threading import Thread
from flask import Flask
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, InlineQueryHandler, ContextTypes

# --- ТОКЕН ---
TELEGRAM_TOKEN = "8331451571:AAGTJuw2hyBnQH6ow7EavScntrHwdgO2SYQ"

logging.basicConfig(level=logging.INFO)

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip()
    if not query:
        return

    # ТУТ НЕТ НИКАКОГО API. ПРОСТО ТЕСТОВЫЙ ОТВЕТ.
    results = [
        InlineQueryResultArticle(
            id="1",
            title="ТЕСТ: Нажми чтобы отправить",
            description="Бот работает без API!",
            input_message_content=InputTextMessageContent(
                message_text=f"Твой запрос: '{query}'. Бот работает!"
            )
        )
    ]
    await update.inline_query.answer(results, cache_time=0)

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return "Bot is running"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    print("Бот запускается...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(InlineQueryHandler(inline_query_handler))
    print("Бот запущен!")
    app.run_polling(drop_pending_updates=True)
