import os
import random
from fastapi import FastAPI, Request
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# =====================
# Переменные окружения
# =====================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://your-app.onrender.com

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set")

if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL is not set")

# =====================
# Инициализация
# =====================
app = FastAPI()
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
    buttons = []
    for i, cell in enumerate(field):
        buttons.append(
            InlineKeyboardButton(
                RED if cell else BLUE,
                callback_data=str(i)
            )
        )

    return InlineKeyboardMarkup([
        buttons[0:3],
        buttons[3:6],
        buttons[6:9],
    ])

# =====================
# Хендлеры Telegram
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

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(on_click))

# =====================
# Webhook endpoints
# =====================
@app.on_event("startup")
async def on_startup():
    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(
        url=f"{WEBHOOK_URL}/webhook"
    )
    print("Webhook установлен")

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}
