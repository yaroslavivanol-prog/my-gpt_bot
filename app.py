import os
import logging
from threading import Thread
from flask import Flask
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, InlineQueryHandler, ContextTypes
from openai import OpenAI

# --- ТВОИ НАСТРОЙКИ ---
TELEGRAM_TOKEN = "8331451571:AAGTJuw2hyBnQH6ow7EavScntrHwdgO2SYQ"
API_KEY = "sk-185f3c2b8f83b9e2a644ed5b1e43e712dc126e02542bacb8"
BASE_URL = "https://api.reformboss.com/v1"

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
logging.basicConfig(level=logging.INFO)

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip()
    if not query:
        return

    try:
        # ИСПОЛЬЗУЕМ ID МОДЕЛИ ИЗ БОТА ИИШКО
        response = client.chat.completions.create(
            model="deepseek-v4.1-flash", 
            messages=[{"role": "user", "content": query}],
            temperature=0.8
        )
        answer = response.choices[0].message.content

        results = [
            InlineQueryResultArticle(
                id="1",
                title="Отправить ответ ИИ",
                description=answer[:100],
                input_message_content=InputTextMessageContent(message_text=answer)
            )
        ]
        await update.inline_query.answer(results, cache_time=0)
        
    except Exception as e:
        logging.error(f"Ошибка API: {e}")
        # Выводим ошибку в меню, чтобы ты её увидел
        results = [
            InlineQueryResultArticle(
                id="err",
                title="⚠️ ОШИБКА API (нажми)",
                description=str(e)[:100],
                input_message_content=InputTextMessageContent(message_text=f"Ошибка API: {e}")
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
