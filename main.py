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
# Загрузка переменных окружения
# =====================
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8000))

if not TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOT_TOKEN is not set")

print(f"Token: {TOKEN[:10]}...")
print(f"Webhook URL: {WEBHOOK_URL}")
print(f"Port: {PORT}")

# =====================
# Telegram application
# =====================
telegram_app = Application.builder().token(TOKEN).build()

BLUE = "🔵"
RED = "🔴"
games: dict[int, list[int]] = {}

# =====================
# Логика игры Lights Out
# =====================
def new_game() -> list[int]:
    return [random.randint(0, 1) for _ in range(9)]


def toggle(field: list[int], index: int) -> None:
    def flip(i: int):
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


def is_solved(field: list[int]) -> bool:
    return all(cell == field[0] for cell in field)


def keyboard(field: list[int]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            RED if cell else BLUE,
            callback_data=str(i),
        )
        for i, cell in enumerate(field)
    ]

    return InlineKeyboardMarkup([
        buttons[0:3],
        buttons[3:6],
        buttons[6:9],
    ])

# =====================
# Telegram handlers
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
        games.pop(user_id, None)
    else:
        await query.edit_message_reply_markup(
            reply_markup=keyboard(field)
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n"
        "/start — начать новую игру\n"
        "/help — справка\n\n"
        "Цель: сделать все клетки одного цвета."
    )


telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(CallbackQueryHandler(on_click))

# =====================
# FastAPI lifespan
# =====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    await telegram_app.initialize()
    await telegram_app.start()

    if WEBHOOK_URL:
        await telegram_app.bot.set_webhook(
            url=f"{WEBHOOK_URL}/webhook"
        )
        print(f"✅ Webhook установлен: {WEBHOOK_URL}/webhook")
    else:
        print("⚠️ WEBHOOK_URL не задан — webhook не установлен")

    yield

    # SHUTDOWN
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

# =====================
# Service endpoints
# =====================
@app.get("/")
async def root():
    return {"status": "ok", "service": "Telegram Lights Out Bot"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
