#!/usr/bin/env python3
"""
Ayla Tracker - Telegram Bot (Python 3.13 сумісна версія)
"""

import logging
import os
import time
import threading
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import database as db
import requests

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Простий HTTP API замість python-telegram-bot
TELEGRAM_API_URL = "https://api.telegram.org/bot"


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
            ["📊 Статистика", "📈 Звіт", "ℹ️ Допомога"]
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
                         "• ⚖️ Вага - контроль розвитку\n\n"
                         "/start - Головне меню\n"
                         "/myid - Отримати Chat ID",
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


def run_bot():
    token = os.getenv('BOT_TOKEN')
    if not token:
        logger.error("BOT_TOKEN не знайдено!")
        return

    db.init_db()
    bot = SimpleTelegramBot(token)

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