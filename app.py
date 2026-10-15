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
LIMIT_PER_HOUR = 10
RESET_INTERVAL = 3600

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
logging.basicConfig(level=logging.INFO)

user_data = defaultdict(lambda: {
    "model": "deepseek-v4-pro",
    "model_name": "DeepSeek",
    "requests": 0,
    "reset_time": 0,
    "bonus": 0,
    "referred_by": None,
    "is_busy": False
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

def get_main_keyboard(current_model="DeepSeek"):
    models = [
        ("🐋 DeepSeek", "set_deepseek", "DeepSeek"),
        ("⚡ Grok", "set_grok", "Grok"),
        ("🧠 Qwen", "set_qwen", "Qwen")
    ]
    keyboard = []
    for label, callback, name in models:
        prefix = "✅ " if name == current_model else ""
        keyboard.append([InlineKeyboardButton(f"{prefix}{label}", callback_data=callback)])
    keyboard.append([
        InlineKeyboardButton("📊 Профиль", callback_data="profile"),
        InlineKeyboardButton("❓ Помощь", callback_data="help")
    ])
    keyboard.append([InlineKeyboardButton("📤 Поделиться ботом", callback_data="share")])
    return InlineKeyboardMarkup(keyboard)

def get_limit_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Получить больше", callback_data="get_more")],
        [InlineKeyboardButton("👥 Пригласить друга (+10)", callback_data="invite")],
        [InlineKeyboardButton("📊 Профиль", callback_data="profile")]
    ])

# --- ХЕНДЛЕРЫ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = time.time()

    if context.args:
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user_id and user_data[user_id]["referred_by"] is None:
                user_data[user_id]["referred_by"] = referrer_id
                user_data[referrer_id]["bonus"] += 10
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text="🎉 По вашей ссылке пришёл новый пользователь!\n+10 запросов."
                )
        except Exception as e:
            logging.error(f"Ошибка рефералки: {e}")

    if now - user_data[user_id]["reset_time"] > RESET_INTERVAL:
        user_data[user_id]["requests"] = 0
        user_data[user_id]["reset_time"] = now

    if not await check_subscription(user_id, context):
        await update.message.reply_text(
            "👋 Добро пожаловать!\n\nЧтобы пользоваться ботом, подпишитесь на канал:\n"
            f"👉 {CHANNEL_ID}\n\nПосле подписки нажмите кнопку ниже.",
            reply_markup=get_subscribe_keyboard()
        )
        return

    info = user_data[user_id]
    total = LIMIT_PER_HOUR + info["bonus"]
    left = total - info["requests"]
    await update.message.reply_text(
        f"👋 Привет! Я бот *DeepSeek | Grok | Qwen*.\n\n"
        f"Текущая модель: *{info['model_name']}*\n"
        f"Осталось запросов: *{left}*\n\n"
        "Выбери модель или напиши вопрос 👇",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(info["model_name"])
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if data == "check_sub":
        if await check_subscription(user_id, context):
            await query.answer("✅ Спасибо за подписку!", show_alert=False)
            info = user_data[user_id]
            await query.edit_message_text(
                f"✅ *Спасибо за подписку!*\n\n"
                f"Текущая модель: *{info['model_name']}*\n\n"
                "Напиши свой вопрос.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(info["model_name"])
            )
        else:
            await query.answer("❌ Вы ещё не подписались!", show_alert=True)
        return

    if not await check_subscription(user_id, context):
        await query.answer("❌ Сначала подпишитесь на канал!", show_alert=True)
        return

    if data.startswith("set_"):
        model_map = {
            "set_deepseek": ("deepseek-v4-pro", "DeepSeek"),
            "set_grok": ("grok-4.7", "Grok"),
            "set_qwen": ("qwen3.8-max", "Qwen")
        }
        model_id, model_name = model_map.get(data, ("deepseek-v4-pro", "DeepSeek"))
        user_data[user_id]["model"] = model_id
        user_data[user_id]["model_name"] = model_name
        await query.answer(f"Модель: {model_name}")
        info = user_data[user_id]
        total = LIMIT_PER_HOUR + info["bonus"]
        left = total - info["requests"]
        await query.edit_message_text(
            f"✅ *Модель изменена на {model_name}*\n\n"
            f"Осталось запросов: *{left}*\n\nНапиши свой вопрос.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(model_name)
        )
        return

    if data == "profile":
        info = user_data[user_id]
        total = LIMIT_PER_HOUR + info["bonus"]
        ref_link = f"{BOT_LINK}?start={user_id}"
        await query.edit_message_text(
            f"📊 *Ваш профиль*\n\n"
            f"Модель: *{info['model_name']}*\n"
            f"Использовано: {info['requests']} / {total}\n"
            f"Бонусные запросы: +{info['bonus']}\n\n"
            f"🔗 Ваша реф-ссылка:\n`{ref_link}`\n\n"
            "За каждого друга — +10 запросов!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 Пригласить друга", callback_data="invite")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back")]
            ])
        )
        return

    if data == "help":
        await query.edit_message_text(
            "❓ *Помощь*\n\n"
            "📌 *Как пользоваться ботом:*\n"
            "1. Выбери модель (DeepSeek, Grok, Qwen)\n"
            "2. Напиши вопрос — получи ответ\n"
            "3. У тебя 10 бесплатных запросов в час\n\n"
            "🎁 *Как получить больше:*\n"
            "• Пригласи друга — +10 запросов\n"
            "• Подписка 299 ₽/мес (скоро)\n\n"
            "📢 *Подписка на канал обязательна:*\n"
            f"{CHANNEL_LINK}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="back")]
            ])
        )
        return

    if data == "share":
        share_text = "🤖 Попробуй бота с нейросетями — DeepSeek, Grok, Qwen!\n\n10 запросов в час бесплатно."
        share_url = f"https://t.me/share/url?url={BOT_LINK}&text={share_text}"
        await query.answer("Спасибо за поддержку! 🙏", show_alert=False)
        await query.edit_message_text(
            "📤 *Поделиться ботом*\n\n"
            "Спасибо, что помогаешь проекту!\n\n"
            "Нажми кнопку ниже — и выбери чат, куда отправить.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Поделиться", url=share_url)],
                [InlineKeyboardButton("◀️ Назад", callback_data="back")]
            ])
        )
        return

    if data == "get_more":
        ref_link = f"{BOT_LINK}?start={user_id}"
        await query.edit_message_text(
            f"🚀 *Получить больше запросов*\n\n"
            f"Способы:\n"
            f"1️⃣ Пригласите друга — +10 запросов\n"
            f"2️⃣ Подписка за 299 ₽/мес (скоро)\n\n"
            f"🔗 Ваша реф-ссылка:\n`{ref_link}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Поделиться", url=f"https://t.me/share/url?url={ref_link}")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back")]
            ])
        )
        return

    if data == "invite":
        info = user_data[user_id]
        ref_link = f"{BOT_LINK}?start={user_id}"
        await query.edit_message_text(
            f"👥 *Пригласите друга*\n\n"
            f"За каждого друга — *+10 запросов*.\n\n"
            f"🔗 Ваша ссылка:\n`{ref_link}`\n\n"
            f"Текущий бонус: *+{info['bonus']}* запросов",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Поделиться", url=f"https://t.me/share/url?url={ref_link}")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back")]
            ])
        )
        return

    if data == "back":
        info = user_data[user_id]
        total = LIMIT_PER_HOUR + info["bonus"]
        left = total - info["requests"]
        await query.edit_message_text(
            f"👋 Главное меню\n\n"
            f"Текущая модель: *{info['model_name']}*\n"
            f"Осталось запросов: *{left}*\n\nВыбери модель или напиши вопрос 👇",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(info["model_name"])
        )
        return

# --- ОБРАБОТКА СООБЩЕНИЙ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    # --- АНТИ-СПАМ: пока бот занят — удаляем сообщение ---
    if user_data[user_id]["is_busy"]:
        try:
            await update.message.delete()
        except Exception:
            pass
        return

    if not await check_subscription(user_id, context):
        await update.message.reply_text(
            f"❌ *Доступ закрыт*\n\nПодпишитесь на канал:\n👉 {CHANNEL_ID}",
            parse_mode="Markdown",
            reply_markup=get_subscribe_keyboard()
        )
        return

    now = time.time()
    data = user_data[user_id]

    # --- УВЕДОМЛЕНИЕ ОБ ОБНОВЛЕНИИ ЛИМИТА ---
    was_exhausted = data["requests"] >= (LIMIT_PER_HOUR + data["bonus"])
    if now - data["reset_time"] > RESET_INTERVAL:
        data["requests"] = 0
        data["reset_time"] = now
        if was_exhausted:
            await update.message.reply_text(
                "✅ *Лимит обновился!*\n\n"
                f"У вас снова {LIMIT_PER_HOUR} запросов.\n"
                "Можете задавать вопросы!",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(data["model_name"])
            )

    total_limit = LIMIT_PER_HOUR + data["bonus"]
    if data["requests"] >= total_limit:
        await update.message.reply_text(
            f"⚠️ *Лимит исчерпан*\n\n"
            f"Вы использовали все {total_limit} запросов в час.\n\n"
            f"Лимит обновится через {int((data['reset_time'] + RESET_INTERVAL - now) / 60)} мин.\n\n"
            f"Или получите больше прямо сейчас 👇",
            parse_mode="Markdown",
            reply_markup=get_limit_keyboard()
        )
        return

    # --- БЛОКИРУЕМ ЮЗЕРА НА ВРЕМЯ ОТВЕТА ---
    data["is_busy"] = True
    try:
        await update.message.chat.send_action(action="typing")
        response = client.chat.completions.create(
            model=data["model"],
            messages=[{"role": "user", "content": user_text}]
        )
        data["requests"] += 1
        left_new = total_limit - data["requests"]
        answer = response.choices[0].message.content
        await update.message.reply_text(
            f"{answer}\n\n"
            f"_Модель: {data['model_name']} · Осталось: {left_new} запросов_",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await update.message.reply_text("⚠️ Ошибка. Попробуйте позже.")
    finally:
        data["is_busy"] = False

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
