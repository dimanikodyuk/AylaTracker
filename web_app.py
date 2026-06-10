#!/usr/bin/env python3
"""
Ayla Tracker - Web Dashboard
"""

from flask import Flask, render_template, jsonify, request
from datetime import datetime, timedelta
import os
import time
import csv
from io import StringIO
from dotenv import load_dotenv
import requests

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

import database as db

db.init_db()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')


def send_telegram(message):
    token = db.get_setting('telegram_bot_token', TELEGRAM_BOT_TOKEN)
    chat_id = db.get_setting('telegram_chat_id', TELEGRAM_CHAT_ID)
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}, timeout=10)
        return True
    except:
        return False


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/stats')
def api_stats():
    stats = db.get_today_stats()
    return jsonify({
        'feed': stats['feed'],
        'walk_seconds': stats['walk_seconds'],
        'sleep_seconds': stats['sleep_seconds'],
        'toilet': stats['toilet'],
        'pet_name': db.get_setting('pet_name', 'Айла'),
        'age_months': db.get_pet_age_months()
    })


@app.route('/api/timeline')
def api_timeline():
    offset = request.args.get('offset', 0, type=int)
    target_date = datetime.now() + timedelta(days=offset)
    day_start = int(target_date.replace(hour=0, minute=0, second=0).timestamp())
    day_end = day_start + 86400

    events = db.get_events_for_day(day_start, day_end)

    result = []
    for e in events:
        result.append({
            'type': e['type'],
            'subtype': e.get('subtype'),
            'start_time': e['timestamp'],
            'duration': e['value'] if e['value'] else 0,
            'time': datetime.fromtimestamp(e['timestamp']).strftime('%H:%M'),
            'note': e['note']
        })
    return jsonify({'events': result, 'date': target_date.strftime('%Y-%m-%d')})


@app.route('/api/weekly')
def api_weekly():
    return jsonify(db.get_weekly_chart_data())


@app.route('/api/events')
def api_events():
    events = db.get_events_list(100)
    for e in events:
        dt = datetime.fromtimestamp(e['timestamp'])
        e['time_str'] = dt.strftime('%d.%m')
        e['time_hour'] = dt.strftime('%H:%M')
        e['note'] = e['subtype'] or e['type']
    return jsonify(events)


@app.route('/api/delete_event', methods=['POST'])
def api_delete_event():
    data = request.get_json()
    db.delete_event(data.get('id'))
    return jsonify({'success': True})


@app.route('/api/add_event', methods=['POST'])
def api_add_event():
    data = request.get_json()
    mapping = {
        'feed': ('feed', None, '🍖 Годування'),
        'toilet_pee': ('toilet', 'піся', '💧 Піся'),
        'toilet_poop': ('toilet', 'кака', '💩 Кака')
    }
    if data['type'] in mapping:
        ev_type, subtype, note = mapping[data['type']]
        db.add_event(ev_type, subtype, note=note)
        return jsonify({'success': True})
    return jsonify({'success': False})


@app.route('/api/walk_status')
def api_walk_status():
    return jsonify(db.get_active_session('walk'))


@app.route('/api/start_walk', methods=['POST'])
def api_start_walk():
    safe = db.get_safe_walk_duration_minutes()
    db.start_session('walk', safe)
    return jsonify({'success': True})


@app.route('/api/stop_walk', methods=['POST'])
def api_stop_walk():
    duration = db.stop_session('walk')
    return jsonify({'success': True, 'duration': duration})


@app.route('/api/sleep_status')
def api_sleep_status():
    return jsonify(db.get_active_session('sleep'))


@app.route('/api/start_sleep', methods=['POST'])
def api_start_sleep():
    db.start_session('sleep')
    return jsonify({'success': True})


@app.route('/api/stop_sleep', methods=['POST'])
def api_stop_sleep():
    duration = db.stop_session('sleep')
    return jsonify({'success': True, 'duration': duration})


@app.route('/api/weight')
def api_weight():
    history = db.get_weight_history(90)
    last = db.get_last_weight()
    daily = db.calculate_daily_food_amount(last or 5)
    return jsonify({
        'dates': [h['date'] for h in history],
        'weights': [h['weight'] for h in history],
        'history': history[::-1][:10],
        'daily_food': daily
    })


@app.route('/api/add_weight', methods=['POST'])
def api_add_weight():
    data = request.get_json()
    db.add_weight(data['weight'])
    return jsonify({'success': True})


@app.route('/api/training')
def api_training():
    stats = db.get_training_stats()
    history = db.get_training_history(30)
    return jsonify({
        'commands': [s['command'] for s in stats],
        'scores': [s['avg_success'] for s in stats],
        'history': history
    })


@app.route('/api/add_training', methods=['POST'])
def api_add_training():
    data = request.get_json()
    db.add_training(data['command'], data.get('duration', 10), data['success_rate'])
    return jsonify({'success': True})


@app.route('/api/mental')
def api_mental():
    mental = db.get_mental_stats(7)
    potty = db.get_potty_stats()
    avg = sum(m['duration'] for m in mental) / 7 if mental else 0
    return jsonify({
        'dates': [m['date'] for m in mental],
        'durations': [m['duration'] for m in mental],
        'potty_types': [p['type'] for p in potty],
        'potty_counts': [p['count'] for p in potty],
        'avg_mental': round(avg, 1)
    })


@app.route('/api/add_mental', methods=['POST'])
def api_add_mental():
    data = request.get_json()
    db.add_mental_activity(data['activity_type'], data['duration'], data.get('difficulty', 3))
    return jsonify({'success': True})


@app.route('/api/health')
def api_health():
    reminders = db.get_medical_reminders()
    # Фільтруємо тільки реальні нагадування
    reminders = [r for r in reminders if r.get('title') and not r['title'].startswith('Тест')][:10]
    return jsonify({
        'reminders': reminders,
        'symptoms': db.get_symptoms(),
        'allergies': db.get_allergies()
    })


@app.route('/api/add_reminder', methods=['POST'])
def api_add_reminder():
    data = request.get_json()
    db.add_medical_reminder(data['title'], data.get('description', ''), data['interval_days'])
    return jsonify({'success': True})


@app.route('/api/complete_reminder', methods=['POST'])
def api_complete_reminder():
    data = request.get_json()
    db.complete_reminder(data['id'])
    return jsonify({'success': True})


@app.route('/api/add_symptom', methods=['POST'])
def api_add_symptom():
    data = request.get_json()
    db.add_symptom(data.get('temperature'), data.get('appetite'), data.get('mood'), data.get('note'))
    return jsonify({'success': True})


@app.route('/api/add_allergy', methods=['POST'])
def api_add_allergy():
    data = request.get_json()
    db.add_allergy(data['product'], data.get('reaction', ''), data.get('severity', 3))
    return jsonify({'success': True})


@app.route('/api/delete_allergy', methods=['POST'])
def api_delete_allergy():
    data = request.get_json()
    db.delete_allergy(data['id'])
    return jsonify({'success': True})


@app.route('/api/report')
def api_report():
    return jsonify(db.get_full_report(7))


@app.route('/api/send_report')
def api_send_report():
    report = db.get_full_report(7)
    msg = f"🐾 <b>Звіт Айли за тиждень</b>\n\n📊 Статистика:\n🍖 Годувань: {report['feed']}\n🚶 Прогулянок: {report['walk_minutes']} хв\n😴 Сну: {report['sleep_hours']} год\n🚽 Туалет: {report['toilet']}\n🧠 Ментальне: {report['mental_minutes']} хв\n🏋️ Тренувань: {report['training_count']} (усп. {report['training_avg']}/5)"
    if send_telegram(msg):
        return jsonify({'message': '✅ Звіт надіслано!'})
    return jsonify({'message': '❌ Помилка Telegram'})


@app.route('/api/insight')
def api_insight():
    stats = db.get_today_stats()
    safe = db.get_safe_walk_duration_minutes()
    last = db.get_last_weight()
    settings = db.get_settings()

    # Розрахунок виконання плану годувань
    planned_meals = settings.get('planned_meals', 4)
    feed_progress = stats['feed']
    feed_percent = int((feed_progress / planned_meals) * 100) if planned_meals > 0 else 0

    # Розрахунок плану сну
    planned_sleep_hours = settings.get('planned_sleep_hours', 14)
    sleep_hours = stats['sleep_seconds'] / 3600
    sleep_percent = int((sleep_hours / planned_sleep_hours) * 100) if planned_sleep_hours > 0 else 0

    insight = f"🐾 Сьогодні: {stats['feed']}/{planned_meals} годів ({feed_percent}%), {stats['walk_minutes']} хв прогулянок."

    if stats['walk_minutes'] > safe:
        insight += f" ⚠️ Прогулянка перевищує безпечний ліміт ({safe} хв)."

    if feed_progress < planned_meals:
        insight += f" 📊 Залишилося годувань: {planned_meals - feed_progress}"

    if sleep_hours < planned_sleep_hours:
        insight += f" 😴 Айла спала {sleep_hours:.1f} год з {planned_sleep_hours} год."

    if last:
        insight += f" 🍖 Рекомендована порція: {db.calculate_daily_food_amount(last)} г/день."

    return jsonify({'insight': insight})


@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    return jsonify(db.get_settings())


@app.route('/api/settings', methods=['POST'])
def api_save_settings():
    data = request.get_json()
    for key, value in data.items():
        if value is not None:
            db.set_setting(key, str(value))
    return jsonify({'success': True})


@app.route('/api/test_telegram', methods=['POST'])
def api_test_telegram():
    data = request.get_json()
    token = data.get('bot_token')
    chat_id = data.get('chat_id')

    if not token or not chat_id:
        return jsonify({'message': '❌ Введіть Bot Token та Chat ID'})

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        response = requests.post(url, json={
            'chat_id': chat_id,
            'text': '🐾 Тестове повідомлення від Ayla Tracker! ✅'
        }, timeout=10)

        if response.status_code == 200:
            db.set_setting('telegram_bot_token', token)
            db.set_setting('telegram_chat_id', chat_id)
            return jsonify({'message': '✅ Telegram налаштовано успішно!'})
        else:
            return jsonify({'message': f'❌ Помилка: {response.text}'})
    except Exception as e:
        return jsonify({'message': f'❌ Помилка: {str(e)}'})


def run_web():
    port = int(os.getenv('WEB_PORT', 5010))
    print(f"🌐 Веб-сервер: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)


if __name__ == '__main__':
    run_web()