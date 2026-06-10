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


def init_db():
    """Ініціалізація бази даних"""
    with get_db() as conn:
        # Перевіряємо чи існує таблиця active_sessions з правильною структурою
        conn.execute("DROP TABLE IF EXISTS active_sessions")

        conn.executescript('''
            -- Таблиця подій
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                type TEXT NOT NULL,
                subtype TEXT,
                value INTEGER,
                note TEXT,
                user_id INTEGER
            );

            -- Активні сесії (перестворюємо з правильною структурою)
            CREATE TABLE IF NOT EXISTS active_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_type TEXT NOT NULL,
                start_time INTEGER NOT NULL,
                expected_duration INTEGER DEFAULT 0,
                note TEXT
            );

            -- Вага
            CREATE TABLE IF NOT EXISTS weight_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                weight REAL NOT NULL,
                note TEXT,
                user_id INTEGER
            );

            -- Тренування
            CREATE TABLE IF NOT EXISTS training_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                command TEXT NOT NULL,
                duration INTEGER,
                success_rate INTEGER,
                note TEXT,
                user_id INTEGER
            );

            -- Ментальні активності
            CREATE TABLE IF NOT EXISTS mental_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                activity_type TEXT NOT NULL,
                duration INTEGER,
                difficulty INTEGER,
                note TEXT,
                user_id INTEGER
            );

            -- Медичні нагадування
            CREATE TABLE IF NOT EXISTS medical_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                last_done INTEGER,
                next_due INTEGER NOT NULL,
                interval_days INTEGER NOT NULL,
                enabled INTEGER DEFAULT 1,
                user_id INTEGER
            );

            -- Симптоми
            CREATE TABLE IF NOT EXISTS symptoms_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                temperature REAL,
                appetite INTEGER,
                mood TEXT,
                note TEXT,
                user_id INTEGER
            );

            -- Ветеринарні клініки
            CREATE TABLE IF NOT EXISTS vet_clinics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                address TEXT,
                phone TEXT,
                website TEXT,
                note TEXT
            );

            -- Їжа
            CREATE TABLE IF NOT EXISTS food_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                food_type TEXT NOT NULL,
                amount REAL,
                brand TEXT,
                note TEXT,
                user_id INTEGER
            );

            -- Алергії
            CREATE TABLE IF NOT EXISTS allergies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product TEXT NOT NULL,
                reaction TEXT,
                severity INTEGER,
                note TEXT
            );

            -- Щоденник
            CREATE TABLE IF NOT EXISTS diary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                content TEXT NOT NULL,
                user_id INTEGER
            );

            -- Маркери туалету
            CREATE TABLE IF NOT EXISTS potty_cues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                cue_type TEXT NOT NULL,
                success INTEGER DEFAULT 0,
                note TEXT
            );

            -- Тригери
            CREATE TABLE IF NOT EXISTS trigger_exposures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                trigger_type TEXT NOT NULL,
                reaction_score INTEGER,
                note TEXT
            );

            -- Користувачі
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

            -- Налаштування
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            );
        ''')

        # Ініціалізація налаштувань
        defaults = {
            "pet_name": "Айла",
            "birth_date": "",
            "target_weight": "8.0",
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            "food_density_calories": "3800",
            "potty_reminder_minutes": "25"
        }
        for key, value in defaults.items():
            conn.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, value))

        print("✅ База даних ініціалізована")


def get_setting(key, default=None):
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row['value'] if row else default


def set_setting(key, value):
    with get_db() as conn:
        conn.execute('INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)',
                     (key, value, int(time.time())))


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
    return months * 5


def calculate_daily_food_amount(weight_kg):
    if not weight_kg:
        weight_kg = 5
    calories_needed = weight_kg * 200
    food_density = float(get_setting('food_density_calories', 3800))
    daily_grams = (calories_needed / food_density) * 1000
    return max(50, min(400, int(daily_grams)))


def add_event(event_type, subtype=None, value=None, note=None, user_id=None):
    with get_db() as conn:
        now = int(time.time())
        conn.execute("""
            INSERT INTO events (timestamp, type, subtype, value, note, user_id) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (now, event_type, subtype, value, note, user_id))
        return True


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
        feed = conn.execute("SELECT COUNT(*) FROM events WHERE type='feed' AND timestamp >= ?", (today_start,)).fetchone()[0]
        walk = conn.execute("SELECT SUM(value) FROM events WHERE type='walk' AND timestamp >= ?", (today_start,)).fetchone()[0] or 0
        toilet = conn.execute("SELECT COUNT(*) FROM events WHERE type='toilet' AND timestamp >= ?", (today_start,)).fetchone()[0]
        sleep = conn.execute("SELECT SUM(value) FROM events WHERE type='sleep' AND timestamp >= ?", (today_start,)).fetchone()[0] or 0
        return {
            'feed': feed,
            'walk_minutes': walk // 60,
            'walk_seconds': walk,
            'sleep_hours': sleep // 3600,
            'sleep_seconds': sleep,
            'toilet': toilet
        }


def get_settings():
    """Отримання всіх налаштувань"""
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        settings = {}
        for row in rows:
            settings[row['key']] = row['value']

        # Значення за замовчуванням
        defaults = {
            'pet_name': 'Айла',
            'birth_date': '',
            'food_density_calories': '3800',
            'planned_meals': '4',
            'planned_sleep_hours': '14',
            'target_weight': '8.0',
            'telegram_bot_token': '',
            'telegram_chat_id': '',
            'potty_reminder_minutes': '25'
        }

        for key, default in defaults.items():
            if key not in settings:
                settings[key] = default

        return settings

def get_events_list(limit=50):
    with get_db() as conn:
        events = conn.execute("""
            SELECT id, type, subtype, timestamp, value, note,
                   datetime(timestamp, 'unixepoch', 'localtime') as time_str
            FROM events ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
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


def get_last_weight():
    with get_db() as conn:
        row = conn.execute("SELECT weight FROM weight_logs ORDER BY timestamp DESC LIMIT 1").fetchone()
        return row['weight'] if row else None


def get_weight_history(days=90):
    start_time = int(time.time()) - days * 86400
    with get_db() as conn:
        rows = conn.execute("""
            SELECT datetime(timestamp, 'unixepoch', 'localtime') as date, weight
            FROM weight_logs WHERE timestamp >= ? ORDER BY timestamp
        """, (start_time,)).fetchall()
        return [{'date': r['date'], 'weight': r['weight']} for r in rows]


def add_training(command, duration, success_rate):
    with get_db() as conn:
        now = int(time.time())
        conn.execute("""
            INSERT INTO training_logs (timestamp, command, duration, success_rate)
            VALUES (?, ?, ?, ?)
        """, (now, command, duration, success_rate))
        return True


def get_training_stats():
    with get_db() as conn:
        stats = conn.execute("""
            SELECT command, COUNT(*) as count, AVG(success_rate) as avg_success
            FROM training_logs GROUP BY command
        """).fetchall()
        return [{'command': r['command'], 'count': r['count'], 'avg_success': round(r['avg_success'], 1)} for r in
                stats]


def get_training_history(limit=30):
    with get_db() as conn:
        history = conn.execute("""
            SELECT datetime(timestamp, 'unixepoch', 'localtime') as date,
                   command, duration, success_rate
            FROM training_logs ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [
            {'date': r['date'], 'command': r['command'], 'duration': r['duration'], 'success_rate': r['success_rate']}
            for r in history]


def add_mental_activity(activity_type, duration, difficulty=3):
    with get_db() as conn:
        now = int(time.time())
        conn.execute("""
            INSERT INTO mental_activities (timestamp, activity_type, duration, difficulty)
            VALUES (?, ?, ?, ?)
        """, (now, activity_type, duration, difficulty))
        return True


def get_mental_stats(days=7):
    start_time = int(time.time()) - days * 86400
    with get_db() as conn:
        rows = conn.execute("""
            SELECT date(timestamp, 'unixepoch') as date, SUM(duration) as total
            FROM mental_activities WHERE timestamp >= ? GROUP BY date ORDER BY date
        """, (start_time,)).fetchall()
        return [{'date': r['date'], 'duration': r['total']} for r in rows]


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


def add_medical_reminder(title, description, interval_days):
    with get_db() as conn:
        now = int(time.time())
        conn.execute("""
            INSERT INTO medical_reminders (title, description, interval_days, last_done, next_due, enabled)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (title, description, interval_days, now, now + interval_days * 86400))
        return True


def get_medical_reminders():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM medical_reminders WHERE enabled = 1 ORDER BY next_due ASC
        """).fetchall()
        reminders = []
        for r in rows:
            rem = dict(r)
            rem['next_due_str'] = datetime.fromtimestamp(rem['next_due']).strftime('%d.%m.%Y')
            reminders.append(rem)
        return reminders


def complete_reminder(reminder_id):
    with get_db() as conn:
        row = conn.execute("SELECT interval_days FROM medical_reminders WHERE id = ?", (reminder_id,)).fetchone()
        if row:
            now = int(time.time())
            conn.execute("""
                UPDATE medical_reminders SET last_done = ?, next_due = ? WHERE id = ?
            """, (now, now + row['interval_days'] * 86400, reminder_id))
            return True
    return False


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
            SELECT datetime(timestamp, 'unixepoch', 'localtime') as date,
                   temperature, appetite, mood, note
            FROM symptoms_log ORDER BY timestamp DESC LIMIT 20
        """).fetchall()
        return [dict(r) for r in rows]


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


def get_full_report(days=7):
    start_time = int(time.time()) - days * 86400
    with get_db() as conn:
        feed = \
        conn.execute("SELECT COUNT(*) FROM events WHERE type='feed' AND timestamp >= ?", (start_time,)).fetchone()[0]
        walk = \
        conn.execute("SELECT SUM(value) FROM events WHERE type='walk' AND timestamp >= ?", (start_time,)).fetchone()[
            0] or 0
        toilet = \
        conn.execute("SELECT COUNT(*) FROM events WHERE type='toilet' AND timestamp >= ?", (start_time,)).fetchone()[0]
        sleep = \
        conn.execute("SELECT SUM(value) FROM events WHERE type='sleep' AND timestamp >= ?", (start_time,)).fetchone()[
            0] or 0
        mental = \
        conn.execute("SELECT SUM(duration) FROM mental_activities WHERE timestamp >= ?", (start_time,)).fetchone()[
            0] or 0
        training_count = \
        conn.execute("SELECT COUNT(*) FROM training_logs WHERE timestamp >= ?", (start_time,)).fetchone()[0]
        training_avg = \
        conn.execute("SELECT AVG(success_rate) FROM training_logs WHERE timestamp >= ?", (start_time,)).fetchone()[
            0] or 0

        return {
            'days': days,
            'feed': feed,
            'walk_minutes': walk // 60,
            'toilet': toilet,
            'sleep_hours': sleep // 3600,
            'mental_minutes': mental,
            'training_count': training_count,
            'training_avg': round(training_avg, 1)
        }


def get_weekly_chart_data():
    start_time = int(time.time()) - 7 * 86400
    with get_db() as conn:
        walk_data = conn.execute("""
            SELECT date(timestamp, 'unixepoch') as date, SUM(value)/60 as total
            FROM events WHERE type='walk' AND timestamp >= ? 
            GROUP BY date ORDER BY date
        """, (start_time,)).fetchall()

        sleep_data = conn.execute("""
            SELECT date(timestamp, 'unixepoch') as date, SUM(value)/3600 as total
            FROM events WHERE type='sleep' AND timestamp >= ? 
            GROUP BY date ORDER BY date
        """, (start_time,)).fetchall()

        mental_data = conn.execute("""
            SELECT date(timestamp, 'unixepoch') as date, SUM(duration) as total
            FROM mental_activities WHERE timestamp >= ? 
            GROUP BY date ORDER BY date
        """, (start_time,)).fetchall()

    dates = [d['date'] for d in walk_data]
    return {
        'dates': dates,
        'walk': [d['total'] for d in walk_data],
        'sleep': [d['total'] for d in sleep_data],
        'mental': [d['total'] for d in mental_data]
    }


def add_user(chat_id, username=None, first_name=None, last_name=None):
    with get_db() as conn:
        now = int(time.time())
        conn.execute("""
            INSERT OR IGNORE INTO allowed_users (chat_id, username, first_name, last_name, added_at, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (chat_id, username, first_name, last_name, now))
        return True

def get_events_for_day(start_timestamp, end_timestamp):
    """Отримання подій за конкретний день"""
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
        return row is not None