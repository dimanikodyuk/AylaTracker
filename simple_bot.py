#!/usr/bin/env python3
"""
Ayla Tracker - Telegram Bot (оновлена версія з груповими чатами)
"""

import logging
import os
import time
import threading
from datetime import datetime, time as dt_time
from dotenv import load_dotenv
import database as db
import requests

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot"

# Google Calendar інтеграція (опціонально)
try:
    from google_calendar import calendar as gc_calendar

    GOOGLE_CALENDAR_AVAILABLE = True
except ImportError:
    GOOGLE_CALENDAR_AVAILABLE = False
    logger.warning("Google Calendar не доступний")


class SimpleTelegramBot:
    def __init__(self, token):
        self.token = token
        self.base_url = f"{TELEGRAM_API_URL}{token}/"
        self.offset = 0
        self.running = True
        self.user_data = {}

    def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
        url = self.base_url + "sendMessage"
        payload = {"chat_id": chat_id, "text": text}
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

    def send_photo(self, chat_id, photo_url, caption=None):
        url = self.base_url + "sendPhoto"
        payload = {"chat_id": chat_id, "photo": photo_url}
        if caption:
            payload["caption"] = caption
        try:
            response = requests.post(url, json=payload, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Send photo error: {e}")
            return None

    def get_updates(self):
        url = self.base_url + "getUpdates"
        payload = {"offset": self.offset, "timeout": 30}
        try:
            response = requests.get(url, params=payload, timeout=35)
            data = response.json()
            if data.get("ok"):
                return data.get("result", [])
        except Exception as e:
            logger.error(f"Get updates error: {e}")
        return []

    def answer_callback(self, callback_id, text=None):
        url = self.base_url + "answerCallbackQuery"
        payload = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Answer callback error: {e}")


# ========== КЛАВІАТУРИ ==========

def get_main_keyboard():
    return {
        "keyboard": [
            ["🍖 Їжа", "💧 Піся", "💩 Кака"],
            ["🚶 Почати прогулянку", "⏰ Закінчити прогулянку"],
            ["😴 Почати сон", "⏰ Закінчити сон"],
            ["🧠 Ментальне", "🏋️ Тренування", "⚖️ Вага"],
            ["⚠️ Поведінка", "📊 Статистика", "📈 Звіт"],
            ["ℹ️ Допомога"]
        ],
        "resize_keyboard": True
    }


def get_behavior_keyboard():
    behaviors = db.get_behavior_types()
    keyboard = []
    row = []
    for i, b in enumerate(behaviors):
        row.append({"text": f"{b['icon']} {b['name']}", "callback_data": f"behavior_{b['id']}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([{"text": "❌ Скасувати", "callback_data": "cancel"}])
    return {"inline_keyboard": keyboard}


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
    types = db.get_training_types()
    keyboard = []
    row = []
    for i, t in enumerate(types):
        row.append({"text": f"{t['icon']} {t['name']}", "callback_data": f"training_{t['id']}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([{"text": "➕ Додати нову команду", "callback_data": "add_training_type"}])
    return {"inline_keyboard": keyboard}


def get_mental_keyboard():
    types = db.get_mental_types()
    keyboard = []
    row = []
    for i, t in enumerate(types):
        row.append({"text": f"{t['icon']} {t['name']}", "callback_data": f"mental_{t['id']}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([{"text": "➕ Додати нову активність", "callback_data": "add_mental_type"}])
    return {"inline_keyboard": keyboard}


def get_rate_keyboard(command_id, command_name):
    return {
        "inline_keyboard": [
            [{"text": "✅ Відмінно (5)", "callback_data": f"rate_5_{command_id}"}],
            [{"text": "👍 Добре (4)", "callback_data": f"rate_4_{command_id}"}],
            [{"text": "😐 Задовільно (3)", "callback_data": f"rate_3_{command_id}"}],
            [{"text": "❌ Погано (1)", "callback_data": f"rate_1_{command_id}"}]
        ]
    }


def get_calendar_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🔄 Синхронізувати нагадування", "callback_data": "calendar_sync"}],
            [{"text": "🍖 Додати годування", "callback_data": "calendar_add_feed"}],
            [{"text": "🚶 Додати прогулянку", "callback_data": "calendar_add_walk"}],
            [{"text": "💊 Додати ліки", "callback_data": "calendar_add_med"}],
            [{"text": "📋 Найближчі події", "callback_data": "calendar_upcoming"}]
        ]
    }


# ========== ОБРОБКА ПОВІДОМЛЕНЬ ==========

def handle_message(bot, chat_id, text, user_data):
    # Їжа
    if text == "🍖 Їжа":
        db.add_event("feed", note="🍖 Годування")
        bot.send_message(chat_id, "✅ Записано годування!")
        # Нагадування про туалет
        remind_minutes = int(db.get_setting('potty_reminder_minutes', 25))
        threading.Timer(remind_minutes * 60, send_potty_reminder, args=[chat_id]).start()

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

    # Поведінка
    elif text == "⚠️ Поведінка":
        keyboard = get_behavior_keyboard()
        bot.send_message(chat_id, "⚠️ Оберіть тип поведінки:", reply_markup=keyboard)

    # Ментальне
    elif text == "🧠 Ментальне":
        bot.send_message(chat_id, "🧠 Оберіть тип активності:", reply_markup=get_mental_keyboard())

    # Тренування
    elif text == "🏋️ Тренування":
        bot.send_message(chat_id, "🏋️ Оберіть команду:", reply_markup=get_training_keyboard())

    # Google Calendar
    elif text == "📅 Google Calendar":
        if GOOGLE_CALENDAR_AVAILABLE and gc_calendar and gc_calendar.service:
            bot.send_message(chat_id, "📅 <b>Google Calendar</b>\n\nОберіть дію:", reply_markup=get_calendar_keyboard(),
                             parse_mode="HTML")
        else:
            bot.send_message(chat_id, "❌ Google Calendar не налаштовано. Потрібен файл credentials.json")

    # Статистика
    elif text == "📊 Статистика":
        stats = db.get_today_stats()
        bot.send_message(chat_id,
                         f"📊 <b>Статистика за сьогодні</b>\n\n"
                         f"🍖 Годувань: {stats['feed']}\n"
                         f"🚶 Прогулянок: {stats['walk_minutes']} хв\n"
                         f"😴 Сну: {stats['sleep_hours']} год\n"
                         f"🚽 Туалет: {stats['toilet']}\n"
                         f"⚠️ Поведінка: {stats['behavior']}",
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
                         f"⚠️ Поведінка: {report['behavior']}\n"
                         f"🧠 Ментальне: {report['mental_minutes']} хв\n"
                         f"🏋️ Тренувань: {report['training_count']} (усп. {report['training_avg']}/5)",
                         parse_mode="HTML")

    # Допомога
    elif text == "ℹ️ Допомога":
        bot.send_message(chat_id,
                         "📖 <b>Довідка Ayla Tracker</b>\n\n"
                         "🍖 Їжа - запис годування\n"
                         "🚶 Прогулянка - таймер з безпечним лімітом\n"
                         "😴 Сон - таймер сну\n"
                         "💧 Піся/💩 Кака - запис туалету з маркерами\n"
                         "⚠️ Поведінка - запис проблемної поведінки\n"
                         "🧠 Ментальне - інтелектуальні ігри\n"
                         "🏋️ Тренування - навчання команд\n"
                         "⚖️ Вага - контроль розвитку\n"
                         "📅 Google Calendar - синхронізація (опціонально)\n\n"
                         "📊 <b>Команди:</b>\n"
                         "/start - Головне меню\n"
                         "/myid - Отримати Chat ID\n"
                         "/stats - Детальна статистика\n"
                         "/reminders - Мої нагадування\n"
                         "/group - Додати цей чат як груповий",
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

    else:
        bot.send_message(chat_id, "❓ Невідома команда", reply_markup=get_main_keyboard())


def handle_callback(bot, chat_id, callback_id, data, user_data):
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

    # Поведінка
    elif data.startswith("behavior_"):
        behavior_id = int(data.split('_')[1])
        behaviors = {b['id']: b for b in db.get_behavior_types()}
        behavior = behaviors.get(behavior_id)
        if behavior:
            db.add_behavior(behavior['name'], behavior['severity'])
            bot.answer_callback(callback_id, f"⚠️ Записано: {behavior['name']}")
            bot.send_message(chat_id, f"⚠️ Записано поведінку: {behavior['icon']} {behavior['name']}")
        else:
            bot.answer_callback(callback_id, "❌ Помилка")

    # Вибір команди для тренування
    elif data.startswith("training_"):
        training_id = int(data.split('_')[1])
        types = {t['id']: t for t in db.get_training_types()}
        training = types.get(training_id)
        if training:
            user_data['training_command_id'] = training_id
            user_data['training_command_name'] = training['name']
            bot.answer_callback(callback_id)
            bot.send_message(chat_id, f"Оцініть виконання '{training['name']}':",
                             reply_markup=get_rate_keyboard(training_id, training['name']))

    # Додати тип тренування
    elif data == "add_training_type":
        bot.answer_callback(callback_id)
        bot.send_message(chat_id, "📝 Введіть назву нової команди (наприклад: Апорт)")
        user_data['awaiting_new_training'] = True

    # Додати тип ментальної активності
    elif data == "add_mental_type":
        bot.answer_callback(callback_id)
        bot.send_message(chat_id, "📝 Введіть назву нової ментальної активності (наприклад: Лабіринт)")
        user_data['awaiting_new_mental'] = True

    # Оцінка тренування
    elif data.startswith("rate_"):
        parts = data.split('_')
        rate = int(parts[1])
        training_id = int(parts[2]) if len(parts) > 2 else None
        command_name = user_data.get('training_command_name', 'Тренування')
        db.add_training(command_name, 10, rate)
        bot.answer_callback(callback_id, f"✅ Записано!")
        bot.send_message(chat_id, f"✅ Записано тренування: {command_name} (оцінка {rate}/5)")
        user_data['training_command_id'] = None
        user_data['training_command_name'] = None

    # Вибір ментальної активності
    elif data.startswith("mental_"):
        mental_id = int(data.split('_')[1])
        types = {t['id']: t for t in db.get_mental_types()}
        mental = types.get(mental_id)
        if mental:
            bot.answer_callback(callback_id)
            bot.send_message(chat_id, f"🧠 Введіть тривалість активності '{mental['name']}' (хв):")
            user_data['awaiting_mental_duration'] = mental_id

    # Google Calendar дії
    elif data == "calendar_sync":
        bot.answer_callback(callback_id, "🔄 Синхронізація...")
        if GOOGLE_CALENDAR_AVAILABLE and gc_calendar and gc_calendar.service:
            gc_calendar.sync_reminders()
            bot.send_message(chat_id, "✅ Всі нагадування синхронізовано з Google Calendar!")
        else:
            bot.send_message(chat_id, "❌ Google Calendar не налаштовано")

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

    elif data == "cancel":
        bot.answer_callback(callback_id)
        bot.send_message(chat_id, "❌ Дію скасовано", reply_markup=get_main_keyboard())


def send_potty_reminder(chat_id):
    try:
        token = db.get_setting('telegram_bot_token')
        if token:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, json={
                'chat_id': chat_id,
                'text': "⏱️ Айла поїла ~20 хв тому. Час вийти на прогулянку, щоб підтримати чисту поведінку вдома!"
            })
    except Exception as e:
        logger.error(f"Помилка нагадування: {e}")


def check_reminders_loop(bot):
    """Фонова перевірка нагадувань"""
    while True:
        time.sleep(3600)  # Перевіряємо кожну годину
        try:
            due_reminders = db.get_due_medical_reminders()
            for r in due_reminders:
                msg = f"💊 <b>{r['title']}</b>\n\n{r.get('description', '')}\n\n⏰ Час виконання: {r.get('reminder_time', '09:00')}"
                admin_chat = db.get_setting('telegram_chat_id')
                if admin_chat:
                    bot.send_message(admin_chat, msg, parse_mode="HTML")
                for group in db.get_group_chats():
                    bot.send_message(group['chat_id'], msg, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Reminders check error: {e}")


def run_bot():
    token = os.getenv('BOT_TOKEN')
    if not token:
        logger.error("BOT_TOKEN не знайдено!")
        return

    db.init_db()
    bot = SimpleTelegramBot(token)

    # Запускаємо перевірку нагадувань
    reminder_thread = threading.Thread(target=check_reminders_loop, args=(bot,), daemon=True)
    reminder_thread.start()

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
                    chat_type = message.get('chat', {}).get('type', 'private')

                    # Додаємо груповий чат якщо це група
                    if chat_type in ['group', 'supergroup']:
                        db.add_group_chat(chat_id, message.get('chat', {}).get('title'))

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

                    elif text == '/group':
                        db.add_group_chat(chat_id, message.get('chat', {}).get('title'))
                        bot.send_message(chat_id, "✅ Цей чат додано як груповий! Я буду надсилати сюди сповіщення.")

                    elif text == '/stats':
                        report = db.get_full_report(30)
                        bot.send_message(chat_id,
                                         f"📊 <b>Статистика за 30 днів</b>\n\n"
                                         f"🍖 Годувань: {report['feed']}\n"
                                         f"🚶 Прогулянок: {report['walk_minutes']} хв\n"
                                         f"😴 Сну: {report['sleep_hours']} год\n"
                                         f"🚽 Туалет: {report['toilet']}\n"
                                         f"⚠️ Поведінка: {report['behavior']}\n"
                                         f"🧠 Ментальне: {report['mental_minutes']} хв",
                                         parse_mode="HTML")

                    elif text == '/reminders':
                        reminders = db.get_medical_reminders()
                        if not reminders:
                            bot.send_message(chat_id, "📭 Немає активних нагадувань")
                        else:
                            message_text = "💊 <b>Ваші нагадування:</b>\n\n"
                            for r in reminders[:10]:
                                message_text += f"• {r['title']}\n  ⏰ {r['next_due_str']} о {r.get('reminder_time', '09:00')}\n\n"
                            bot.send_message(chat_id, message_text, parse_mode="HTML")

                    # Додавання нового типу тренування
                    elif user_data.get('awaiting_new_training'):
                        db.add_training_type(text)
                        bot.send_message(chat_id, f"✅ Додано нову команду: {text}")
                        user_data['awaiting_new_training'] = False

                    # Додавання нового типу ментальної активності
                    elif user_data.get('awaiting_new_mental'):
                        db.add_mental_type(text)
                        bot.send_message(chat_id, f"✅ Додано нову активність: {text}")
                        user_data['awaiting_new_mental'] = False

                    # Тривалість ментальної активності
                    elif user_data.get('awaiting_mental_duration'):
                        try:
                            duration = int(text)
                            mental_id = user_data['awaiting_mental_duration']
                            types = {t['id']: t for t in db.get_mental_types()}
                            mental = types.get(mental_id)
                            if mental:
                                db.add_mental_activity(mental['name'], duration, 3)
                                bot.send_message(chat_id, f"🧠 Записано: {mental['name']} ({duration} хв)")
                            user_data['awaiting_mental_duration'] = None
                        except ValueError:
                            bot.send_message(chat_id, "❌ Введіть число (хвилини)")

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

                if 'update_id' in update:
                    bot.offset = update['update_id'] + 1

        except Exception as e:
            logger.error(f"Bot loop error: {e}")
            time.sleep(5)

        time.sleep(1)


if __name__ == '__main__':
    run_bot()