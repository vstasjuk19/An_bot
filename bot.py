import logging 
import os
import json 
import gspread 
import base64
import asyncio
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup 
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from datetime import datetime


#--- Змінні середовища ---

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

#--- Підключення до Google Sheets ---

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

b64_credentials = os.getenv("GOOGLE_CREDENTIALS_B64") 
if not b64_credentials: 
    raise ValueError("GOOGLE_CREDENTIALS_B64 не встановлено!")

credentials_json = base64.b64decode(b64_credentials).decode("utf-8") 
credentials_dict = json.loads(credentials_json)

creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope) 
client = gspread.authorize(creds)

category_sheets = {
    "Чоловічі": "Чоловічі",
    "Жіночі": "Жіночі", 
    "На хлопчика": "На хлопчика",
    "На дівчинку": "На дівчинку", 
    "Аксесуари": "Аксесуари"
}
users_sheet_name = "Користувачі"

sizes_by_category = {
    "Чоловічі": ["S", "M", "L", "XL", "XXL", "XXXL","XXXXL"], 
    "Жіночі": ["XS", "S", "M", "L", "XL", "XXL", "XXXL", "XXXXL"],
    "На хлопчика": ["86", "92", "98", "104", "110", "116", "128", "134", "140", "146", "152","158", "164", "170", "176"],
    "На дівчинку": ["86", "92", "98", "104", "110", "116", "128", "134", "140", "146", "152", "158"]
}

user_states = {}

main_menu = [["Каталог"], ["Наші контакти"], ["Зв'язатися з нами"]] 
catalog_menu = [["Чоловічі", "Жіночі"], ["На хлопчика", "На дівчинку"], ["Аксесуари"], ["⬅️ Назад"]]


def load_products(sheet_name):
    try:
        sheet = client.open_by_url(
            "https://docs.google.com/spreadsheets/d/1qPKiXWnsSpPmHGLEwdFyuvk-qBUm_0pW-EicKZXHRmc/edit?usp=drivesdk"
        ).worksheet(sheet_name)
        rows = sheet.get_all_values()
        if len(rows) < 2:
            return []

        headers = [h.strip().replace('\xa0', ' ') for h in rows[0]]
        products = []

        for row in rows[1:]:
            if len(row) < len(headers):
                continue
            data = dict(zip(headers, row))
            products.append({
                'id': data.get('ID', ''),
                'name': data.get('Назва', ''),
                'category': data.get('Категорія', ''),
                'price': data.get('Ціна', ''),
                'description': data.get('Опис', ''),
                'photo': data.get('Фото (URL)', ''),
                'sizes_available': data.get('Наявні розміри', '')
            })

        return products

def save_new_user(user):
    try:
        sheet = client.open_by_url(
            "https://docs.google.com/spreadsheets/d/1qPKiXWnsSpPmHGLEwdFyuvk-qBUm_0pW-EicKZXHRmc/edit?usp=drivesdk"
        ).worksheet("Користувачі")

        users = sheet.get_all_records()
        user_ids = [str(u.get("user_id")) for u in users]

        if str(user.id) not in user_ids:
            sheet.append_row([
                str(user.id),
                user.full_name,
                f"@{user.username}" if user.username else "",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ])
    except Exception as e:
        print(f"Помилка при збереженні користувача: {e}")

        

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_new_user(user)

    reply_markup = ReplyKeyboardMarkup(main_menu, resize_keyboard=True)
    await update.message.reply_text("Вітаємо! Оберіть пункт меню:", reply_markup=reply_markup)


async def send_products(update_or_query, context):
    products = context.user_data.get("products", [])
    pos = context.user_data.get("position", 0) 
    next_pos = pos + 10
    current_batch = products[pos:next_pos]

    if hasattr(update_or_query, "message"):
        chat_id = update_or_query.message.chat_id
    else:
        chat_id = update_or_query.effective_chat.id

    for product in current_batch:
        sizes = product.get("sizes_available", "").strip().lower()
        is_accessory = context.user_data.get("category") == "Аксесуари"
        is_available = is_accessory or (sizes and sizes != "відсутні")

        caption = (
            f"{product['name']}\n{product['description']}\n"
            f"Ціна: {product['price']} грн"
        )

        if not is_available:
            caption += "\nТовар тимчасово відсутній"
            reply_markup = None
        else:
            if not is_accessory:
                caption += f"\nДоступні розміри: {product['sizes_available']}"
            keyboard = [[InlineKeyboardButton("Замовити", callback_data=f"order_{product['id']}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_photo(
            chat_id=chat_id,
            photo=product['photo'],
            caption=caption,
            reply_markup=reply_markup
        )
        
        await asyncio.sleep(0.5)  # затримка в 0.5 секунди між товарами

    context.user_data["position"] = next_pos

    if next_pos < len(products):
        keyboard = [[InlineKeyboardButton("Ще товари", callback_data="more_products")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=chat_id,
            text="Бажаєте переглянути ще?",
            reply_markup=reply_markup
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    text = update.message.text
    user_id = update.effective_user.id

    if text == "Каталог":
        reply_markup = ReplyKeyboardMarkup(catalog_menu, resize_keyboard=True)
        await update.message.reply_text("Оберіть категорію з каталогу:", reply_markup=reply_markup)

    elif text == "Наші контакти":
        await update.message.reply_text("Телефон: +38066 705 3468\nEmail: vishivanochki@ukr.net")

    elif text == "Зв'язатися з нами":
        user_states[user_id] = "awaiting_message"
        await update.message.reply_text("Будь ласка, напишіть ваше повідомлення:")

    elif text == "⬅️ Назад":
        reply_markup = ReplyKeyboardMarkup(main_menu, resize_keyboard=True)
        await update.message.reply_text("Повертаємось до головного меню:", reply_markup=reply_markup)

    elif text in category_sheets:
        sheet_name = category_sheets[text]
        products = load_products(sheet_name)

        if not products:
            await update.message.reply_text("Категорія наразі пуста.")
            return

        context.user_data["products"] = products
        context.user_data["position"] = 0
        context.user_data["category"] = text

        await send_products(update, context)

    elif user_states.get(user_id) == "awaiting_message":
        user_states.pop(user_id, None)
        user = update.effective_user
        message = f"Повідомлення від користувача:\n\n{update.message.text}\n\nІм'я: {user.full_name} (@{user.username})"
        await context.bot.send_message(chat_id=ADMIN_ID, text=message)
        await update.message.reply_text("Дякуємо! Ми скоро з вами зв'яжемось.")

    else:
        await update.message.reply_text("Будь ласка, оберіть пункт меню.")

    

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    query = update.callback_query 
    await query.answer()
    data = query.data

    if data == "more_products":
        await send_products(query, context)
        return

    elif data.startswith("order_"):
        product_id = data.split("_")[1]
        products = context.user_data.get("products", [])
        product = next((p for p in products if str(p["id"]) == product_id), None)

        if not product:
            await query.message.reply_text("Помилка: товар не знайдено.")
            return

        sizes_raw = product.get("sizes_available", "")
        if sizes_raw.strip().lower() == "відсутні":
            await query.message.reply_text("Цей товар тимчасово відсутній.")
            return

        context.user_data["selected_product"] = product
        sizes = [s.strip() for s in sizes_raw.split(",") if s.strip()]

        if sizes:
            buttons = [[InlineKeyboardButton(size, callback_data=f"size_{size}")] for size in sizes]
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.message.reply_text("Оберіть розмір:", reply_markup=reply_markup)
        else:
            await send_order(update, context, size=None)

    elif data.startswith("size_"):
        size = data.split("_")[1]
        await send_order(update, context, size)

async def send_order(update: Update, context: ContextTypes.DEFAULT_TYPE, size=None):
    user = update.callback_query.from_user
    product = context.user_data.get("selected_product")

    if not product:
        await update.callback_query.message.reply_text("Помилка: товар не знайдено.")
        return

    message = f"Нове замовлення:\n\nТовар: {product['name']}\nЦіна: {product['price']} грн"
    if size:
        message += f"\nРозмір: {size}"
    message += f"\nКористувач: {user.full_name} (@{user.username})"

    await context.bot.send_message(chat_id=ADMIN_ID, text=message)
    await update.callback_query.message.reply_text("Дякуємо за замовлення! Ми зв'яжемося з вами.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build() 
    app.add_handler(CommandHandler("start", start)) 
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button)) 
    app.run_polling()

