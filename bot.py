import logging
import os
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Підключення до Google Sheets
import json
import os
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials_json = os.environ["GOOGLE_CREDENTIALS"]
credentials_dict = json.loads(credentials_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)

# Категорії таблиці на окремих аркушах
category_sheets = {
    "Чоловічі": "Men",
    "Жіночі": "Women",
    "На хлопчика": "Boys",
    "На дівчинку": "Girls",
    "Аксесуари": "Accessories"
}

user_states = {}

def load_products(sheet_name):
    try:
        sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1qPKiXWnsSpPmHGLEwdFyuvk-qBUm_0pW-EicKZXHRmc/edit?usp=drivesdk").worksheet(sheet_name)
        data = sheet.get_all_records()
        return [{
            'id': row['ID'],
            'name': row['Назва'],
            'category': row['Категорія'],
            'price': row['Ціна'],
            'description': row['Опис'],
            'photo': row['Фото (URL)']
        } for row in data]
    except Exception as e:
        print(f"Error loading sheet {sheet_name}: {e}")
        return []

main_menu = [["Каталог"], ["Наші контакти"], ["Зв'язатися з нами"]]
catalog_menu = [["Чоловічі", "Жіночі"], ["На хлопчика", "На дівчинку"], ["Аксесуари"], ["⬅️ Назад"]]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_markup = ReplyKeyboardMarkup(main_menu, resize_keyboard=True)
    await update.message.reply_text("Вітаємо! Оберіть пункт меню:", reply_markup=reply_markup)

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
        products = load_products(category_sheets[text])
        if not products:
            await update.message.reply_text("Категорія наразі пуста.")
            return
        for product in products:
            keyboard = [[InlineKeyboardButton("Замовити", callback_data=f"order_{product['id']}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=product['photo'],
                caption=f"{product['name']}\n{product['description']}\nЦіна: {product['price']} грн",
                reply_markup=reply_markup
            )
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
    product_id = query.data.split("_")[1]
    for sheet_name in category_sheets.values():
        products = load_products(sheet_name)
        product = next((item for item in products if str(item['id']) == product_id), None)
        if product:
            user = query.from_user
            message = f"Нове замовлення:\n\nТовар: {product['name']}\nЦіна: {product['price']} грн\nКористувач: {user.full_name} (@{user.username})"
            await context.bot.send_message(chat_id=ADMIN_ID, text=message)
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("Дякуємо за замовлення! Ми зв'яжемося з вами.")
            break

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()
