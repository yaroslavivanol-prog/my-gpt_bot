import os
import logging
import time
from threading import Thread
from collections import defaultdict
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from openai import OpenAI

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
API_KEY = os.environ.get("API_KEY")
BASE_URL = "https://api.reformboss.com/v1"
CHANNEL_ID = "@claude_gpt_deepseek"
CHANNEL_LINK = "https://t.me/claude_gpt_deepseek"
BOT_LINK = "https://t.me/claude_gpt_deepseek_bot"
LIMIT_PER_HOUR = 5
RESET_INTERVAL = 3600

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

user_data = defaultdict(lambda: {
    "model": "deepseek-v4-pro",
    "requests": 0,
    "reset_time": 0,
    "bonus": 0
})

# --- ПРОВЕРКА ПОДПИСКИ ---
async def check_subscription(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
    return False

# --- КЛАВИАТУРЫ ---
def get_subscribe_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_LINK)],
        [InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")]
    ])

def get_main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🐋 DeepSeek", callback_data="set_deepseek"),
            InlineKeyboardButton("⚡ Grok", callback_data="set_grok")
        ],
        [
            InlineKeyboardButton("🧠 Qwen", callback_data="set_qwen"),
            InlineKeyboardButton("📊 Профиль", callback_data="profile")
        ]
    ])

# --- ХЕНДЛЕРЫ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = time.time()
    if now - user_data[user_id]["reset_time"] > RESET_INTERVAL:
        user_data[user_id]["requests"] = 0
        user_data[user_id]["reset_time"] = now

    if not await check_subscription(user_id, context):
        await update.message.reply_text(
            "👋 Добро пожаловать!\n\n"
            "Чтобы пользоваться ботом, подпишитесь на наш канал:\n"
            f"👉 {CHANNEL_ID}\n\n"
            "После подписки нажмите кнопку ниже.",
            reply_markup=get_subscribe_keyboard()
        )
        return

    await update.message.reply_text(
        "👋 Привет! Я бот *DeepSeek | Grok | Qwen*.\n\n"
        "Выбери модель и напиши вопрос 👇\n\n"
        f"📊 Лимит: {LIMIT_PER_HOUR} запросов в час.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if data == "check_sub":
        if await check_subscription(user_id, context):
            await query.answer("✅ Спасибо за подписку!", show_alert=False)
            await query.edit_message_text(
                "✅ *Спасибо за подписку!*\n\n"
                "Теперь выбери модель и напиши свой вопрос.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        else:
            await query.answer("❌ Вы ещё не подписались на канал!", show_alert=True)
        return

    if not await check_subscription(user_id, context):
        await query.answer("❌ Сначала подпишитесь на канал!", show_alert=True)
        return

    if data.startswith("set_"):
        model_map = {
            "set_deepseek": "deepseek-v4-pro",
            "set_grok": "grok-4.7",
            "set_qwen": "qwen3.8-max"
        }
        model_name = model_map.get(data)
        if model_name:
            user_data[user_id]["model"] = model_name
            await query.answer(f"Модель: {model_name}")
            await query.edit_message_text(
                f"✅ Модель изменена на *{model_name}*\n\nНапиши свой вопрос.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        return

    if data == "profile":
        info = user_data[user_id]
        total = LIMIT_PER_HOUR + info["bonus"]
        await query.edit_message_text(
            f"📊 *Ваш профиль*\n\n"
            f"Модель: `{info['model']}`\n"
            f"Использовано: {info['requests']} / {total}\n"
            f"Бонус: +{info['bonus']}\n\n"
            f"🔗 Ваша реф-ссылка:\n`{BOT_LINK}?start={user_id}`",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    if not await check_subscription(user_id, context):
        await update.message.reply_text(
            f"❌ *Доступ закрыт*\n\n"
            f"Чтобы продолжить, подпишитесь на канал:\n👉 {CHANNEL_ID}",
            parse_mode="Markdown",
            reply_markup=get_subscribe_keyboard()
        )
        return

    now = time.time()
    data = user_data[user_id]
    if now - data["reset_time"] > RESET_INTERVAL:
        data["requests"] = 0
        data["reset_time"] = now

    total_limit = LIMIT_PER_HOUR + data["bonus"]
    if data["requests"] >= total_limit:
        await update.message.reply_text(
            f"⚠️ *Лимит исчерпан*\n\n"
            f"У вас {total_limit} запросов в час. Лимит обновится через "
            f"{int((data['reset_time'] + RESET_INTERVAL - now) / 60)} мин.\n\n"
            f"Или пригласите друга и получите +10 запросов:\n"
            f"`{BOT_LINK}?start={user_id}`",
            parse_mode="Markdown"
        )
        return

    try:
        await update.message.chat.send_action(action="typing")
        response = client.chat.completions.create(
            model=data["model"],
            messages=[{"role": "user", "content": user_text}]
        )
        data["requests"] += 1
        answer = response.choices[0].message.content
        left = total_limit - data["requests"]
        await update.message.reply_text(
            f"{answer}\n\n_Осталось: {left} запросов_",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await update.message.reply_text("⚠️ Ошибка. Попробуйте позже.")

# --- ВЕБ-СЕРВЕР ---
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
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен!")
    app.run_polling(drop_pending_updates=True)
