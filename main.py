import os
import random
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from dotenv import load_dotenv

# =====================
# Загрузка окружения !!!!
# =====================
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://localhost:8000")
PORT = int(os.getenv("PORT", 8000))

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set")

print(f"Token: {TOKEN[:10]}...")
print(f"Webhook URL: {WEBHOOK_URL}")
print(f"Port: {PORT}")

# =====================
# Telegram app
# =====================
telegram_app = Application.builder().token(TOKEN).build()

BLUE = "🔵"
RED = "🔴"
games = {}

# =====================
# Логика игры
# =====================
def new_game():
    return [random.randint(0, 1) for _ in range(9)]


def toggle(field, index):
    def flip(i):
        field[i] ^= 1

    flip(index)
    row, col = divmod(index, 3)

    if row > 0:
        flip(index - 3)
    if row < 2:
        flip(index + 3)
    if col > 0:
        flip(index - 1)
    if col < 2:
        flip(index + 1)


def is_solved(field):
    return all(cell == field[0] for cell in field)


def keyboard(field):
    buttons = [
        InlineKeyboardButton(
            RED if cell else BLUE,
            callback_data=str(i)
        )
        for i, cell in enumerate(field)
    ]

    return InlineKeyboardMarkup([
        buttons[0:3],
        buttons[3:6],
        buttons[6:9],
    ])

# =====================
# Хендлеры
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    games[user_id] = new_game()

    await update.message.reply_text(
        "🧠 Lights Out 3×3\n\n"
        "Нажимай на клетки.\n"
        "Сделай поле одного цвета!",
        reply_markup=keyboard(games[user_id]),
    )


async def on_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if user_id not in games:
        games[user_id] = new_game()

    index = int(query.data)
    field = games[user_id]

    toggle(field, index)

    if is_solved(field):
        await query.edit_message_text("🎉 Победа!\nПоле одного цвета!")
        del games[user_id]
    else:
        await query.edit_message_reply_markup(
            reply_markup=keyboard(field)
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Используйте /start для начала новой игры.\n"
        "Цель: сделать все клетки одного цвета."
    )

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(CallbackQueryHandler(on_click))

# =====================
# Lifespan
# =====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    await telegram_app.initialize()
    await telegram_app.start()

    if WEBHOOK_URL and "localhost" not in WEBHOOK_URL:
        await telegram_app.bot.set_webhook(
            url=f"{WEBHOOK_URL}/webhook"
        )
        print(f"✅ Webhook установлен: {WEBHOOK_URL}/webhook")
    else:
        print("⚠️  Webhook не установлен (локальный режим)")

    yield

    # SHUTDOWN
    await telegram_app.bot.delete_webhook()
    await telegram_app.stop()
    await telegram_app.shutdown()
    print("🛑 Bot stopped")

# =====================
# FastAPI app
# =====================
app = FastAPI(lifespan=lifespan)

# =====================
# Webhook endpoint
# =====================
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}


@app.get("/")
async def root():
    return {"status": "Bot is running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
