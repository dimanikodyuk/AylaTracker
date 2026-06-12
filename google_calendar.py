#!/usr/bin/env python3
"""
Google Calendar інтеграція для Ayla Tracker
"""

import os
import pickle
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging

logger = logging.getLogger(__name__)

# Якщо змінюєте scope, видаліть token.pickle
SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.pickle'


class GoogleCalendar:
    def __init__(self):
        self.service = None
        self.creds = None
        self.authenticate()

    def authenticate(self):
        """Аутентифікація в Google Calendar"""
        try:
            # Завантажуємо збережені токени
            if os.path.exists(TOKEN_FILE):
                with open(TOKEN_FILE, 'rb') as token:
                    self.creds = pickle.load(token)

            # Якщо токен недійсний або відсутній
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    if not os.path.exists(CREDENTIALS_FILE):
                        logger.error(f"Файл {CREDENTIALS_FILE} не знайдено!")
                        logger.info("Інструкція: https://developers.google.com/calendar/api/quickstart/python")
                        return False

                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    self.creds = flow.run_local_server(port=0)

                # Зберігаємо токен
                with open(TOKEN_FILE, 'wb') as token:
                    pickle.dump(self.creds, token)

            self.service = build('calendar', 'v3', credentials=self.creds)
            logger.info("✅ Google Calendar авторизовано")
            return True

        except Exception as e:
            logger.error(f"Google Calendar помилка: {e}")
            return False

    def add_event(self, summary, description, start_time, end_time=None,
                  location=None, reminders=None):
        """
        Додавання події в календар

        Args:
            summary: Назва події
            description: Опис
            start_time: datetime початку
            end_time: datetime кінця (опціонально)
            location: Місце
            reminders: Нагадування (список хвилин)
        """
        if not self.service:
            return False

        try:
            # Якщо end_time не вказано, подія триває 1 годину
            if not end_time:
                end_time = start_time + datetime.timedelta(hours=1)

            event = {
                'summary': summary,
                'location': location,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'Europe/Kyiv',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'Europe/Kyiv',
                },
            }

            # Додаємо нагадування
            if reminders:
                event['reminders'] = {
                    'useDefault': False,
                    'overrides': [{'method': 'popup', 'minutes': m} for m in reminders]
                }

            event = self.service.events().insert(calendarId='primary', body=event).execute()
            logger.info(f"✅ Подію додано: {event.get('htmlLink')}")
            return event.get('htmlLink')

        except HttpError as error:
            logger.error(f"Помилка додавання події: {error}")
            return False

    def add_feeding_reminder(self, time, meal_number):
        """Додати нагадування про годування"""
        now = datetime.datetime.now()
        feeding_time = datetime.datetime.combine(now.date(), time)

        # Якщо час вже минув сьогодні, додаємо на завтра
        if feeding_time < now:
            feeding_time += datetime.timedelta(days=1)

        return self.add_event(
            summary=f"🍖 Годування Айли #{meal_number}",
            description=f"Час годувати Айлу. Рекомендована порція: {self.get_daily_food()}г",
            start_time=feeding_time,
            end_time=feeding_time + datetime.timedelta(minutes=30),
            reminders=[15, 5]
        )

    def add_walk_reminder(self, time):
        """Додати нагадування про прогулянку"""
        now = datetime.datetime.now()
        walk_time = datetime.datetime.combine(now.date(), time)

        if walk_time < now:
            walk_time += datetime.timedelta(days=1)

        return self.add_event(
            summary="🚶 Прогулянка з Айлою",
            description="Час вийти на прогулянку!",
            start_time=walk_time,
            end_time=walk_time + datetime.timedelta(minutes=30),
            reminders=[10, 5]
        )

    def add_vet_visit(self, date, reason, clinic, doctor):
        """Додати візит до ветеринара"""
        visit_time = datetime.datetime.combine(date, datetime.time(10, 0))

        return self.add_event(
            summary=f"🏥 Візит до ветеринара: {reason}",
            description=f"Лікар: {doctor}\nКлініка: {clinic}\nВізьміть документи Айли",
            start_time=visit_time,
            end_time=visit_time + datetime.timedelta(hours=1),
            location=clinic,
            reminders=[60, 30, 15]
        )

    def add_vaccination_reminder(self, vaccine_name, date):
        """Додати нагадування про вакцинацію"""
        vaccin_time = datetime.datetime.combine(date, datetime.time(11, 0))

        return self.add_event(
            summary=f"💉 Вакцинація: {vaccine_name}",
            description=f"Час для вакцинації Айли. Після вакцинації - спокійний режим",
            start_time=vaccin_time,
            end_time=vaccin_time + datetime.timedelta(hours=1),
            reminders=[1440, 60, 30]  # 1 день, 1 година, 30 хв
        )

    def add_medication_reminder(self, medication_name, time, dosage):
        """Додати нагадування про ліки"""
        now = datetime.datetime.now()
        med_time = datetime.datetime.combine(now.date(), time)

        if med_time < now:
            med_time += datetime.timedelta(days=1)

        return self.add_event(
            summary=f"💊 {medication_name}",
            description=f"Дозування: {dosage}\nДайте ліки Айлі",
            start_time=med_time,
            end_time=med_time + datetime.timedelta(minutes=15),
            reminders=[60, 15, 5]
        )

    def get_upcoming_events(self, max_results=10):
        """Отримати майбутні події"""
        if not self.service:
            return []

        try:
            now = datetime.datetime.utcnow().isoformat() + 'Z'
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            return events

        except HttpError as error:
            logger.error(f"Помилка отримання подій: {error}")
            return []

    def sync_reminders(self):
        """Синхронізувати всі нагадування з бази даних"""
        import database as db

        reminders = db.get_medical_reminders()

        for reminder in reminders:
            # Конвертуємо timestamp в datetime
            next_due = datetime.datetime.fromtimestamp(reminder['next_due'])

            self.add_event(
                summary=f"💊 {reminder['title']}",
                description=reminder.get('description', ''),
                start_time=next_due,
                end_time=next_due + datetime.timedelta(hours=1),
                reminders=[1440, 60, 15]
            )


# Глобальний екземпляр
calendar = GoogleCalendar()


def setup_google_calendar():
    """Інструкція з налаштування Google Calendar"""
    instructions = """
    📅 <b>Налаштування Google Calendar:</b>

    1. Перейдіть на https://console.cloud.google.com/
    2. Створіть новий проект або виберіть існуючий
    3. Увімкніть Google Calendar API
    4. Створіть облікові дані -> OAuth client ID
    5. Завантажте credentials.json в папку AylaTracker
    6. Перезапустіть бота

    Після першого запуску потрібно буде авторизуватися
    """
    return instructions