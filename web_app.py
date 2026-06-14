#!/usr/bin/env python3
"""
Ayla Tracker - Web Dashboard (оновлена версія)
"""

from flask import Flask, jsonify, request, send_from_directory
from datetime import datetime, timedelta
import os
import time
from dotenv import load_dotenv
import requests
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = os.urandom(24)

import database as db

db.init_db()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_HTML = os.path.join(CURRENT_DIR, 'index.html')


@app.route('/')
def index():
    try:
        if os.path.exists(INDEX_HTML):
            with open(INDEX_HTML, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return "<h1>🐾 Ayla Tracker</h1><p>Loading...</p>"
    except Exception as e:
        return f"<h1>Error: {e}</h1>"


@app.route('/<path:filename>')
def serve_static(filename):
    if filename == 'index.html':
        return index()
    return send_from_directory(CURRENT_DIR, filename)


def send_telegram(message, chat_id=None):
    token = db.get_setting('telegram_bot_token', TELEGRAM_BOT_TOKEN)
    target_chat = chat_id or db.get_setting('telegram_chat_id', TELEGRAM_CHAT_ID)
    if not token or not target_chat:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={'chat_id': target_chat, 'text': message, 'parse_mode': 'HTML'}, timeout=10)
        return True
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False


# ========== ОСНОВНІ API ==========

@app.route('/api/stats')
def api_stats():
    try:
        stats = db.get_today_stats()
        return jsonify({
            'feed': stats['feed'],
            'walk_seconds': stats.get('walk_seconds', 0),
            'sleep_seconds': stats.get('sleep_seconds', 0),
            'toilet': stats.get('toilet', 0),
            'behavior': stats.get('behavior', 0),
            'pet_name': db.get_setting('pet_name', 'Айла'),
            'age_months': db.get_pet_age_months()
        })
    except Exception as e:
        return jsonify({'feed': 0, 'walk_seconds': 0, 'sleep_seconds': 0, 'toilet': 0, 'behavior': 0, 'pet_name': 'Айла', 'age_months': 4})


@app.route('/api/timeline')
def api_timeline():
    try:
        offset = request.args.get('offset', 0, type=int)
        target_date = datetime.now() + timedelta(days=offset)
        day_start = int(target_date.replace(hour=0, minute=0, second=0).timestamp())
        day_end = day_start + 86400

        events = db.get_events_for_day(day_start, day_end)

        result = []
        for e in events:
            dt = datetime.fromtimestamp(e['timestamp'])
            result.append({
                'type': e['type'],
                'subtype': e.get('subtype'),
                'start_time': e['timestamp'],
                'hour': dt.hour,
                'minute': dt.minute,
                'duration': e['value'] if e['value'] else 0,
                'time': dt.strftime('%H:%M'),
                'note': e.get('note', '')
            })
        return jsonify({'events': result, 'date': target_date.strftime('%Y-%m-%d')})
    except Exception as e:
        logger.error(f"Timeline error: {e}")
        return jsonify({'events': [], 'date': datetime.now().strftime('%Y-%m-%d')})


@app.route('/api/weekly')
def api_weekly():
    try:
        return jsonify(db.get_weekly_chart_data())
    except Exception as e:
        return jsonify({'dates': [], 'walk': [], 'sleep': []})


@app.route('/api/events')
def api_events():
    try:
        events = db.get_events_list(200)
        for e in events:
            dt = datetime.fromtimestamp(e['timestamp'])
            e['time_str'] = dt.strftime('%d.%m.%Y')
            e['time_hour'] = dt.strftime('%H:%M')
            e['datetime_full'] = dt.strftime('%Y-%m-%dT%H:%M')
        return jsonify(events)
    except Exception as e:
        return jsonify([])


@app.route('/api/event/<int:event_id>', methods=['GET', 'PUT', 'DELETE'])
def api_event(event_id):
    try:
        if request.method == 'GET':
            event = db.get_event_by_id(event_id)
            if event:
                dt = datetime.fromtimestamp(event['timestamp'])
                event['datetime_full'] = dt.strftime('%Y-%m-%dT%H:%M')
                return jsonify(event)
            return jsonify({'error': 'Event not found'}), 404

        elif request.method == 'PUT':
            data = request.get_json()
            new_timestamp = None
            if data.get('datetime'):
                new_timestamp = int(datetime.strptime(data['datetime'], '%Y-%m-%dT%H:%M').timestamp())
            db.update_event(event_id, new_timestamp=new_timestamp, new_type=data.get('type'),
                           new_subtype=data.get('subtype'), new_value=data.get('value'), new_note=data.get('note'))
            return jsonify({'success': True})

        elif request.method == 'DELETE':
            db.delete_event(event_id)
            return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete_event', methods=['POST'])
def api_delete_event():
    try:
        data = request.get_json()
        db.delete_event(data.get('id'))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False})


@app.route('/api/add_event', methods=['POST'])
def api_add_event():
    try:
        data = request.get_json()
        mapping = {
            'feed': ('feed', None, '🍖 Годування'),
            'toilet_pee': ('toilet', 'піся', '💧 Піся'),
            'toilet_poop': ('toilet', 'кака', '💩 Кака')
        }
        if data['type'] == 'behavior':
            db.add_behavior(data.get('subtype', 'Погана поведінка'), 1, data.get('note'))
            return jsonify({'success': True})
        if data['type'] in mapping:
            ev_type, subtype, note = mapping[data['type']]
            db.add_event(ev_type, subtype, note=note)
            return jsonify({'success': True})
        return jsonify({'success': False})
    except Exception as e:
        return jsonify({'success': False})


@app.route('/api/behavior_types')
def api_behavior_types():
    try:
        return jsonify(db.get_behavior_types())
    except Exception as e:
        return jsonify([])


# ========== ПРОГУЛЯНКА ТА СОН ==========

@app.route('/api/walk_status')
def api_walk_status():
    try:
        return jsonify(db.get_active_session('walk'))
    except Exception as e:
        return jsonify({'active': False, 'duration': 0})


@app.route('/api/start_walk', methods=['POST'])
def api_start_walk():
    try:
        safe = db.get_safe_walk_duration_minutes()
        db.start_session('walk', safe)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False})


@app.route('/api/stop_walk', methods=['POST'])
def api_stop_walk():
    try:
        duration = db.stop_session('walk')
        return jsonify({'success': True, 'duration': duration})
    except Exception as e:
        return jsonify({'success': False, 'duration': 0})


@app.route('/api/sleep_status')
def api_sleep_status():
    try:
        return jsonify(db.get_active_session('sleep'))
    except Exception as e:
        return jsonify({'active': False, 'duration': 0})


@app.route('/api/start_sleep', methods=['POST'])
def api_start_sleep():
    try:
        db.start_session('sleep')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False})


@app.route('/api/stop_sleep', methods=['POST'])
def api_stop_sleep():
    try:
        duration = db.stop_session('sleep')
        return jsonify({'success': True, 'duration': duration})
    except Exception as e:
        return jsonify({'success': False, 'duration': 0})


# ========== ВАГА ==========

@app.route('/api/weight')
def api_weight():
    try:
        history = db.get_weight_history(90)
        last = db.get_last_weight()
        daily = db.calculate_daily_food_amount(last or 5)
        return jsonify({
            'dates': [h['date'] for h in history],
            'weights': [h['weight'] for h in history],
            'history': history[::-1][:20],
            'daily_food': daily
        })
    except Exception as e:
        return jsonify({'dates': [], 'weights': [], 'history': [], 'daily_food': 200})


@app.route('/api/weight/<int:weight_id>', methods=['PUT', 'DELETE'])
def api_update_weight(weight_id):
    try:
        if request.method == 'PUT':
            data = request.get_json()
            new_timestamp = None
            if data.get('datetime'):
                new_timestamp = int(datetime.strptime(data['datetime'], '%Y-%m-%dT%H:%M').timestamp())
            db.update_weight_log(weight_id, data['weight'], new_timestamp)
            return jsonify({'success': True})
        elif request.method == 'DELETE':
            db.delete_weight_log(weight_id)
            return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/add_weight', methods=['POST'])
def api_add_weight():
    try:
        data = request.get_json()
        db.add_weight(data['weight'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False})


# ========== ТРЕНУВАННЯ ==========

@app.route('/api/training')
def api_training():
    try:
        stats = db.get_training_stats()
        history = db.get_training_history(50)
        types = db.get_training_types()
        return jsonify({
            'commands': [s['command'] for s in stats],
            'scores': [s['avg_success'] for s in stats],
            'history': history,
            'types': types
        })
    except Exception as e:
        return jsonify({'commands': [], 'scores': [], 'history': [], 'types': []})


@app.route('/api/training/<int:training_id>', methods=['PUT', 'DELETE'])
def api_update_training(training_id):
    try:
        if request.method == 'PUT':
            data = request.get_json()
            new_timestamp = None
            if data.get('datetime'):
                new_timestamp = int(datetime.strptime(data['datetime'], '%Y-%m-%dT%H:%M').timestamp())
            db.update_training_log(training_id, new_command=data.get('command'), new_duration=data.get('duration'),
                                   new_success_rate=data.get('success_rate'), new_timestamp=new_timestamp)
            return jsonify({'success': True})
        elif request.method == 'DELETE':
            db.delete_training_log(training_id)
            return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/add_training', methods=['POST'])
def api_add_training():
    try:
        data = request.get_json()
        db.add_training(data['command'], data.get('duration', 10), data['success_rate'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False})


@app.route('/api/training_types', methods=['GET', 'POST'])
def api_training_types():
    try:
        if request.method == 'POST':
            data = request.get_json()
            db.add_training_type(data['name'], data.get('icon', '🏋️'))
            return jsonify({'success': True})
        return jsonify(db.get_training_types())
    except Exception as e:
        return jsonify([])


# ========== МЕНТАЛЬНА АКТИВНІСТЬ ==========

@app.route('/api/mental')
def api_mental():
    try:
        activities = db.get_mental_activities(50)
        stats = db.get_mental_stats(7)
        types = db.get_mental_types()
        potty = db.get_potty_stats()
        avg = sum(m['duration'] for m in stats) / 7 if stats else 0
        return jsonify({
            'dates': [m['date'] for m in stats],
            'durations': [m['duration'] for m in stats],
            'activities': activities,
            'types': types,
            'potty_types': [p['type'] for p in potty],
            'potty_counts': [p['count'] for p in potty],
            'avg_mental': round(avg, 1)
        })
    except Exception as e:
        return jsonify({'dates': [], 'durations': [], 'activities': [], 'types': [], 'potty_types': [], 'potty_counts': [], 'avg_mental': 0})


@app.route('/api/mental/<int:activity_id>', methods=['PUT', 'DELETE'])
def api_update_mental(activity_id):
    try:
        if request.method == 'PUT':
            data = request.get_json()
            new_timestamp = None
            if data.get('datetime'):
                new_timestamp = int(datetime.strptime(data['datetime'], '%Y-%m-%dT%H:%M').timestamp())
            db.update_mental_activity(activity_id, new_activity_type=data.get('activity_type'),
                                      new_duration=data.get('duration'), new_timestamp=new_timestamp)
            return jsonify({'success': True})
        elif request.method == 'DELETE':
            db.delete_mental_activity(activity_id)
            return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/add_mental', methods=['POST'])
def api_add_mental():
    try:
        data = request.get_json()
        db.add_mental_activity(data['activity_type'], data['duration'], data.get('difficulty', 3))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False})


@app.route('/api/mental_types', methods=['GET', 'POST'])
def api_mental_types():
    try:
        if request.method == 'POST':
            data = request.get_json()
            db.add_mental_type(data['name'], data.get('icon', '🧠'))
            return jsonify({'success': True})
        return jsonify(db.get_mental_types())
    except Exception as e:
        return jsonify([])


# ========== ЗДОРОВ'Я ==========

@app.route('/api/health')
def api_health():
    try:
        reminders = db.get_medical_reminders()
        due_reminders = db.get_due_medical_reminders()
        return jsonify({
            'reminders': reminders,
            'due_reminders': due_reminders,
            'symptoms': db.get_symptoms(),
            'allergies': db.get_allergies()
        })
    except Exception as e:
        return jsonify({'reminders': [], 'due_reminders': [], 'symptoms': [], 'allergies': []})


@app.route('/api/add_reminder', methods=['POST'])
def api_add_reminder():
    try:
        data = request.get_json()
        if not data or not data.get('title') or not data.get('interval_days'):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        interval = int(data['interval_days'])
        if interval <= 0:
            return jsonify({'success': False, 'error': 'interval_days must be positive'})
        db.add_medical_reminder(data['title'], data.get('description', ''), interval, data.get('reminder_time', '09:00'))
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Add reminder error: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/complete_reminder', methods=['POST'])
def api_complete_reminder():
    try:
        data = request.get_json()
        db.complete_reminder(data['id'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False})


@app.route('/api/delete_reminder', methods=['POST'])
def api_delete_reminder():
    try:
        data = request.get_json()
        db.delete_reminder(data['id'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False})


@app.route('/api/add_symptom', methods=['POST'])
def api_add_symptom():
    try:
        data = request.get_json()
        db.add_symptom(data.get('temperature'), data.get('appetite'), data.get('mood'), data.get('note'))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False})


@app.route('/api/delete_symptom', methods=['POST'])
def api_delete_symptom():
    try:
        data = request.get_json()
        db.delete_symptom(data['id'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False})


@app.route('/api/add_allergy', methods=['POST'])
def api_add_allergy():
    try:
        data = request.get_json()
        db.add_allergy(data['product'], data.get('reaction', ''), data.get('severity', 3))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False})


@app.route('/api/delete_allergy', methods=['POST'])
def api_delete_allergy():
    try:
        data = request.get_json()
        db.delete_allergy(data['id'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False})


# ========== ПРОПОРЦІЇ ==========

@app.route('/api/measurements')
def api_measurements():
    try:
        measurements = db.get_body_measurements(50)
        return jsonify({'measurements': measurements})
    except Exception as e:
        return jsonify({'measurements': []})


@app.route('/api/measurements', methods=['POST'])
def api_add_measurement():
    try:
        data = request.get_json()
        db.add_body_measurement(neck_cm=data.get('neck_cm'), chest_cm=data.get('chest_cm'),
                                waist_cm=data.get('waist_cm'), length_cm=data.get('length_cm'),
                                height_cm=data.get('height_cm'), note=data.get('note'))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False})


@app.route('/api/measurements/<int:measurement_id>', methods=['PUT', 'DELETE'])
def api_update_measurement(measurement_id):
    try:
        if request.method == 'PUT':
            data = request.get_json()
            new_timestamp = None
            if data.get('datetime'):
                new_timestamp = int(datetime.strptime(data['datetime'], '%Y-%m-%dT%H:%M').timestamp())
            db.update_body_measurement(measurement_id, neck_cm=data.get('neck_cm'), chest_cm=data.get('chest_cm'),
                                       waist_cm=data.get('waist_cm'), length_cm=data.get('length_cm'),
                                       height_cm=data.get('height_cm'), note=data.get('note'), new_timestamp=new_timestamp)
            return jsonify({'success': True})
        elif request.method == 'DELETE':
            db.delete_body_measurement(measurement_id)
            return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== ЗВІТИ ==========

@app.route('/api/report')
def api_report():
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        events = db.get_events_by_date_range(today, today)
        return jsonify({
            'date': today,
            'feed': len([e for e in events if e['type'] == 'feed']),
            'walk_minutes': sum([e['value'] for e in events if e['type'] == 'walk']) // 60,
            'toilet': len([e for e in events if e['type'] == 'toilet']),
            'sleep_hours': sum([e['value'] for e in events if e['type'] == 'sleep']) // 3600,
            'behavior': len([e for e in events if e['type'] == 'behavior']),
            'mental': len([e for e in events if e['type'] == 'mental']),
            'training': len([e for e in events if e['type'] == 'training'])
        })
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/report/week')
def api_report_week():
    try:
        return jsonify(db.get_full_report(7))
    except Exception as e:
        return jsonify({'days': 7, 'feed': 0, 'walk_seconds': 0, 'toilet': 0, 'sleep_seconds': 0,
                        'mental_minutes': 0, 'training_count': 0, 'training_avg': 0, 'behavior': 0})


@app.route('/api/send_report', methods=['POST'])
def api_send_report():
    try:
        report = db.get_full_report(7)
        msg = f"🐾 <b>Звіт Айли за тиждень</b>\n\n📊 Статистика:\n🍖 Годувань: {report['feed']}\n🚶 Прогулянок: {report['walk_minutes']} хв\n😴 Сну: {report['sleep_hours']} год\n🚽 Туалет: {report['toilet']}\n⚠️ Поведінка: {report['behavior']}\n🧠 Ментальне: {report['mental_minutes']} хв\n🏋️ Тренувань: {report['training_count']} (усп. {report['training_avg']}/5)"
        send_telegram(msg)
        for group in db.get_group_chats():
            send_telegram(msg, group['chat_id'])
        return jsonify({'message': '✅ Звіт надіслано!'})
    except Exception as e:
        return jsonify({'message': '❌ Помилка'})


@app.route('/api/send_daily_report', methods=['POST'])
def api_send_daily_report():
    try:
        data = request.get_json()
        date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
        events = db.get_events_by_date_range(date, date)
        msg = f"📅 <b>Звіт за {date}</b>\n\n🍖 Годувань: {len([e for e in events if e['type'] == 'feed'])}\n🚶 Прогулянок: {sum([e['value'] for e in events if e['type'] == 'walk']) // 60} хв\n😴 Сну: {sum([e['value'] for e in events if e['type'] == 'sleep']) // 3600} год\n🚽 Туалет: {len([e for e in events if e['type'] == 'toilet'])}\n⚠️ Поведінка: {len([e for e in events if e['type'] == 'behavior'])}"
        send_telegram(msg, data.get('chat_id'))
        return jsonify({'message': '✅ Звіт надіслано!'})
    except Exception as e:
        return jsonify({'message': '❌ Помилка'})


# ========== ІНШІ API ==========

@app.route('/api/insight')
def api_insight():
    try:
        stats = db.get_today_stats()
        safe = db.get_safe_walk_duration_minutes()
        settings = db.get_settings()
        planned_meals = int(settings.get('planned_meals', 4))
        feed_percent = int((stats['feed'] / planned_meals) * 100) if planned_meals > 0 else 0
        insight = f"📊 Прогрес: {stats['feed']}/{planned_meals} годів ({feed_percent}%), {stats['walk_minutes']} хв прогулянок."
        if stats['walk_minutes'] > safe:
            insight += f" ⚠️ Ліміт прогулянки {safe} хв."
        return jsonify({'insight': insight})
    except Exception as e:
        return jsonify({'insight': '🐾 Вітаємо! Система працює.'})


@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    try:
        return jsonify(db.get_settings())
    except Exception as e:
        return jsonify({})


@app.route('/api/settings', methods=['POST'])
def api_save_settings():
    try:
        data = request.get_json()
        for key, value in data.items():
            if value is not None:
                db.set_setting(key, str(value))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False})


@app.route('/api/test_telegram', methods=['POST'])
def api_test_telegram():
    try:
        data = request.get_json()
        token = data.get('bot_token')
        chat_id = data.get('chat_id')
        if not token or not chat_id:
            return jsonify({'message': '❌ Введіть Bot Token та Chat ID'})
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        response = requests.post(url, json={'chat_id': chat_id, 'text': '🐾 Тестове повідомлення від Ayla Tracker! ✅'}, timeout=10)
        if response.status_code == 200:
            db.set_setting('telegram_bot_token', token)
            db.set_setting('telegram_chat_id', chat_id)
            return jsonify({'message': '✅ Telegram налаштовано успішно!'})
        return jsonify({'message': f'❌ Помилка: {response.text}'})
    except Exception as e:
        return jsonify({'message': f'❌ Помилка: {str(e)}'})


# ========== ВЕТПАСПОРТ ТА СІМ'Я ==========

@app.route('/api/vaccinations', methods=['GET', 'POST'])
def api_vaccinations():
    try:
        if request.method == 'POST':
            data = request.get_json()
            db.add_vaccination(data['vaccine_name'], data['vaccine_date'], data.get('next_due'),
                              data.get('series'), data.get('vet_name'), data.get('clinic_name'), data.get('notes'))
            return jsonify({'success': True})
        return jsonify(db.get_vaccinations())
    except Exception as e:
        return jsonify([])


@app.route('/api/parasite_treatments', methods=['GET', 'POST'])
def api_parasite_treatments():
    try:
        if request.method == 'POST':
            data = request.get_json()
            db.add_parasite_treatment(data['name'], data['treatment_date'], data.get('next_due'),
                                     data.get('parasite_type'), data.get('medication'), data.get('dosage'), data.get('notes'))
            return jsonify({'success': True})
        return jsonify(db.get_parasite_treatments())
    except Exception as e:
        return jsonify([])


@app.route('/api/dental_history', methods=['GET', 'POST'])
def api_dental_history():
    try:
        if request.method == 'POST':
            data = request.get_json()
            db.add_dental_procedure(data['procedure_date'], data['procedure_type'], data.get('vet_name'),
                                   data.get('notes'), data.get('next_due'))
            return jsonify({'success': True})
        return jsonify(db.get_dental_history())
    except Exception as e:
        return jsonify([])


@app.route('/api/family_members', methods=['GET', 'POST', 'DELETE'])
def api_family_members():
    try:
        if request.method == 'POST':
            data = request.get_json()
            db.add_family_member(data['name'], data.get('role', 'member'), data.get('chat_id'), data.get('notify', True))
            return jsonify({'success': True})
        elif request.method == 'DELETE':
            data = request.get_json()
            db.delete_family_member(data['id'])
            return jsonify({'success': True})
        return jsonify(db.get_family_members())
    except Exception as e:
        return jsonify([])


@app.route('/api/notify_family', methods=['POST'])
def api_notify_family():
    try:
        data = request.get_json()
        notified = db.notify_family(data['message'])
        return jsonify({'notified': notified})
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/group_chats', methods=['GET', 'POST'])
def api_group_chats():
    try:
        if request.method == 'POST':
            data = request.get_json()
            db.add_group_chat(data['chat_id'], data.get('title'))
            return jsonify({'success': True})
        return jsonify(db.get_group_chats())
    except Exception as e:
        return jsonify([])


def run_web():
    port = int(os.getenv('WEB_PORT', 5010))
    print(f"🌐 Веб-сервер: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)


if __name__ == '__main__':
    run_web()