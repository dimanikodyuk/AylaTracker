#!/usr/bin/env python3
"""
Ayla Tracker - Telegram Bot (оновлена версія)
"""

import logging
import os
import time
import threading
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from dotenv import load_dotenv
import database as db

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_main_keyboard():
    keyboard = [
        ["🍖 Їжа", "💧 Піся", "💩 Кака"],
        ["🚶 Почати прогулянку", "⏰ Закінчити прогулянку"],
        ["😴 Почати сон", "⏰ Закінчити сон"],
        ["🧠 Ментальне", "🏋️ Тренування", "⚖️ Вага"],
        ["📊 Статистика", "📈 Звіт", "ℹ️ Допомога"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_potty_cue_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔄 Крутилась", callback_data="cue_circling")],
        [InlineKeyboardButton("👃 Нюхала підлогу", callback_data="cue_sniffing")],
        [InlineKeyboardButton("😶 Затихла", callback_data="cue_froze")],
        [InlineKeyboardButton("🏃 Побігла до кута", callback_data="cue_running")],
        [InlineKeyboardButton("❌ Без попередження", callback_data="cue_none")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_training_keyboard():
    keyboard = [
        [InlineKeyboardButton("🐕 Сідати", callback_data="training_sit")],
        [InlineKeyboardButton("😴 Лежати", callback_data="training_down")],
        [InlineKeyboardButton("🚶 Поруч", callback_data="training_heel")],
        [InlineKeyboardButton("🖐️ Дай лапу", callback_data="training_paw")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_mental_keyboard():
    keyboard = [
        [InlineKeyboardButton("🧩 Головоломка", callback_data="mental_puzzle")],
        [InlineKeyboardButton("🔍 Пошук ласощів", callback_data="mental_scent")],
        [InlineKeyboardButton("🎓 Вивчення трюків", callback_data="mental_shaping")],
        [InlineKeyboardButton("👃 Нюхальний килимок", callback_data="mental_sniffing")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context):
    chat_id = update.effective_chat.id
    user = update.effective_user

    db.add_user(chat_id, user.username, user.first_name, user.last_name)

    await update.message.reply_text(
        f"🐾 <b>Вітаю, {user.first_name}!</b> 🐾\n\n"
        f"Я допомагаю відстежувати активність Айли.\n\n"
        f"📌 <b>Основні команди:</b>\n"
        f"• 🍖 Їжа - запис годування\n"
        f"• 🚶 Прогулянка - таймер прогулянки\n"
        f"• 😴 Сон - таймер сну\n"
        f"• 💧 Піся / 💩 Кака - запис туалету\n"
        f"• 🧠 Ментальне - інтелектуальні ігри\n"
        f"• 🏋️ Тренування - навчання команд\n"
        f"• ⚖️ Вага - контроль розвитку\n\n"
        f"Оберіть дію:",
        reply_markup=get_main_keyboard(),
        parse_mode='HTML'
    )


async def handle_message(update: Update, context):
    text = update.message.text
    chat_id = update.effective_chat.id

    if not db.is_user_allowed(chat_id):
        db.add_user(chat_id)
        await update.message.reply_text("🐾 Ви додані в систему!", reply_markup=get_main_keyboard())
        return

    logger.info(f"Повідомлення від {chat_id}: {text}")

    # Їжа
    if text == "🍖 Їжа":
        db.add_event("feed", note="🍖 Годування")
        await update.message.reply_text("✅ Записано годування!")

        # Плануємо нагадування про туалет
        remind_minutes = int(db.get_setting('potty_reminder_minutes', 25))
        threading.Timer(remind_minutes * 60, send_potty_reminder, args=[chat_id]).start()

    # Туалет
    elif text == "💧 Піся":
        db.add_event("toilet", "піся", note="💧 Піся")
        await update.message.reply_text("✅ Записано: Піся!", reply_markup=get_potty_cue_keyboard())

    elif text == "💩 Кака":
        db.add_event("toilet", "кака", note="💩 Кака")
        await update.message.reply_text("✅ Записано: Кака!", reply_markup=get_potty_cue_keyboard())

    # Прогулянка
    elif text == "🚶 Почати прогулянку":
        safe_duration = db.get_safe_walk_duration_minutes()
        db.start_session("walk", expected_duration=safe_duration)
        await update.message.reply_text(
            f"🚶 Прогулянка розпочата!\n"
            f"⏰ Безпечний ліміт: {safe_duration} хв"
        )

    elif text == "⏰ Закінчити прогулянку":
        duration = db.stop_session("walk")
        await update.message.reply_text(f"✅ Прогулянка завершена!\n⏱ Тривалість: {duration // 60} хв")

    # Сон
    elif text == "😴 Почати сон":
        db.start_session("sleep")
        await update.message.reply_text("💤 Сон розпочато!")

    elif text == "⏰ Закінчити сон":
        duration = db.stop_session("sleep")
        await update.message.reply_text(f"✅ Сон завершено!\n⏱ Тривалість: {duration // 60} хв")

    # Вага
    elif text == "⚖️ Вага":
        await update.message.reply_text("⚖️ Надішліть вагу Айли в кг (наприклад: 4.5)")
        context.user_data['awaiting_weight'] = True

    # Ментальне
    elif text == "🧠 Ментальне":
        await update.message.reply_text("🧠 Оберіть тип активності:", reply_markup=get_mental_keyboard())

    # Тренування
    elif text == "🏋️ Тренування":
        await update.message.reply_text("🏋️ Оберіть команду:", reply_markup=get_training_keyboard())

    # Статистика
    elif text == "📊 Статистика":
        stats = db.get_today_stats()
        await update.message.reply_text(
            f"📊 <b>Статистика за сьогодні</b>\n\n"
            f"🍖 Годувань: {stats['feed']}\n"
            f"🚶 Прогулянок: {stats['walk_minutes']} хв\n"
            f"😴 Сну: {stats['sleep_hours']} год\n"
            f"🚽 Туалет: {stats['toilet']}",
            parse_mode='HTML'
        )

    # Звіт
    elif text == "📈 Звіт":
        report = db.get_full_report(7)
        await update.message.reply_text(
            f"📈 <b>Тижневий звіт</b>\n\n"
            f"🍖 Годувань: {report['feed']}\n"
            f"🚶 Прогулянок: {report['walk_minutes']} хв\n"
            f"😴 Сну: {report['sleep_hours']} год\n"
            f"🚽 Туалет: {report['toilet']}\n"
            f"🧠 Ментальне: {report['mental_minutes']} хв\n"
            f"🏋️ Тренувань: {report['training_count']} (усп. {report['training_avg']}/5)",
            parse_mode='HTML'
        )

    # Допомога
    elif text == "ℹ️ Допомога":
        await update.message.reply_text(
            "📖 <b>Довідка</b>\n\n"
            "• 🍖 Їжа - запис годування\n"
            "• 🚶 Прогулянка - таймер з безпечним лімітом\n"
            "• 😴 Сон - таймер сну\n"
            "• 💧 Піся/💩 Кака - запис туалету з маркерами\n"
            "• 🧠 Ментальне - інтелектуальні ігри\n"
            "• 🏋️ Тренування - навчання команд\n"
            "• ⚖️ Вага - контроль розвитку\n\n"
            "📊 <b>Команди:</b>\n"
            "/start - Головне меню\n"
            "/myid - Отримати Chat ID",
            parse_mode='HTML'
        )

    # Обробка ваги
    elif context.user_data.get('awaiting_weight'):
        try:
            weight = float(text.replace(',', '.'))
            db.add_weight(weight)
            daily_food = db.calculate_daily_food_amount(weight)
            await update.message.reply_text(
                f"✅ Вагу {weight} кг збережено!\n"
                f"🍖 Рекомендована порція: {daily_food} г/день"
            )
            context.user_data['awaiting_weight'] = False
        except ValueError:
            await update.message.reply_text("❌ Надішліть число (наприклад: 4.5)")

    else:
        await update.message.reply_text("❓ Невідома команда", reply_markup=get_main_keyboard())


async def button_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Маркери туалету
    if data.startswith("cue_"):
        cue_map = {
            "cue_circling": "Крутилась", "cue_sniffing": "Нюхала підлогу",
            "cue_froze": "Затихла", "cue_running": "Побігла до кута", "cue_none": "Без попередження"
        }
        cue_type = cue_map.get(data, "Невідомо")
        db.add_potty_cue(cue_type, success=0)
        await query.edit_message_text(f"🔍 Записано маркер: {cue_type}")

    # Тренування
    elif data.startswith("training_"):
        cmd_map = {
            "training_sit": "Сідати", "training_down": "Лежати",
            "training_heel": "Поруч", "training_paw": "Дай лапу"
        }
        command = cmd_map.get(data, "Сідати")

        # Запитуємо оцінку
        keyboard = [
            [InlineKeyboardButton("✅ Відмінно (5)", callback_data=f"rate_5_{command}")],
            [InlineKeyboardButton("👍 Добре (4)", callback_data=f"rate_4_{command}")],
            [InlineKeyboardButton("😐 Задовільно (3)", callback_data=f"rate_3_{command}")],
            [InlineKeyboardButton("❌ Погано (1)", callback_data=f"rate_1_{command}")]
        ]
        await query.edit_message_text(f"Оцініть виконання '{command}':", reply_markup=InlineKeyboardMarkup(keyboard))

    # Оцінка тренування
    elif data.startswith("rate_"):
        parts = data.split("_")
        rate = int(parts[1])
        command = "_".join(parts[2:]) if len(parts) > 2 else "Сідати"
        db.add_training(command, 10, rate)
        await query.edit_message_text(f"✅ Записано тренування: {command} (оцінка {rate}/5)")

    # Ментальна активність
    elif data.startswith("mental_"):
        act_map = {
            "mental_puzzle": "Головоломка", "mental_scent": "Пошук ласощів",
            "mental_shaping": "Вивчення трюків", "mental_sniffing": "Нюхальний килимок"
        }
        activity = act_map.get(data, "Активність")
        db.add_mental_activity(activity, 15, 3)
        await query.edit_message_text(f"🧠 Записано ментальну активність: {activity} (15 хв)")


async def myid(update: Update, context):
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"🆔 Ваш Chat ID: `{chat_id}`", parse_mode='Markdown')


def send_potty_reminder(chat_id):
    """Відправка нагадування про туалет"""
    try:
        import requests
        token = db.get_setting('telegram_bot_token')
        if token:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, json={
                'chat_id': chat_id,
                'text': "⏱️ Айла поїла ~20 хв тому. Час вийти на прогулянку, щоб підтримати чисту поведінку вдома!"
            })
    except Exception as e:
        logger.error(f"Помилка нагадування: {e}")


def check_overdue_reminders():
    """Перевірка прострочених нагадувань"""
    reminders = db.get_due_reminders()
    token = db.get_setting('telegram_bot_token')
    if not token:
        return

    for r in reminders:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, json={
                'chat_id': db.get_setting('telegram_chat_id'),
                'text': f"💊 <b>Нагадування!</b>\n\n{r['title']}\n{r.get('description', '')}\n\n⏰ Термін виконання: {r['next_due_str']}",
                'parse_mode': 'HTML'
            })
        except Exception as e:
            logger.error(f"Помилка нагадування: {e}")


def run_bot():
    token = os.getenv('BOT_TOKEN')
    if not token:
        logger.error("BOT_TOKEN не знайдено!")
        return

    db.init_db()

    # Запускаємо перевірку нагадувань в окремому потоці
    def reminder_loop():
        while True:
            time.sleep(3600)  # Перевіряємо кожну годину
            check_overdue_reminders()

    reminder_thread = threading.Thread(target=reminder_loop, daemon=True)
    reminder_thread.start()

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🚀 Бот запущено!")
    app.run_polling()


if __name__ == '__main__':
    run_bot()