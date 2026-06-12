#!/usr/bin/env python3
"""
Ayla Tracker - Telegram Bot (Python 3.13 сумісна версія)
"""

import logging
import os
import time
import threading
import asyncio
from datetime import datetime, time as dt_time, timedelta
from dotenv import load_dotenv
import database as db
import requests

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Простий HTTP API замість python-telegram-bot
TELEGRAM_API_URL = "https://api.telegram.org/bot"

# Google Calendar інтеграція
try:
    from google_calendar import calendar as gc_calendar, setup_google_calendar as gc_setup

    GOOGLE_CALENDAR_AVAILABLE = True
except ImportError:
    GOOGLE_CALENDAR_AVAILABLE = False
    logger.warning("Google Calendar не доступний. Встановіть google-api-python-client")


class SimpleTelegramBot:
    def __init__(self, token):
        self.token = token
        self.base_url = f"{TELEGRAM_API_URL}{token}/"
        self.offset = 0
        self.running = True
        self.user_data = {}

    def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
        """Відправка повідомлення"""
        url = self.base_url + "sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            response = requests.post(url, json=payload, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Send message error: {e}")
            return None

    def get_updates(self):
        """Отримання оновлень"""
        url = self.base_url + "getUpdates"
        payload = {
            "offset": self.offset,
            "timeout": 30
        }
        try:
            response = requests.get(url, params=payload, timeout=35)
            data = response.json()
            if data.get("ok"):
                return data.get("result", [])
        except Exception as e:
            logger.error(f"Get updates error: {e}")
        return []

    def answer_callback(self, callback_id, text=None):
        """Відповідь на callback"""
        url = self.base_url + "answerCallbackQuery"
        payload = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Answer callback error: {e}")


def get_main_keyboard():
    return {
        "keyboard": [
            ["🍖 Їжа", "💧 Піся", "💩 Кака"],
            ["🚶 Почати прогулянку", "⏰ Закінчити прогулянку"],
            ["😴 Почати сон", "⏰ Закінчити сон"],
            ["🧠 Ментальне", "🏋️ Тренування", "⚖️ Вага"],
            ["📊 Статистика", "📈 Звіт", "📅 Google Calendar"],
            ["ℹ️ Допомога"]
        ],
        "resize_keyboard": True
    }


def get_potty_cue_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🔄 Крутилась", "callback_data": "cue_circling"}],
            [{"text": "👃 Нюхала підлогу", "callback_data": "cue_sniffing"}],
            [{"text": "😶 Затихла", "callback_data": "cue_froze"}],
            [{"text": "🏃 Побігла до кута", "callback_data": "cue_running"}],
            [{"text": "❌ Без попередження", "callback_data": "cue_none"}]
        ]
    }


def get_training_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🐕 Сідати", "callback_data": "training_sit"}],
            [{"text": "😴 Лежати", "callback_data": "training_down"}],
            [{"text": "🚶 Поруч", "callback_data": "training_heel"}],
            [{"text": "🖐️ Дай лапу", "callback_data": "training_paw"}]
        ]
    }


def get_mental_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🧩 Головоломка", "callback_data": "mental_puzzle"}],
            [{"text": "🔍 Пошук ласощів", "callback_data": "mental_scent"}],
            [{"text": "🎓 Вивчення трюків", "callback_data": "mental_shaping"}],
            [{"text": "👃 Нюхальний килимок", "callback_data": "mental_sniffing"}]
        ]
    }


def get_rate_keyboard(command):
    return {
        "inline_keyboard": [
            [{"text": "✅ Відмінно (5)", "callback_data": f"rate_5_{command}"}],
            [{"text": "👍 Добре (4)", "callback_data": f"rate_4_{command}"}],
            [{"text": "😐 Задовільно (3)", "callback_data": f"rate_3_{command}"}],
            [{"text": "❌ Погано (1)", "callback_data": f"rate_1_{command}"}]
        ]
    }


def get_calendar_keyboard():
    """Клавіатура для Google Calendar"""
    return {
        "inline_keyboard": [
            [{"text": "🔄 Синхронізувати нагадування", "callback_data": "calendar_sync"}],
            [{"text": "🍖 Додати годування", "callback_data": "calendar_add_feed"}],
            [{"text": "🚶 Додати прогулянку", "callback_data": "calendar_add_walk"}],
            [{"text": "💊 Додати ліки", "callback_data": "calendar_add_med"}],
            [{"text": "📋 Найближчі події", "callback_data": "calendar_upcoming"}]
        ]
    }


def handle_message(bot, chat_id, text, user_data):
    """Обробка текстових повідомлень"""

    # Їжа
    if text == "🍖 Їжа":
        db.add_event("feed", note="🍖 Годування")
        bot.send_message(chat_id, "✅ Записано годування!")

    # Туалет
    elif text == "💧 Піся":
        db.add_event("toilet", "піся", note="💧 Піся")
        bot.send_message(chat_id, "✅ Записано: Піся!", reply_markup=get_potty_cue_keyboard())

    elif text == "💩 Кака":
        db.add_event("toilet", "кака", note="💩 Кака")
        bot.send_message(chat_id, "✅ Записано: Кака!", reply_markup=get_potty_cue_keyboard())

    # Прогулянка
    elif text == "🚶 Почати прогулянку":
        safe_duration = db.get_safe_walk_duration_minutes()
        db.start_session("walk", expected_duration=safe_duration)
        bot.send_message(chat_id, f"🚶 Прогулянка розпочата!\n⏰ Безпечний ліміт: {safe_duration} хв")

    elif text == "⏰ Закінчити прогулянку":
        duration = db.stop_session("walk")
        bot.send_message(chat_id, f"✅ Прогулянка завершена!\n⏱ Тривалість: {duration // 60} хв")

    # Сон
    elif text == "😴 Почати сон":
        db.start_session("sleep")
        bot.send_message(chat_id, "💤 Сон розпочато!")

    elif text == "⏰ Закінчити сон":
        duration = db.stop_session("sleep")
        bot.send_message(chat_id, f"✅ Сон завершено!\n⏱ Тривалість: {duration // 60} хв")

    # Вага
    elif text == "⚖️ Вага":
        bot.send_message(chat_id, "⚖️ Надішліть вагу Айли в кг (наприклад: 4.5)")
        user_data['awaiting_weight'] = True

    # Ментальне
    elif text == "🧠 Ментальне":
        bot.send_message(chat_id, "🧠 Оберіть тип активності:", reply_markup=get_mental_keyboard())

    # Тренування
    elif text == "🏋️ Тренування":
        bot.send_message(chat_id, "🏋️ Оберіть команду:", reply_markup=get_training_keyboard())

    # Google Calendar
    elif text == "📅 Google Calendar":
        if GOOGLE_CALENDAR_AVAILABLE and gc_calendar and gc_calendar.service:
            bot.send_message(
                chat_id,
                "📅 <b>Google Calendar</b>\n\n"
                "Оберіть дію:",
                reply_markup=get_calendar_keyboard(),
                parse_mode="HTML"
            )
        else:
            from google_calendar import setup_google_calendar
            bot.send_message(
                chat_id,
                setup_google_calendar(),
                parse_mode="HTML"
            )

    # Статистика
    elif text == "📊 Статистика":
        stats = db.get_today_stats()
        bot.send_message(chat_id,
                         f"📊 <b>Статистика за сьогодні</b>\n\n"
                         f"🍖 Годувань: {stats['feed']}\n"
                         f"🚶 Прогулянок: {stats['walk_minutes']} хв\n"
                         f"😴 Сну: {stats['sleep_hours']} год\n"
                         f"🚽 Туалет: {stats['toilet']}",
                         parse_mode="HTML")

    # Звіт
    elif text == "📈 Звіт":
        report = db.get_full_report(7)
        bot.send_message(chat_id,
                         f"📈 <b>Тижневий звіт</b>\n\n"
                         f"🍖 Годувань: {report['feed']}\n"
                         f"🚶 Прогулянок: {report['walk_minutes']} хв\n"
                         f"😴 Сну: {report['sleep_hours']} год\n"
                         f"🚽 Туалет: {report['toilet']}\n"
                         f"🧠 Ментальне: {report['mental_minutes']} хв\n"
                         f"🏋️ Тренувань: {report['training_count']} (усп. {report['training_avg']}/5)",
                         parse_mode="HTML")

    # Допомога
    elif text == "ℹ️ Допомога":
        bot.send_message(chat_id,
                         "📖 <b>Довідка</b>\n\n"
                         "• 🍖 Їжа - запис годування\n"
                         "• 🚶 Прогулянка - таймер\n"
                         "• 😴 Сон - таймер сну\n"
                         "• 💧 Піся/💩 Кака - запис туалету\n"
                         "• 🧠 Ментальне - інтелектуальні ігри\n"
                         "• 🏋️ Тренування - навчання команд\n"
                         "• ⚖️ Вага - контроль розвитку\n"
                         "• 📅 Google Calendar - синхронізація з календарем\n\n"
                         "📊 <b>Команди:</b>\n"
                         "/start - Головне меню\n"
                         "/myid - Отримати Chat ID\n"
                         "/stats - Детальна статистика\n"
                         "/reminders - Мої нагадування",
                         parse_mode="HTML")

    # Обробка ваги
    elif user_data.get('awaiting_weight'):
        try:
            weight = float(text.replace(',', '.'))
            db.add_weight(weight)
            daily_food = db.calculate_daily_food_amount(weight)
            bot.send_message(chat_id, f"✅ Вагу {weight} кг збережено!\n🍖 Рекомендована порція: {daily_food} г/день")
            user_data['awaiting_weight'] = False
        except ValueError:
            bot.send_message(chat_id, "❌ Надішліть число (наприклад: 4.5)")

    # Обробка часу для годування в календарі
    elif user_data.get('awaiting_feed_time'):
        try:
            hour, minute = map(int, text.split(':'))
            feed_time = dt_time(hour, minute)
            user_data['feed_time'] = feed_time
            bot.send_message(chat_id, "🍖 Введіть номер годування (1-4):")
            user_data['awaiting_feed_time'] = False
            user_data['awaiting_feed_number'] = True
        except:
            bot.send_message(chat_id, "❌ Неправильний формат. Використовуйте ГГ:ХХ")

    # Обробка номера годування
    elif user_data.get('awaiting_feed_number'):
        try:
            meal_num = int(text)
            if 1 <= meal_num <= 4:
                feed_time = user_data.get('feed_time')
                if GOOGLE_CALENDAR_AVAILABLE and gc_calendar and gc_calendar.service:
                    link = gc_calendar.add_feeding_reminder(feed_time, meal_num)
                    if link:
                        bot.send_message(chat_id, f"✅ Годування додано в календар!\n{link}")
                    else:
                        bot.send_message(chat_id, "❌ Помилка додавання в календар")
                else:
                    bot.send_message(chat_id, "❌ Google Calendar не налаштовано")
            else:
                bot.send_message(chat_id, "❌ Введіть число від 1 до 4")
            user_data['awaiting_feed_number'] = False
            user_data['feed_time'] = None
        except:
            bot.send_message(chat_id, "❌ Введіть число")

    # Обробка часу для прогулянки
    elif user_data.get('awaiting_walk_time'):
        try:
            hour, minute = map(int, text.split(':'))
            walk_time = dt_time(hour, minute)
            if GOOGLE_CALENDAR_AVAILABLE and gc_calendar and gc_calendar.service:
                link = gc_calendar.add_walk_reminder(walk_time)
                if link:
                    bot.send_message(chat_id, f"✅ Прогулянку додано в календар!\n{link}")
                else:
                    bot.send_message(chat_id, "❌ Помилка додавання в календар")
            else:
                bot.send_message(chat_id, "❌ Google Calendar не налаштовано")
            user_data['awaiting_walk_time'] = False
        except:
            bot.send_message(chat_id, "❌ Неправильний формат. Використовуйте ГГ:ХХ")
            user_data['awaiting_walk_time'] = False

    # Обробка назви ліків
    elif user_data.get('awaiting_med_name'):
        user_data['med_name'] = text
        bot.send_message(chat_id, "💊 Введіть дозування (наприклад: 1 таблетка)")
        user_data['awaiting_med_name'] = False
        user_data['awaiting_med_dosage'] = True

    # Обробка дозування ліків
    elif user_data.get('awaiting_med_dosage'):
        user_data['med_dosage'] = text
        bot.send_message(chat_id, "⏰ Введіть час прийому (ГГ:ХХ)")
        user_data['awaiting_med_dosage'] = False
        user_data['awaiting_med_time'] = True

    # Обробка часу прийому ліків
    elif user_data.get('awaiting_med_time'):
        try:
            hour, minute = map(int, text.split(':'))
            med_time = dt_time(hour, minute)
            med_name = user_data.get('med_name')
            med_dosage = user_data.get('med_dosage')

            if GOOGLE_CALENDAR_AVAILABLE and gc_calendar and gc_calendar.service:
                link = gc_calendar.add_medication_reminder(med_name, med_time, med_dosage)
                if link:
                    bot.send_message(chat_id, f"✅ Нагадування про ліки додано в календар!\n{link}")
                else:
                    bot.send_message(chat_id, "❌ Помилка додавання в календар")
            else:
                bot.send_message(chat_id, "❌ Google Calendar не налаштовано")

            user_data['awaiting_med_time'] = False
            user_data['med_name'] = None
            user_data['med_dosage'] = None
        except:
            bot.send_message(chat_id, "❌ Неправильний формат. Використовуйте ГГ:ХХ")
            user_data['awaiting_med_time'] = False

    else:
        bot.send_message(chat_id, "❓ Невідома команда", reply_markup=get_main_keyboard())


def handle_callback(bot, chat_id, callback_id, data, user_data):
    """Обробка callback запитів"""

    # Маркери туалету
    if data.startswith("cue_"):
        cue_map = {
            "cue_circling": "Крутилась", "cue_sniffing": "Нюхала підлогу",
            "cue_froze": "Затихла", "cue_running": "Побігла до кута", "cue_none": "Без попередження"
        }
        cue_type = cue_map.get(data, "Невідомо")
        db.add_potty_cue(cue_type, success=0)
        bot.answer_callback(callback_id, f"🔍 Записано маркер: {cue_type}")
        bot.send_message(chat_id, f"🔍 Записано маркер: {cue_type}")

    # Вибір команди для тренування
    elif data.startswith("training_"):
        cmd_map = {
            "training_sit": "Сідати", "training_down": "Лежати",
            "training_heel": "Поруч", "training_paw": "Дай лапу"
        }
        command = cmd_map.get(data, "Сідати")
        bot.answer_callback(callback_id)
        bot.send_message(chat_id, f"Оцініть виконання '{command}':", reply_markup=get_rate_keyboard(command))

    # Оцінка тренування
    elif data.startswith("rate_"):
        parts = data.split("_")
        rate = int(parts[1])
        command = "_".join(parts[2:]) if len(parts) > 2 else "Сідати"
        db.add_training(command, 10, rate)
        bot.answer_callback(callback_id, f"✅ Записано!")
        bot.send_message(chat_id, f"✅ Записано тренування: {command} (оцінка {rate}/5)")

    # Ментальна активність
    elif data.startswith("mental_"):
        act_map = {
            "mental_puzzle": "Головоломка", "mental_scent": "Пошук ласощів",
            "mental_shaping": "Вивчення трюків", "mental_sniffing": "Нюхальний килимок"
        }
        activity = act_map.get(data, "Активність")
        db.add_mental_activity(activity, 15, 3)
        bot.answer_callback(callback_id, f"🧠 Записано!")
        bot.send_message(chat_id, f"🧠 Записано ментальну активність: {activity} (15 хв)")

    # Google Calendar дії
    elif data == "calendar_sync":
        bot.answer_callback(callback_id, "🔄 Синхронізація...")
        if GOOGLE_CALENDAR_AVAILABLE and gc_calendar and gc_calendar.service:
            gc_calendar.sync_reminders()
            bot.send_message(chat_id, "✅ Всі нагадування синхронізовано з Google Calendar!")
        else:
            bot.send_message(chat_id, "❌ Google Calendar не налаштовано. Використайте /setup_calendar")

    elif data == "calendar_add_feed":
        bot.answer_callback(callback_id)
        bot.send_message(chat_id, "⏰ Введіть час годування (ГГ:ХХ):")
        user_data['awaiting_feed_time'] = True

    elif data == "calendar_add_walk":
        bot.answer_callback(callback_id)
        bot.send_message(chat_id, "⏰ Введіть час прогулянки (ГГ:ХХ):")
        user_data['awaiting_walk_time'] = True

    elif data == "calendar_add_med":
        bot.answer_callback(callback_id)
        bot.send_message(chat_id, "💊 Введіть назву ліків:")
        user_data['awaiting_med_name'] = True

    elif data == "calendar_upcoming":
        bot.answer_callback(callback_id, "📋 Отримання подій...")
        if GOOGLE_CALENDAR_AVAILABLE and gc_calendar and gc_calendar.service:
            events = gc_calendar.get_upcoming_events()
            if not events:
                bot.send_message(chat_id, "📭 Немає найближчих подій")
            else:
                message = "📅 <b>Найближчі події:</b>\n\n"
                for event in events[:5]:
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    # Форматуємо дату
                    if 'T' in start:
                        start_date = start.split('T')[0]
                        start_time = start.split('T')[1][:5]
                        start_str = f"{start_date} {start_time}"
                    else:
                        start_str = start
                    message += f"• <b>{event['summary']}</b>\n  ⏰ {start_str}\n\n"
                bot.send_message(chat_id, message, parse_mode="HTML")
        else:
            bot.send_message(chat_id, "❌ Google Calendar не налаштовано")


def run_bot():
    token = os.getenv('BOT_TOKEN')
    if not token:
        logger.error("BOT_TOKEN не знайдено!")
        return

    db.init_db()
    bot = SimpleTelegramBot(token)

    # Ініціалізація Google Calendar
    if GOOGLE_CALENDAR_AVAILABLE:
        try:
            from google_calendar import calendar as gc_calendar
            if gc_calendar and gc_calendar.service:
                logger.info("✅ Google Calendar підключено")
        except Exception as e:
            logger.warning(f"Google Calendar не доступний: {e}")

    # Відправка привітання адміну
    admin_chat_id = db.get_setting('telegram_chat_id')
    if admin_chat_id:
        bot.send_message(admin_chat_id, "🐾 Бот Ayla Tracker запущено!", reply_markup=get_main_keyboard())

    logger.info("🚀 Бот запущено!")

    user_data = {}

    while bot.running:
        try:
            updates = bot.get_updates()

            for update in updates:
                if 'message' in update:
                    message = update['message']
                    chat_id = message['chat']['id']
                    text = message.get('text', '')

                    # Обробка команди /start
                    if text == '/start':
                        user = message.get('from', {})
                        db.add_user(chat_id, user.get('username'), user.get('first_name'), user.get('last_name'))
                        bot.send_message(chat_id,
                                         f"🐾 <b>Вітаю, {user.get('first_name', 'гість')}!</b>\n\n"
                                         f"Я допомагаю відстежувати активність Айли.\n\n"
                                         f"Оберіть дію:",
                                         reply_markup=get_main_keyboard(),
                                         parse_mode='HTML')
                    elif text == '/myid':
                        bot.send_message(chat_id, f"🆔 Ваш Chat ID: `{chat_id}`", parse_mode='Markdown')
                    elif text == '/stats':
                        report = db.get_full_report(30)
                        bot.send_message(chat_id,
                                         f"📊 <b>Статистика за 30 днів</b>\n\n"
                                         f"🍖 Годувань: {report['feed']}\n"
                                         f"🚶 Прогулянок: {report['walk_minutes']} хв\n"
                                         f"😴 Сну: {report['sleep_hours']} год\n"
                                         f"🚽 Туалет: {report['toilet']}\n"
                                         f"🧠 Ментальне: {report['mental_minutes']} хв",
                                         parse_mode="HTML")
                    elif text == '/reminders':
                        reminders = db.get_medical_reminders()
                        if not reminders:
                            bot.send_message(chat_id, "📭 Немає активних нагадувань")
                        else:
                            message = "💊 <b>Ваші нагадування:</b>\n\n"
                            for r in reminders[:10]:
                                message += f"• {r['title']}\n  ⏰ {r['next_due_str']}\n\n"
                            bot.send_message(chat_id, message, parse_mode="HTML")
                    elif not text.startswith('/'):
                        if chat_id not in user_data:
                            user_data[chat_id] = {}
                        handle_message(bot, chat_id, text, user_data[chat_id])

                elif 'callback_query' in update:
                    callback = update['callback_query']
                    chat_id = callback['message']['chat']['id']
                    callback_id = callback['id']
                    data = callback.get('data', '')

                    if chat_id not in user_data:
                        user_data[chat_id] = {}
                    handle_callback(bot, chat_id, callback_id, data, user_data[chat_id])

                # Оновлюємо offset
                if 'update_id' in update:
                    bot.offset = update['update_id'] + 1

        except Exception as e:
            logger.error(f"Bot loop error: {e}")
            time.sleep(5)

        time.sleep(1)


if __name__ == '__main__':
    run_bot()