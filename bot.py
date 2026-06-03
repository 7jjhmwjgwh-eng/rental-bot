import logging
import asyncio
import os
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    CallbackQueryHandler, ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
YOUR_CHAT_ID = int(os.getenv("CHAT_ID", "1060355277"))

(NAME, PHONE, AMOUNT, DATE, NOTES, PAY_SELECT, PAY_AMOUNT, PAY_NOTE) = range(8)

tenants = {}
payments = []

def main_keyboard():
    return ReplyKeyboardMarkup([
        ["➕ Добавить арендатора", "💰 Записать платёж"],
        ["📊 Статистика", "📋 Список арендаторов"],
        ["🔔 Напоминания", "❓ Помощь"]
    ], resize_keyboard=True)

def is_menu_button(text):
    buttons = ["➕ Добавить арендатора", "💰 Записать платёж", "📊 Статистика",
               "📋 Список арендаторов", "🔔 Напоминания", "❓ Помощь"]
    return text in buttons

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я твой бот для управления арендой.\n\nВыбери действие 👇",
        reply_markup=main_keyboard()
    )

# ─── ДОБАВИТЬ АРЕНДАТОРА ─────────────────────────────────────────────────────
async def add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("➕ Введи имя арендатора:", reply_markup=main_keyboard())
    return NAME

async def add_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if is_menu_button(update.message.text):
        return await handle_menu(update, ctx)
    ctx.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("📱 Введи номер телефона:")
    return PHONE

async def add_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if is_menu_button(update.message.text):
        return await handle_menu(update, ctx)
    ctx.user_data["phone"] = update.message.text.strip()
    await update.message.reply_text("💵 Введи сумму аренды в месяц (цифры):")
    return AMOUNT

async def add_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if is_menu_button(update.message.text):
        return await handle_menu(update, ctx)
    try:
        ctx.user_data["amount"] = float(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Только цифры! Например: 1500000")
        return AMOUNT
    await update.message.reply_text("📅 Введи день оплаты (1-31):")
    return DATE

async def add_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if is_menu_button(update.message.text):
        return await handle_menu(update, ctx)
    try:
        day = int(update.message.text.strip())
        if not 1 <= day <= 31:
            raise ValueError
        ctx.user_data["pay_day"] = day
    except:
        await update.message.reply_text("❌ Введи число от 1 до 31")
        return DATE
    await update.message.reply_text("📝 Примечание (или напиши: нет):")
    return NOTES

async def add_notes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if is_menu_button(update.message.text):
        return await handle_menu(update, ctx)
    notes = update.message.text.strip()
    if notes.lower() == "нет":
        notes = ""
    d = ctx.user_data
    tenants[d["name"]] = {
        "phone": d.get("phone", ""),
        "amount": d["amount"],
        "pay_day": d["pay_day"],
        "notes": notes,
        "received": 0
    }
    await update.message.reply_text(
        f"✅ Арендатор добавлен!\n\n"
        f"👤 {d['name']}\n"
        f"📱 {d.get('phone', '—')}\n"
        f"💰 {d['amount']:,.0f} сум/мес\n"
        f"📅 День оплаты: {d['pay_day']}-е число",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END

# ─── ЗАПИСАТЬ ПЛАТЁЖ ─────────────────────────────────────────────────────────
async def pay_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not tenants:
        await update.message.reply_text("❌ Нет арендаторов. Сначала добавь.", reply_markup=main_keyboard())
        return ConversationHandler.END
    buttons = [[InlineKeyboardButton(f"{name} — {info['amount']:,.0f} сум", callback_data=f"pay_{name}")] for name, info in tenants.items()]
    await update.message.reply_text("Выбери арендатора:", reply_markup=InlineKeyboardMarkup(buttons))
    return PAY_SELECT

async def pay_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    name = query.data.replace("pay_", "")
    ctx.user_data["pay_name"] = name
    await query.edit_message_text(f"💵 Сколько заплатил {name}? Введи сумму:")
    return PAY_AMOUNT

async def pay_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if is_menu_button(update.message.text):
        return await handle_menu(update, ctx)
    try:
        ctx.user_data["pay_amount"] = float(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Только цифры")
        return PAY_AMOUNT
    await update.message.reply_text("📝 Примечание (или: нет):")
    return PAY_NOTE

async def pay_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if is_menu_button(update.message.text):
        return await handle_menu(update, ctx)
    note = update.message.text.strip()
    if note.lower() == "нет":
        note = ""
    d = ctx.user_data
    name = d["pay_name"]
    amount = d["pay_amount"]
    if name in tenants:
        tenants[name]["received"] = tenants[name].get("received", 0) + amount
    payments.append({"date": datetime.now().strftime("%d.%m.%Y %H:%M"), "name": name, "amount": amount, "note": note})
    rent = tenants.get(name, {}).get("amount", 1)
    percent = round((tenants[name]["received"] / rent) * 100, 1)
    await update.message.reply_text(
        f"✅ Платёж записан!\n\n"
        f"👤 {name}\n"
        f"💰 Получено сейчас: {amount:,.0f} сум\n"
        f"📊 Всего получено: {tenants[name]['received']:,.0f} сум ({percent}% от аренды)",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END

# ─── СТАТИСТИКА ──────────────────────────────────────────────────────────────
async def statistics(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not tenants:
        await update.message.reply_text("📊 Пока нет арендаторов.", reply_markup=main_keyboard())
        return
    text = "📊 Статистика:\n\n"
    total_monthly = total_received = 0
    for name, info in tenants.items():
        rent = info["amount"]
        received = info.get("received", 0)
        percent = round((received / rent) * 100, 1) if rent > 0 else 0
        total_monthly += rent
        total_received += received
        bar = "🟩" * int(percent // 20) + "⬜" * (5 - int(percent // 20))
        text += (f"👤 {name}\n"
                 f"📱 {info.get('phone', '—')}\n"
                 f"💰 {rent:,.0f} сум/мес\n"
                 f"✅ {received:,.0f} сум ({percent}%)\n"
                 f"{bar}\n"
                 f"📅 День: {info['pay_day']}-е число\n\n")
    text += f"💼 Итого в месяц: {total_monthly:,.0f} сум\n💵 Всего получено: {total_received:,.0f} сум"
    await update.message.reply_text(text, reply_markup=main_keyboard())

async def list_tenants(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not tenants:
        await update.message.reply_text("📋 Пусто.", reply_markup=main_keyboard())
        return
    text = "📋 Арендаторы:\n\n"
    for i, (name, info) in enumerate(tenants.items(), 1):
        text += f"{i}. {name}\n📱 {info.get('phone','—')} | 💰 {info['amount']:,.0f} сум | 📅 {info['pay_day']}-е\n\n"
    await update.message.reply_text(text, reply_markup=main_keyboard())

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Помощь:\n\n"
        "➕ Добавить арендатора — имя, телефон, сумма, день оплаты\n"
        "💰 Записать платёж — отметить оплату\n"
        "📊 Статистика — % собрано с каждого\n"
        "📋 Список — все арендаторы\n"
        "🔔 Напоминания — за 3 дня и в день оплаты",
        reply_markup=main_keyboard()
    )

async def reminders_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔔 Напоминания:\n• За 3 дня до оплаты\n• В день оплаты в 9:00", reply_markup=main_keyboard())

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.", reply_markup=main_keyboard())
    return ConversationHandler.END

async def handle_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📊 Статистика":
        await statistics(update, ctx)
    elif text == "📋 Список арендаторов":
        await list_tenants(update, ctx)
    elif text == "❓ Помощь":
        await help_cmd(update, ctx)
    elif text == "🔔 Напоминания":
        await reminders_info(update, ctx)
    elif text == "➕ Добавить арендатора":
        await update.message.reply_text("➕ Введи имя арендатора:", reply_markup=main_keyboard())
        return NAME
    elif text == "💰 Записать платёж":
        await pay_start(update, ctx)
        return PAY_SELECT
    return ConversationHandler.END

async def check_reminders(app):
    today = datetime.now()
    in_3_days = today + timedelta(days=3)
    for name, info in tenants.items():
        try:
            pay_day = info["pay_day"]
            rent = info["amount"]
            received = info.get("received", 0)
            if today.day == pay_day:
                await app.bot.send_message(YOUR_CHAT_ID,
                    f"🔴 СЕГОДНЯ ДЕНЬ ОПЛАТЫ!\n👤 {name}\n📱 {info.get('phone','—')}\n💰 {rent:,.0f} сум\n✅ Получено: {received:,.0f} сум\n⏳ Осталось: {rent-received:,.0f} сум")
            elif in_3_days.day == pay_day:
                await app.bot.send_message(YOUR_CHAT_ID,
                    f"🟡 Через 3 дня оплата!\n👤 {name}\n📱 {info.get('phone','—')}\n📅 {pay_day}.{today.month:02d}.{today.year}\n💰 {rent:,.0f} сум")
        except Exception as e:
            logging.error(f"Ошибка: {e}")

async def post_init(app):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    scheduler.add_job(check_reminders, "cron", hour=9, minute=0, args=[app])
    scheduler.start()
    print("✅ Бот запущен!")

def main():
    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    add_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Добавить арендатора$"), add_start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_phone)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_amount)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_date)],
            NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^(📊 Статистика|📋 Список арендаторов|🔔 Напоминания|❓ Помощь|💰 Записать платёж)$"), cancel)],
    )

    pay_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💰 Записать платёж$"), pay_start)],
        states={
            PAY_SELECT: [CallbackQueryHandler(pay_select, pattern="^pay_")],
            PAY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, pay_amount)],
            PAY_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pay_note)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^(📊 Статистика|📋 Список арендаторов|🔔 Напоминания|❓ Помощь|➕ Добавить арендатора)$"), cancel)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(add_conv)
    app.add_handler(pay_conv)
    app.add_handler(MessageHandler(filters.Regex("^📊 Статистика$"), statistics))
    app.add_handler(MessageHandler(filters.Regex("^📋 Список арендаторов$"), list_tenants))
    app.add_handler(MessageHandler(filters.Regex("^🔔 Напоминания$"), reminders_info))
    app.add_handler(MessageHandler(filters.Regex("^❓ Помощь$"), help_cmd))
    app.run_polling()

if __name__ == "__main__":
    main()
