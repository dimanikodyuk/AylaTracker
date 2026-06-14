#!/usr/bin/env python3
"""
Database module - єдине джерело роботи з БД з потокобезпекою
"""

import sqlite3
import threading
import time
import os
from datetime import datetime, timedelta
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

DB_PATH = "ayla.db"
_db_lock = threading.Lock()


def get_db_connection():
    """Отримання потокобезпечного з'єднання з БД"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def get_db():
    """Контекстний менеджер для роботи з БД"""
    with _db_lock:
        conn = get_db_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()


def migrate_db():
    """Міграція бази даних - додавання нових колонок та таблиць (БЕЗ ВТРАТИ ДАНИХ)"""
    with get_db() as conn:
        # Перевіряємо таблицю medical_reminders
        cursor = conn.execute("PRAGMA table_info(medical_reminders)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'reminder_time' not in columns:
            conn.execute("ALTER TABLE medical_reminders ADD COLUMN reminder_time TEXT DEFAULT '09:00'")
            logger.info("✅ Додано колонку reminder_time до medical_reminders")

        if 'last_triggered' not in columns:
            conn.execute("ALTER TABLE medical_reminders ADD COLUMN last_triggered INTEGER DEFAULT 0")
            logger.info("✅ Додано колонку last_triggered до medical_reminders")

        # Перевіряємо таблицю body_measurements
        cursor = conn.execute("PRAGMA table_info(body_measurements)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'note' not in columns:
            conn.execute("ALTER TABLE body_measurements ADD COLUMN note TEXT")
            logger.info("✅ Додано колонку note до body_measurements")

        # Перевіряємо таблицю allowed_users
        cursor = conn.execute("PRAGMA table_info(allowed_users)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'role' not in columns:
            conn.execute("ALTER TABLE allowed_users ADD COLUMN role TEXT DEFAULT 'user'")
            logger.info("✅ Додано колонку role до allowed_users")

        # ========== НОВІ ТАБЛИЦІ (тільки CREATE IF NOT EXISTS) ==========

        # Таблиця збитків
        conn.execute('''
            CREATE TABLE IF NOT EXISTS damages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                cost REAL NOT NULL,
                category TEXT,
                note TEXT,
                user_id INTEGER
            )
        ''')
        logger.info("✅ Перевірено/створено таблицю damages")

        # Таблиця карантину
        conn.execute('''
            CREATE TABLE IF NOT EXISTS quarantine (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                last_vaccination_date INTEGER NOT NULL,
                quarantine_end_date INTEGER NOT NULL,
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        ''')
        logger.info("✅ Перевірено/створено таблицю quarantine")

        # Додаємо початковий запис карантину тільки якщо таблиця порожня
        count = conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
        if count == 0:
            default_date = int((datetime.now() - timedelta(days=1)).timestamp())
            conn.execute("""
                INSERT INTO quarantine (last_vaccination_date, quarantine_end_date)
                VALUES (?, ?)
            """, (default_date, default_date))
            logger.info("✅ Додано початковий запис quarantine (карантин завершено)")

        # Таблиця зумісів
        conn.execute('''
            CREATE TABLE IF NOT EXISTS zoomies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                duration INTEGER,
                intensity INTEGER DEFAULT 3,
                note TEXT
            )
        ''')
        logger.info("✅ Перевірено/створено таблицю zoomies")

        # Додаємо нові налаштування, якщо їх немає
        new_settings = {
            "last_vaccination_date": "",
            "quarantine_days": "14"
        }
        for key, value in new_settings.items():
            conn.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, value))
            logger.info(f"✅ Перевірено налаштування {key}")

        logger.info("✅ Міграцію БД завершено (дані збережено)")


def init_db():
    """Ініціалізація бази даних - створює таблиці ТІЛЬКИ якщо їх немає"""
    with get_db() as conn:
        # Перевіряємо чи існує таблиця events (ознака, що БД вже створена)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
        table_exists = cursor.fetchone() is not None

        if not table_exists:
            # Тільки якщо БД порожня - створюємо всі таблиці
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    subtype TEXT,
                    value INTEGER,
                    note TEXT,
                    user_id INTEGER
                );

                CREATE TABLE IF NOT EXISTS active_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_type TEXT NOT NULL,
                    start_time INTEGER NOT NULL,
                    expected_duration INTEGER DEFAULT 0,
                    note TEXT
                );

                CREATE TABLE IF NOT EXISTS weight_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    note TEXT,
                    user_id INTEGER
                );

                CREATE TABLE IF NOT EXISTS training_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    command TEXT NOT NULL,
                    duration INTEGER,
                    success_rate INTEGER,
                    note TEXT,
                    user_id INTEGER
                );

                CREATE TABLE IF NOT EXISTS training_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    icon TEXT DEFAULT '🏋️',
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                );

                CREATE TABLE IF NOT EXISTS mental_activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    activity_type TEXT NOT NULL,
                    duration INTEGER,
                    difficulty INTEGER,
                    note TEXT,
                    user_id INTEGER
                );

                CREATE TABLE IF NOT EXISTS mental_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    icon TEXT DEFAULT '🧠',
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                );

                CREATE TABLE IF NOT EXISTS behavior_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    icon TEXT DEFAULT '⚠️',
                    severity INTEGER DEFAULT 1,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                );

                CREATE TABLE IF NOT EXISTS medical_reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    reminder_time TEXT,
                    interval_days INTEGER NOT NULL,
                    last_triggered INTEGER,
                    next_due INTEGER NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    user_id INTEGER
                );

                CREATE TABLE IF NOT EXISTS symptoms_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    temperature REAL,
                    appetite INTEGER,
                    mood TEXT,
                    note TEXT,
                    user_id INTEGER
                );

                CREATE TABLE IF NOT EXISTS vet_clinics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    address TEXT,
                    phone TEXT,
                    website TEXT,
                    note TEXT
                );

                CREATE TABLE IF NOT EXISTS food_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    food_type TEXT NOT NULL,
                    amount REAL,
                    brand TEXT,
                    note TEXT,
                    user_id INTEGER
                );

                CREATE TABLE IF NOT EXISTS allergies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product TEXT NOT NULL,
                    reaction TEXT,
                    severity INTEGER,
                    note TEXT
                );

                CREATE TABLE IF NOT EXISTS diary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    user_id INTEGER
                );

                CREATE TABLE IF NOT EXISTS potty_cues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    cue_type TEXT NOT NULL,
                    success INTEGER DEFAULT 0,
                    note TEXT
                );

                CREATE TABLE IF NOT EXISTS trigger_exposures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    trigger_type TEXT NOT NULL,
                    reaction_score INTEGER,
                    note TEXT
                );

                CREATE TABLE IF NOT EXISTS allowed_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL UNIQUE,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    added_at INTEGER NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    role TEXT DEFAULT 'user'
                );

                CREATE TABLE IF NOT EXISTS group_chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL UNIQUE,
                    title TEXT,
                    is_active INTEGER DEFAULT 1,
                    added_at INTEGER DEFAULT (strftime('%s', 'now'))
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at INTEGER DEFAULT (strftime('%s', 'now'))
                );

                CREATE TABLE IF NOT EXISTS vet_vaccinations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vaccine_name TEXT NOT NULL,
                    vaccine_date INTEGER NOT NULL,
                    vaccine_next_due INTEGER,
                    vaccine_series TEXT,
                    vet_name TEXT,
                    clinic_name TEXT,
                    notes TEXT,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                );

                CREATE TABLE IF NOT EXISTS parasite_treatment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    treatment_name TEXT NOT NULL,
                    treatment_date INTEGER NOT NULL,
                    next_due INTEGER,
                    parasite_type TEXT,
                    medication_name TEXT,
                    dosage TEXT,
                    notes TEXT,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                );

                CREATE TABLE IF NOT EXISTS dental_care (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    procedure_date INTEGER NOT NULL,
                    procedure_type TEXT NOT NULL,
                    vet_name TEXT,
                    notes TEXT,
                    next_due INTEGER,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                );

                CREATE TABLE IF NOT EXISTS family_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    role TEXT DEFAULT 'member',
                    chat_id INTEGER,
                    notify_enabled INTEGER DEFAULT 1,
                    added_at INTEGER DEFAULT (strftime('%s', 'now'))
                );

                CREATE TABLE IF NOT EXISTS smart_reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    condition_type TEXT NOT NULL,
                    condition_value TEXT,
                    days_before INTEGER DEFAULT 0,
                    enabled INTEGER DEFAULT 1,
                    last_triggered INTEGER,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                );

                CREATE TABLE IF NOT EXISTS body_measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    neck_cm REAL,
                    chest_cm REAL,
                    waist_cm REAL,
                    length_cm REAL,
                    height_cm REAL,
                    note TEXT,
                    user_id INTEGER
                );
            ''')

            # Ініціалізація налаштувань тільки для нової БД
            defaults = {
                "pet_name": "Айла",
                "birth_date": "",
                "target_weight": "8.0",
                "telegram_bot_token": "",
                "telegram_chat_id": "",
                "group_chat_id": "",
                "food_density_calories": "3800",
                "potty_reminder_minutes": "25",
                "planned_meals": "4",
                "planned_sleep_hours": "20"
            }
            for key, value in defaults.items():
                conn.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, value))

            # Типи тренувань
            training_defaults = [("Сідати", "🐕"), ("Лежати", "😴"), ("До мене", "🏃"), ("Поруч", "🚶"), ("Дай лапу", "🖐️"),
                                 ("Голос", "🗣️"), ("Апорт", "🎾")]
            for name, icon in training_defaults:
                conn.execute('INSERT OR IGNORE INTO training_types (name, icon) VALUES (?, ?)', (name, icon))

            # Типи ментальних активностей
            mental_defaults = [("Головоломка", "🧩"), ("Пошук ласощів", "🔍"), ("Вивчення трюків", "🎓"),
                               ("Нюхальний килимок", "👃"), ("Клікер-тренування", "🖱️"), ("Соціалізація", "🤝")]
            for name, icon in mental_defaults:
                conn.execute('INSERT OR IGNORE INTO mental_types (name, icon) VALUES (?, ?)', (name, icon))

            # Типи поведінки
            behavior_defaults = [("Кусається", "🦷", 3), ("Гавкає", "🗣️", 2), ("Гризе меблі", "🪑", 3),
                                 ("Стрибає на людей", "🦘", 2), ("Тягне повідок", "🪢", 2), ("Погана поведінка", "⚠️", 1)]
            for name, icon, severity in behavior_defaults:
                conn.execute('INSERT OR IGNORE INTO behavior_types (name, icon, severity) VALUES (?, ?, ?)',
                             (name, icon, severity))

            logger.info("✅ Нова база даних створена")
        else:
            logger.info("✅ Існуюча база даних знайдена, дані збережено")

    # Виконуємо міграцію (додаємо нові таблиці та колонки)
    migrate_db()

    print("✅ База даних ініціалізована (дані збережено)")


def get_setting(key, default=None):
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row['value'] if row else default


def set_setting(key, value):
    with get_db() as conn:
        conn.execute('INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)',
                     (key, value, int(time.time())))


def get_pet_name():
    return get_setting('pet_name', 'Айла')


def get_pet_age_months():
    birth_date = get_setting('birth_date')
    if not birth_date:
        return 4
    try:
        birth = datetime.strptime(birth_date, '%Y-%m-%d')
        today = datetime.now()
        months = (today.year - birth.year) * 12 + (today.month - birth.month)
        return max(1, months)
    except:
        return 4


def get_safe_walk_duration_minutes():
    months = get_pet_age_months()
    return min(months * 5, 120)


def calculate_daily_food_amount(weight_kg, activity_factor=None):
    if not weight_kg or weight_kg <= 0:
        weight_kg = 5

    months = get_pet_age_months()
    if months < 4:
        activity_factor = 2.0
    elif months < 12:
        activity_factor = 1.8
    else:
        activity_factor = 1.6

    rer = 70 * (weight_kg ** 0.75)
    daily_calories = rer * activity_factor

    food_density = float(get_setting('food_density_calories', 3800))
    daily_grams = (daily_calories / food_density) * 1000

    return max(50, min(800, int(daily_grams)))


def add_event(event_type, subtype=None, value=None, note=None, user_id=None):
    with get_db() as conn:
        now = int(time.time())
        conn.execute("""
            INSERT INTO events (timestamp, type, subtype, value, note, user_id) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (now, event_type, subtype, value, note, user_id))
        return True


def add_behavior(behavior_type, severity=None, note=None):
    with get_db() as conn:
        now = int(time.time())
        conn.execute("""
            INSERT INTO events (timestamp, type, subtype, value, note) 
            VALUES (?, ?, ?, ?, ?)
        """, (now, 'behavior', behavior_type, severity or 1, note))
        return True


def update_event(event_id, new_timestamp=None, new_type=None, new_subtype=None, new_value=None, new_note=None):
    with get_db() as conn:
        updates = []
        params = []

        if new_timestamp is not None:
            updates.append("timestamp = ?")
            params.append(new_timestamp)
        if new_type is not None:
            updates.append("type = ?")
            params.append(new_type)
        if new_subtype is not None:
            updates.append("subtype = ?")
            params.append(new_subtype)
        if new_value is not None:
            updates.append("value = ?")
            params.append(new_value)
        if new_note is not None:
            updates.append("note = ?")
            params.append(new_note)

        if not updates:
            return False

        params.append(event_id)
        query = f"UPDATE events SET {', '.join(updates)} WHERE id = ?"
        conn.execute(query, params)
        return True


def get_event_by_id(event_id):
    with get_db() as conn:
        row = conn.execute("""
            SELECT id, type, subtype, timestamp, value, note
            FROM events WHERE id = ?
        """, (event_id,)).fetchone()
        return dict(row) if row else None


def start_session(session_type, expected_duration=0):
    with get_db() as conn:
        now = int(time.time())
        conn.execute("DELETE FROM active_sessions WHERE session_type = ?", (session_type,))
        conn.execute("""
            INSERT INTO active_sessions (session_type, start_time, expected_duration) 
            VALUES (?, ?, ?)
        """, (session_type, now, expected_duration))
        return True


def get_active_session(session_type):
    with get_db() as conn:
        row = conn.execute("SELECT start_time, expected_duration FROM active_sessions WHERE session_type = ?",
                           (session_type,)).fetchone()
        if row:
            duration = int(time.time()) - row['start_time']
            return {
                'active': True,
                'start_time': row['start_time'],
                'duration': duration,
                'expected_duration': row['expected_duration']
            }
        return {'active': False, 'duration': 0, 'expected_duration': 0}


def stop_session(session_type):
    with get_db() as conn:
        row = conn.execute("SELECT start_time FROM active_sessions WHERE session_type = ?", (session_type,)).fetchone()
        if not row:
            return 0

        start_time = row['start_time']
        end_time = int(time.time())
        duration = max(60, end_time - start_time)

        conn.execute("""
            INSERT INTO events (timestamp, type, value, note) 
            VALUES (?, ?, ?, ?)
        """, (start_time, session_type, duration, f"тривалість {duration // 60} хв"))

        conn.execute("DELETE FROM active_sessions WHERE session_type = ?", (session_type,))
        return duration


def get_today_stats():
    today_start = int(datetime.now().replace(hour=0, minute=0, second=0).timestamp())
    with get_db() as conn:
        feed = \
        conn.execute("SELECT COUNT(*) FROM events WHERE type='feed' AND timestamp >= ?", (today_start,)).fetchone()[0]
        walk = \
        conn.execute("SELECT SUM(value) FROM events WHERE type='walk' AND timestamp >= ?", (today_start,)).fetchone()[
            0] or 0
        toilet = \
        conn.execute("SELECT COUNT(*) FROM events WHERE type='toilet' AND timestamp >= ?", (today_start,)).fetchone()[0]
        sleep = \
        conn.execute("SELECT SUM(value) FROM events WHERE type='sleep' AND timestamp >= ?", (today_start,)).fetchone()[
            0] or 0
        behavior = \
        conn.execute("SELECT COUNT(*) FROM events WHERE type='behavior' AND timestamp >= ?", (today_start,)).fetchone()[
            0]
        return {
            'feed': feed,
            'walk_minutes': walk // 60,
            'walk_seconds': walk,
            'sleep_hours': sleep // 3600,
            'sleep_seconds': sleep,
            'toilet': toilet,
            'behavior': behavior
        }


def get_settings():
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        settings = {}
        for row in rows:
            settings[row['key']] = row['value']

        defaults = {
            'pet_name': 'Айла',
            'birth_date': '',
            'food_density_calories': '3800',
            'planned_meals': '4',
            'planned_sleep_hours': '14',
            'target_weight': '8.0',
            'telegram_bot_token': '',
            'telegram_chat_id': '',
            'group_chat_id': '',
            'potty_reminder_minutes': '25',
            'last_vaccination_date': '',
            'quarantine_days': '14'
        }

        for key, default in defaults.items():
            if key not in settings:
                settings[key] = default

        return settings


def get_events_list(limit=200):
    with get_db() as conn:
        events = conn.execute("""
            SELECT id, type, subtype, timestamp, value, note,
                   datetime(timestamp, 'unixepoch', 'localtime') as time_str,
                   datetime(timestamp, 'unixepoch', 'localtime') as datetime_full,
                   date(timestamp, 'unixepoch', 'localtime') as date_only
            FROM events ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(e) for e in events]


def get_events_by_date_range(start_date, end_date):
    start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp())
    end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp()) + 86400
    with get_db() as conn:
        events = conn.execute("""
            SELECT id, type, subtype, timestamp, value, note,
                   datetime(timestamp, 'unixepoch', 'localtime') as time_str,
                   date(timestamp, 'unixepoch', 'localtime') as date_only
            FROM events 
            WHERE timestamp >= ? AND timestamp < ?
            ORDER BY timestamp ASC
        """, (start_ts, end_ts)).fetchall()
        return [dict(e) for e in events]


def delete_event(event_id):
    with get_db() as conn:
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
        return True


def add_weight(weight):
    with get_db() as conn:
        now = int(time.time())
        conn.execute("INSERT INTO weight_logs (timestamp, weight) VALUES (?, ?)", (now, weight))
        return True


def update_weight_log(weight_id, new_weight, new_timestamp=None):
    with get_db() as conn:
        if new_timestamp:
            conn.execute("UPDATE weight_logs SET weight = ?, timestamp = ? WHERE id = ?",
                         (new_weight, new_timestamp, weight_id))
        else:
            conn.execute("UPDATE weight_logs SET weight = ? WHERE id = ?", (new_weight, weight_id))
        return True


def delete_weight_log(weight_id):
    with get_db() as conn:
        conn.execute("DELETE FROM weight_logs WHERE id = ?", (weight_id,))
        return True


def get_last_weight():
    with get_db() as conn:
        row = conn.execute("SELECT weight FROM weight_logs ORDER BY timestamp DESC LIMIT 1").fetchone()
        return row['weight'] if row else None


def get_weight_history(days=90):
    start_time = int(time.time()) - days * 86400
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, datetime(timestamp, 'unixepoch', 'localtime') as date, weight, timestamp
            FROM weight_logs WHERE timestamp >= ? ORDER BY timestamp
        """, (start_time,)).fetchall()
        return [{'id': r['id'], 'date': r['date'], 'weight': r['weight'], 'timestamp': r['timestamp']} for r in rows]


def add_training(command, duration, success_rate):
    with get_db() as conn:
        now = int(time.time())
        conn.execute("""
            INSERT INTO training_logs (timestamp, command, duration, success_rate)
            VALUES (?, ?, ?, ?)
        """, (now, command, duration, success_rate))
        return True


def update_training_log(training_id, new_command=None, new_duration=None, new_success_rate=None, new_timestamp=None):
    with get_db() as conn:
        updates = []
        params = []

        if new_command is not None:
            updates.append("command = ?")
            params.append(new_command)
        if new_duration is not None:
            updates.append("duration = ?")
            params.append(new_duration)
        if new_success_rate is not None:
            updates.append("success_rate = ?")
            params.append(new_success_rate)
        if new_timestamp is not None:
            updates.append("timestamp = ?")
            params.append(new_timestamp)

        if not updates:
            return False

        params.append(training_id)
        query = f"UPDATE training_logs SET {', '.join(updates)} WHERE id = ?"
        conn.execute(query, params)
        return True


def delete_training_log(training_id):
    with get_db() as conn:
        conn.execute("DELETE FROM training_logs WHERE id = ?", (training_id,))
        return True


def get_training_stats():
    with get_db() as conn:
        stats = conn.execute("""
            SELECT command, COUNT(*) as count, AVG(success_rate) as avg_success
            FROM training_logs GROUP BY command
        """).fetchall()
        return [{'command': r['command'], 'count': r['count'], 'avg_success': round(r['avg_success'], 1)} for r in
                stats]


def get_training_history(limit=50):
    with get_db() as conn:
        history = conn.execute("""
            SELECT id, datetime(timestamp, 'unixepoch', 'localtime') as date, timestamp,
                   command, duration, success_rate
            FROM training_logs ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [
            {'id': r['id'], 'date': r['date'], 'timestamp': r['timestamp'], 'command': r['command'],
             'duration': r['duration'], 'success_rate': r['success_rate']}
            for r in history]


def get_training_types():
    with get_db() as conn:
        rows = conn.execute("SELECT id, name, icon FROM training_types ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def add_training_type(name, icon='🏋️'):
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO training_types (name, icon) VALUES (?, ?)", (name, icon))
        return True


def add_mental_activity(activity_type, duration, difficulty=3):
    with get_db() as conn:
        now = int(time.time())
        conn.execute("""
            INSERT INTO mental_activities (timestamp, activity_type, duration, difficulty)
            VALUES (?, ?, ?, ?)
        """, (now, activity_type, duration, difficulty))
        return True


def update_mental_activity(activity_id, new_activity_type=None, new_duration=None, new_timestamp=None):
    with get_db() as conn:
        updates = []
        params = []

        if new_activity_type is not None:
            updates.append("activity_type = ?")
            params.append(new_activity_type)
        if new_duration is not None:
            updates.append("duration = ?")
            params.append(new_duration)
        if new_timestamp is not None:
            updates.append("timestamp = ?")
            params.append(new_timestamp)

        if not updates:
            return False

        params.append(activity_id)
        query = f"UPDATE mental_activities SET {', '.join(updates)} WHERE id = ?"
        conn.execute(query, params)
        return True


def delete_mental_activity(activity_id):
    with get_db() as conn:
        conn.execute("DELETE FROM mental_activities WHERE id = ?", (activity_id,))
        return True


def get_mental_activities(limit=50):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, activity_type, duration, difficulty,
                   datetime(timestamp, 'unixepoch', 'localtime') as date, timestamp
            FROM mental_activities ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_mental_stats(days=7):
    start_time = int(time.time()) - days * 86400
    with get_db() as conn:
        rows = conn.execute("""
            SELECT date(timestamp, 'unixepoch') as date, SUM(duration) as total
            FROM mental_activities WHERE timestamp >= ? GROUP BY date ORDER BY date
        """, (start_time,)).fetchall()
        return [{'date': r['date'], 'duration': r['total']} for r in rows]


def get_mental_types():
    with get_db() as conn:
        rows = conn.execute("SELECT id, name, icon FROM mental_types ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def add_mental_type(name, icon='🧠'):
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO mental_types (name, icon) VALUES (?, ?)", (name, icon))
        return True


def get_behavior_types():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, icon, severity FROM behavior_types ORDER BY severity DESC, name").fetchall()
        return [dict(r) for r in rows]


def add_potty_cue(cue_type, success=0):
    with get_db() as conn:
        now = int(time.time())
        conn.execute("""
            INSERT INTO potty_cues (timestamp, cue_type, success) VALUES (?, ?, ?)
        """, (now, cue_type, success))
        return True


def get_potty_stats():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT cue_type, COUNT(*) as count FROM potty_cues GROUP BY cue_type
        """).fetchall()
        return [{'type': r['cue_type'], 'count': r['count']} for r in rows]


def add_medical_reminder(title, description, interval_days, reminder_time='09:00'):
    with get_db() as conn:
        now = datetime.now()
        reminder_hour, reminder_minute = map(int, reminder_time.split(':'))

        next_due_date = datetime(now.year, now.month, now.day, reminder_hour, reminder_minute, 0)

        if next_due_date <= now:
            next_due_date += timedelta(days=1)

        if interval_days > 0:
            next_due_date += timedelta(days=interval_days)

        next_due = int(next_due_date.timestamp())

        conn.execute("""
            INSERT INTO medical_reminders (title, description, interval_days, reminder_time, last_triggered, next_due, enabled)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (title, description, interval_days, reminder_time, int(now.timestamp()), next_due))

        return True


def get_medical_reminders():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM medical_reminders WHERE enabled = 1 ORDER BY next_due ASC").fetchall()
        reminders = []
        for r in rows:
            rem = dict(r)
            rem['next_due_str'] = datetime.fromtimestamp(rem['next_due']).strftime('%d.%m.%Y')
            reminders.append(rem)
        return reminders


def get_due_medical_reminders():
    now = int(time.time())
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM medical_reminders 
            WHERE enabled = 1 AND next_due <= ?
            ORDER BY next_due ASC
        """, (now,)).fetchall()
        reminders = []
        for r in rows:
            rem = dict(r)
            next_dt = datetime.fromtimestamp(rem['next_due'])
            rem['next_due_str'] = next_dt.strftime('%d.%m.%Y %H:%M')
            reminders.append(rem)
        return reminders


def complete_reminder(reminder_id):
    with get_db() as conn:
        row = conn.execute("SELECT interval_days, reminder_time FROM medical_reminders WHERE id = ?",
                           (reminder_id,)).fetchone()
        if row:
            if row['interval_days'] == 0:
                conn.execute("DELETE FROM medical_reminders WHERE id = ?", (reminder_id,))
                return True

            now = datetime.now()
            reminder_time = row['reminder_time'] or '09:00'
            reminder_hour, reminder_minute = map(int, reminder_time.split(':'))

            next_due_date = datetime(now.year, now.month, now.day, reminder_hour, reminder_minute, 0)

            if next_due_date <= now:
                next_due_date += timedelta(days=1)

            next_due_date += timedelta(days=row['interval_days'])
            next_due = int(next_due_date.timestamp())

            conn.execute("""
                UPDATE medical_reminders SET last_triggered = ?, next_due = ? WHERE id = ?
            """, (int(now.timestamp()), next_due, reminder_id))
            return True
    return False


def get_notification_recipients():
    members = get_family_members()
    group_chats = get_group_chats()
    recipients = []

    for m in members:
        if m.get('chat_id') and m.get('notify_enabled'):
            recipients.append(m['chat_id'])

    for g in group_chats:
        recipients.append(g['chat_id'])

    admin_chat = get_setting('telegram_chat_id')
    if admin_chat:
        recipients.append(int(admin_chat))

    return list(set(recipients))


def delete_reminder(reminder_id):
    with get_db() as conn:
        conn.execute("DELETE FROM medical_reminders WHERE id = ?", (reminder_id,))
        return True


def add_symptom(temperature=None, appetite=None, mood=None, note=None):
    with get_db() as conn:
        now = int(time.time())
        conn.execute("""
            INSERT INTO symptoms_log (timestamp, temperature, appetite, mood, note)
            VALUES (?, ?, ?, ?, ?)
        """, (now, temperature, appetite, mood, note))
        return True


def get_symptoms():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, datetime(timestamp, 'unixepoch', 'localtime') as date,
                   temperature, appetite, mood, note
            FROM symptoms_log ORDER BY timestamp DESC LIMIT 20
        """).fetchall()
        return [dict(r) for r in rows]


def delete_symptom(symptom_id):
    with get_db() as conn:
        conn.execute("DELETE FROM symptoms_log WHERE id = ?", (symptom_id,))
        return True


def add_allergy(product, reaction, severity=3):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO allergies (product, reaction, severity) VALUES (?, ?, ?)
        """, (product, reaction, severity))
        return True


def get_allergies():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM allergies ORDER BY severity DESC").fetchall()
        return [dict(r) for r in rows]


def delete_allergy(allergy_id):
    with get_db() as conn:
        conn.execute("DELETE FROM allergies WHERE id = ?", (allergy_id,))
        return True


def add_user(chat_id, username=None, first_name=None, last_name=None):
    with get_db() as conn:
        now = int(time.time())
        conn.execute("""
            INSERT OR IGNORE INTO allowed_users (chat_id, username, first_name, last_name, added_at, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (chat_id, username, first_name, last_name, now))
        return True


def add_group_chat(chat_id, title=None):
    with get_db() as conn:
        now = int(time.time())
        conn.execute("""
            INSERT OR IGNORE INTO group_chats (chat_id, title, is_active, added_at)
            VALUES (?, ?, 1, ?)
        """, (chat_id, title, now))
        return True


def get_group_chats():
    with get_db() as conn:
        rows = conn.execute("SELECT chat_id, title FROM group_chats WHERE is_active = 1").fetchall()
        return [dict(r) for r in rows]


def get_events_for_day(start_timestamp, end_timestamp):
    with get_db() as conn:
        events = conn.execute("""
            SELECT id, type, subtype, timestamp, value, note
            FROM events 
            WHERE timestamp >= ? AND timestamp < ?
            ORDER BY timestamp ASC
        """, (start_timestamp, end_timestamp)).fetchall()
        return [dict(e) for e in events]


def is_user_allowed(chat_id):
    with get_db() as conn:
        row = conn.execute("SELECT 1 FROM allowed_users WHERE chat_id = ? AND is_active = 1", (chat_id,)).fetchone()
        if row:
            return True
        row = conn.execute("SELECT 1 FROM group_chats WHERE chat_id = ? AND is_active = 1", (chat_id,)).fetchone()
        return row is not None


def get_weekly_chart_data():
    start_time = int(time.time()) - 7 * 86400
    with get_db() as conn:
        walk_data = conn.execute("""
            SELECT date(timestamp, 'unixepoch') as date, COALESCE(SUM(value)/60, 0) as total
            FROM events WHERE type='walk' AND timestamp >= ? 
            GROUP BY date ORDER BY date
        """, (start_time,)).fetchall()

        sleep_data = conn.execute("""
            SELECT date(timestamp, 'unixepoch') as date, COALESCE(SUM(value)/3600, 0) as total
            FROM events WHERE type='sleep' AND timestamp >= ? 
            GROUP BY date ORDER BY date
        """, (start_time,)).fetchall()

        dates = []
        for i in range(7):
            d = datetime.now() - timedelta(days=6 - i)
            dates.append(d.strftime('%Y-%m-%d'))

        walk_dict = {r['date']: r['total'] for r in walk_data}
        sleep_dict = {r['date']: r['total'] for r in sleep_data}

        return {
            'dates': dates,
            'walk': [walk_dict.get(d, 0) for d in dates],
            'sleep': [sleep_dict.get(d, 0) for d in dates]
        }


def get_full_report(days=7):
    start_time = int(time.time()) - days * 86400
    with get_db() as conn:
        feed = \
        conn.execute("SELECT COUNT(*) FROM events WHERE type='feed' AND timestamp >= ?", (start_time,)).fetchone()[0]
        walk = conn.execute("SELECT COALESCE(SUM(value), 0) FROM events WHERE type='walk' AND timestamp >= ?",
                            (start_time,)).fetchone()[0]
        toilet = \
        conn.execute("SELECT COUNT(*) FROM events WHERE type='toilet' AND timestamp >= ?", (start_time,)).fetchone()[0]
        sleep = conn.execute("SELECT COALESCE(SUM(value), 0) FROM events WHERE type='sleep' AND timestamp >= ?",
                             (start_time,)).fetchone()[0]
        mental = conn.execute("SELECT COALESCE(SUM(duration), 0) FROM mental_activities WHERE timestamp >= ?",
                              (start_time,)).fetchone()[0]
        training_count = \
        conn.execute("SELECT COUNT(*) FROM training_logs WHERE timestamp >= ?", (start_time,)).fetchone()[0]
        training_avg = conn.execute("SELECT COALESCE(AVG(success_rate), 0) FROM training_logs WHERE timestamp >= ?",
                                    (start_time,)).fetchone()[0]
        behavior = \
        conn.execute("SELECT COUNT(*) FROM events WHERE type='behavior' AND timestamp >= ?", (start_time,)).fetchone()[
            0]

        return {
            'days': days,
            'feed': feed,
            'walk_seconds': walk,
            'walk_minutes': walk // 60,
            'toilet': toilet,
            'sleep_seconds': sleep,
            'sleep_hours': sleep // 3600,
            'mental_minutes': mental,
            'training_count': training_count,
            'training_avg': round(training_avg, 1),
            'behavior': behavior
        }


# ========== ПРОПОРЦІЇ ==========

def add_body_measurement(neck_cm=None, chest_cm=None, waist_cm=None, length_cm=None, height_cm=None, note=None):
    with get_db() as conn:
        now = int(time.time())
        conn.execute("""
            INSERT INTO body_measurements (timestamp, neck_cm, chest_cm, waist_cm, length_cm, height_cm, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (now, neck_cm, chest_cm, waist_cm, length_cm, height_cm, note))
        return True


def get_body_measurements(limit=30):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, neck_cm, chest_cm, waist_cm, length_cm, height_cm, note,
                   datetime(timestamp, 'unixepoch', 'localtime') as date, timestamp
            FROM body_measurements ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def update_body_measurement(measurement_id, neck_cm=None, chest_cm=None, waist_cm=None, length_cm=None, height_cm=None,
                            note=None, new_timestamp=None):
    with get_db() as conn:
        updates = []
        params = []

        if neck_cm is not None:
            updates.append("neck_cm = ?")
            params.append(neck_cm)
        if chest_cm is not None:
            updates.append("chest_cm = ?")
            params.append(chest_cm)
        if waist_cm is not None:
            updates.append("waist_cm = ?")
            params.append(waist_cm)
        if length_cm is not None:
            updates.append("length_cm = ?")
            params.append(length_cm)
        if height_cm is not None:
            updates.append("height_cm = ?")
            params.append(height_cm)
        if note is not None:
            updates.append("note = ?")
            params.append(note)
        if new_timestamp is not None:
            updates.append("timestamp = ?")
            params.append(new_timestamp)

        if not updates:
            return False

        params.append(measurement_id)
        query = f"UPDATE body_measurements SET {', '.join(updates)} WHERE id = ?"
        conn.execute(query, params)
        return True


def delete_body_measurement(measurement_id):
    with get_db() as conn:
        conn.execute("DELETE FROM body_measurements WHERE id = ?", (measurement_id,))
        return True


# ========== ВЕТЕРИНАРНИЙ ПАСПОРТ ==========

def add_vaccination(vaccine_name, vaccine_date, next_due=None, series=None, vet_name=None, clinic_name=None,
                    notes=None):
    with get_db() as conn:
        vaccine_ts = int(datetime.strptime(vaccine_date, '%Y-%m-%d').timestamp())
        next_due_ts = int(datetime.strptime(next_due, '%Y-%m-%d').timestamp()) if next_due else None
        conn.execute("""
            INSERT INTO vet_vaccinations (vaccine_name, vaccine_date, vaccine_next_due, vaccine_series, vet_name, clinic_name, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (vaccine_name, vaccine_ts, next_due_ts, series, vet_name, clinic_name, notes))
        return True


def get_vaccinations():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, vaccine_name, 
                   datetime(vaccine_date, 'unixepoch') as vaccine_date,
                   datetime(vaccine_next_due, 'unixepoch') as next_due,
                   vaccine_series, vet_name, clinic_name, notes
            FROM vet_vaccinations ORDER BY vaccine_date DESC
        """).fetchall()
        return [dict(r) for r in rows]


def add_parasite_treatment(name, treatment_date, next_due=None, parasite_type=None, medication=None, dosage=None,
                           notes=None):
    with get_db() as conn:
        treatment_ts = int(datetime.strptime(treatment_date, '%Y-%m-%d').timestamp())
        next_due_ts = int(datetime.strptime(next_due, '%Y-%m-%d').timestamp()) if next_due else None
        conn.execute("""
            INSERT INTO parasite_treatment (treatment_name, treatment_date, next_due, parasite_type, medication_name, dosage, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, treatment_ts, next_due_ts, parasite_type, medication, dosage, notes))
        return True


def get_parasite_treatments():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, treatment_name,
                   datetime(treatment_date, 'unixepoch') as treatment_date,
                   datetime(next_due, 'unixepoch') as next_due,
                   parasite_type, medication_name, dosage, notes
            FROM parasite_treatment ORDER BY treatment_date DESC
        """).fetchall()
        return [dict(r) for r in rows]


def add_dental_procedure(procedure_date, procedure_type, vet_name=None, notes=None, next_due=None):
    with get_db() as conn:
        date_ts = int(datetime.strptime(procedure_date, '%Y-%m-%d').timestamp())
        next_due_ts = int(datetime.strptime(next_due, '%Y-%m-%d').timestamp()) if next_due else None
        conn.execute("""
            INSERT INTO dental_care (procedure_date, procedure_type, vet_name, notes, next_due)
            VALUES (?, ?, ?, ?, ?)
        """, (date_ts, procedure_type, vet_name, notes, next_due_ts))
        return True


def get_dental_history():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, procedure_type, vet_name, notes,
                   datetime(procedure_date, 'unixepoch') as procedure_date,
                   datetime(next_due, 'unixepoch') as next_due
            FROM dental_care ORDER BY procedure_date DESC
        """).fetchall()
        return [dict(r) for r in rows]


# ========== СІМЕЙНИЙ ДОСТУП ==========

def add_family_member(name, role='member', chat_id=None, notify=True):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO family_members (name, role, chat_id, notify_enabled)
            VALUES (?, ?, ?, ?)
        """, (name, role, chat_id, 1 if notify else 0))
        return True


def get_family_members():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, name, role, chat_id, notify_enabled,
                   datetime(added_at, 'unixepoch') as added_at
            FROM family_members ORDER BY id
        """).fetchall()
        return [dict(r) for r in rows]


def delete_family_member(member_id):
    with get_db() as conn:
        conn.execute("DELETE FROM family_members WHERE id = ?", (member_id,))
        return True


def notify_family(message):
    members = get_family_members()
    group_chats = get_group_chats()
    notified = []

    for m in members:
        if m.get('chat_id') and m.get('notify_enabled'):
            try:
                token = get_setting('telegram_bot_token')
                if token:
                    import requests
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    requests.post(url, json={'chat_id': m['chat_id'], 'text': message}, timeout=5)
                    notified.append(m['name'])
            except:
                pass

    for g in group_chats:
        try:
            token = get_setting('telegram_bot_token')
            if token:
                import requests
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                requests.post(url, json={'chat_id': g['chat_id'], 'text': message}, timeout=5)
                notified.append(f"group_{g['chat_id']}")
        except:
            pass

    return notified


# ========== НОВІ ФУНКЦІЇ ДЛЯ ЦУЦЕНЯТИ ==========

# ----- 1. КАЛЬКУЛЯТОР ЗБИТКІВ -----

def add_damage(item_name, cost, category=None, note=None):
    """Додати запис про знищену річ"""
    with get_db() as conn:
        now = int(time.time())
        conn.execute("""
            INSERT INTO damages (timestamp, item_name, cost, category, note)
            VALUES (?, ?, ?, ?, ?)
        """, (now, item_name, cost, category, note))
        return True


def get_damages(limit=100):
    """Отримати список збитків"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, item_name, cost, category, note,
                   datetime(timestamp, 'unixepoch', 'localtime') as date,
                   timestamp
            FROM damages ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_damages_stats(days=30):
    """Отримати статистику збитків за період"""
    start_time = int(time.time()) - days * 86400
    with get_db() as conn:
        total = conn.execute("""
            SELECT COALESCE(SUM(cost), 0) as total FROM damages 
            WHERE timestamp >= ?
        """, (start_time,)).fetchone()['total']

        by_category = conn.execute("""
            SELECT category, COUNT(*) as count, COALESCE(SUM(cost), 0) as total
            FROM damages WHERE timestamp >= ? AND category IS NOT NULL
            GROUP BY category ORDER BY total DESC
        """, (start_time,)).fetchall()

        last = conn.execute("""
            SELECT item_name, cost, datetime(timestamp, 'unixepoch', 'localtime') as date
            FROM damages ORDER BY timestamp DESC LIMIT 1
        """).fetchone()

        return {
            'total': total,
            'count': len(get_damages(1000)),
            'by_category': [dict(c) for c in by_category],
            'last': dict(last) if last else None
        }


def delete_damage(damage_id):
    """Видалити запис про збиток"""
    with get_db() as conn:
        conn.execute("DELETE FROM damages WHERE id = ?", (damage_id,))
        return True


# ----- 2. КОНТРОЛЬ ВАКЦИНАЦІЙНОГО КАРАНТИНУ -----

def set_last_vaccination(vaccination_date):
    """Встановити дату останнього щеплення"""
    with get_db() as conn:
        date_ts = int(datetime.strptime(vaccination_date, '%Y-%m-%d').timestamp())
        quarantine_days = int(get_setting('quarantine_days', 14))
        end_ts = date_ts + quarantine_days * 86400

        set_setting('last_vaccination_date', vaccination_date)

        conn.execute("DELETE FROM quarantine")
        conn.execute("""
            INSERT INTO quarantine (last_vaccination_date, quarantine_end_date)
            VALUES (?, ?)
        """, (date_ts, end_ts))

        return True


def get_quarantine_status():
    """Отримати статус карантину"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT last_vaccination_date, quarantine_end_date
            FROM quarantine ORDER BY id DESC LIMIT 1
        """).fetchone()

        if not row:
            return {
                'in_quarantine': False,
                'days_left': 0,
                'message': "ℹ️ Щеплення не зареєстровані. Айла може гуляти!"
            }

        now = int(time.time())
        end_date = row['quarantine_end_date']
        last_vaccine_date = row['last_vaccination_date']

        if now >= end_date:
            days_left = 0
            in_quarantine = False
            message = f"✅ Карантин завершено! Айла може гуляти на вулиці."
        else:
            days_left = (end_date - now) // 86400 + 1
            in_quarantine = True
            message = f"🚨 <b>Увага! ВАКЦИНАЦІЙНИЙ КАРАНТИН!</b>\n\nДо кінця карантину ще {days_left} днів.\nГуляти тільки на руках або вдома! Не контактувати з іншими собаками та землею."

        if last_vaccine_date:
            last_date = datetime.fromtimestamp(last_vaccine_date)
            days_since_vaccine = (datetime.now() - last_date).days
            if days_since_vaccine < 14:
                message += f"\n\n💉 Останнє щеплення: {last_date.strftime('%d.%m.%Y')}\n⏳ Пройшло: {days_since_vaccine} днів з 14"

        return {
            'in_quarantine': in_quarantine,
            'days_left': days_left,
            'message': message,
            'end_date': datetime.fromtimestamp(end_date).strftime('%d.%m.%Y') if end_date else None
        }


# ----- 3. ТРЕКЕР ЗУМІСІВ (FRAP) -----

def add_zoomie(duration, intensity=3, note=None):
    """Додати запис про зуміс (раптовий напад енергії)"""
    with get_db() as conn:
        now = int(time.time())
        conn.execute("""
            INSERT INTO zoomies (timestamp, duration, intensity, note)
            VALUES (?, ?, ?, ?)
        """, (now, duration, intensity, note))
        return True


def get_zoomies(limit=50):
    """Отримати список зумісів"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, duration, intensity, note,
                   datetime(timestamp, 'unixepoch', 'localtime') as date,
                   time(timestamp, 'unixepoch', 'localtime') as time_of_day,
                   timestamp
            FROM zoomies ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_zoomies_stats(days=30):
    """Отримати статистику зумісів"""
    start_time = int(time.time()) - days * 86400
    with get_db() as conn:
        count = conn.execute("""
            SELECT COUNT(*) as count FROM zoomies WHERE timestamp >= ?
        """, (start_time,)).fetchone()['count']

        avg_duration = conn.execute("""
            SELECT COALESCE(AVG(duration), 0) as avg_duration FROM zoomies WHERE timestamp >= ?
        """, (start_time,)).fetchone()['avg_duration']

        hour_stats = conn.execute("""
            SELECT strftime('%H', datetime(timestamp, 'unixepoch', 'localtime')) as hour,
                   COUNT(*) as count
            FROM zoomies WHERE timestamp >= ?
            GROUP BY hour ORDER BY count DESC
        """, (start_time,)).fetchall()

        return {
            'count': count,
            'avg_duration': round(avg_duration, 1),
            'hour_stats': [dict(h) for h in hour_stats],
            'peak_hour': hour_stats[0]['hour'] if hour_stats else None
        }


def delete_zoomie(zoomie_id):
    """Видалити запис про зуміс"""
    with get_db() as conn:
        conn.execute("DELETE FROM zoomies WHERE id = ?", (zoomie_id,))
        return True