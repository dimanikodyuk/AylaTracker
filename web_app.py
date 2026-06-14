#!/usr/bin/env python3
"""
Ayla Tracker - Web Dashboard (оновлена версія з функціоналом цуценяти)
"""

from flask import Flask, jsonify, request, send_from_directory
from datetime import datetime, timedelta
import os
import io
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


def send_telegram(message, chat_id=None, parse_mode='HTML'):
    token = db.get_setting('telegram_bot_token', TELEGRAM_BOT_TOKEN)
    target_chat = chat_id or db.get_setting('telegram_chat_id', TELEGRAM_CHAT_ID)
    if not token or not target_chat:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={'chat_id': target_chat, 'text': message, 'parse_mode': parse_mode}, timeout=10)
        return True
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False


def send_telegram_photo(photo_bytes, caption, chat_id=None):
    token = db.get_setting('telegram_bot_token', TELEGRAM_BOT_TOKEN)
    target_chat = chat_id or db.get_setting('telegram_chat_id', TELEGRAM_CHAT_ID)
    if not token or not target_chat:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        requests.post(url, data={'chat_id': target_chat, 'caption': caption, 'parse_mode': 'HTML'},
                      files={'photo': ('chart.png', photo_bytes, 'image/png')}, timeout=15)
        return True
    except Exception as e:
        logger.error(f"Telegram photo error: {e}")
        return False


def make_bar(value, max_val, width=12, fill='█', empty='░'):
    if max_val == 0:
        filled = 0
    else:
        filled = int((value / max_val) * width)
    filled = max(0, min(width, filled))
    return fill * filled + empty * (width - filled)


def generate_weekly_chart(weekly_data):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np

        dates = weekly_data.get('dates', [])
        walk = weekly_data.get('walk', [])
        sleep = weekly_data.get('sleep', [])

        if not dates:
            return None

        short_dates = []
        for d in dates:
            try:
                dt = datetime.strptime(d, '%Y-%m-%d')
                short_dates.append(dt.strftime('%d.%m'))
            except:
                short_dates.append(d)

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 5), facecolor='#f5f5f7')
        fig.suptitle('🐾 Айла — статистика тижня', fontsize=14, fontweight='bold', color='#333', y=0.98)

        x = np.arange(len(short_dates))
        w = 0.6

        ax1.bar(x, walk, width=w, color='#3498db', alpha=0.85, zorder=3)
        ax1.set_facecolor('#f0f4f8')
        ax1.set_ylabel('хв', color='#3498db', fontsize=9)
        ax1.set_title('🚶 Прогулянки (хв/день)', fontsize=10, color='#333', pad=4)
        ax1.set_xticks(x)
        ax1.set_xticklabels(short_dates, fontsize=9)
        ax1.grid(axis='y', linestyle='--', alpha=0.5, zorder=0)
        ax1.tick_params(colors='#555')
        for i, v in enumerate(walk):
            if v > 0:
                ax1.text(i, v + 0.5, str(int(v)), ha='center', va='bottom', fontsize=8, color='#2980b9',
                         fontweight='bold')
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)

        ax2.bar(x, sleep, width=w, color='#9b59b6', alpha=0.85, zorder=3)
        ax2.set_facecolor('#f4f0f8')
        ax2.set_ylabel('год', color='#9b59b6', fontsize=9)
        ax2.set_title('😴 Сон (год/день)', fontsize=10, color='#333', pad=4)
        ax2.set_xticks(x)
        ax2.set_xticklabels(short_dates, fontsize=9)
        ax2.grid(axis='y', linestyle='--', alpha=0.5, zorder=0)
        ax2.tick_params(colors='#555')
        for i, v in enumerate(sleep):
            if v > 0:
                ax2.text(i, v + 0.2, f'{v:.1f}', ha='center', va='bottom', fontsize=8, color='#8e44ad',
                         fontweight='bold')
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)

        plt.tight_layout(rect=[0, 0, 1, 0.96])

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='#f5f5f7')
        buf.seek(0)
        plt.close(fig)
        return buf.read()
    except Exception as e:
        logger.error(f"Chart generation error: {e}")
        return None


def send_notifications(message):
    recipients = db.get_notification_recipients()
    sent = 0
    for chat_id in recipients:
        if send_telegram(message, chat_id):
            sent += 1
    return sent


def build_daily_report_text(date_str, events, pet_name='Айла'):
    feed_events = [e for e in events if e['type'] == 'feed']
    walk_events = [e for e in events if e['type'] == 'walk']
    sleep_events = [e for e in events if e['type'] == 'sleep']
    toilet_events = [e for e in events if e['type'] == 'toilet']
    behavior_events = [e for e in events if e['type'] == 'behavior']

    walk_min = sum(e['value'] for e in walk_events if e['value']) // 60
    sleep_hrs = sum(e['value'] for e in sleep_events if e['value']) / 3600
    pee = len([e for e in toilet_events if e.get('subtype') == 'піся'])
    poop = len([e for e in toilet_events if e.get('subtype') == 'кака'])

    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        day_ua = ['Понеділок', 'Вівторок', 'Середа', 'Четвер', 'П\'ятниця', 'Субота', 'Неділя'][dt.weekday()]
        date_pretty = f"{dt.strftime('%d.%m.%Y')} ({day_ua})"
    except:
        date_pretty = date_str

    score = 0
    if len(feed_events) >= 3: score += 2
    if walk_min >= 20: score += 2
    if walk_min >= 40: score += 1
    if sleep_hrs >= 10: score += 2
    if not behavior_events: score += 2

    mood_emoji = '🌟' if score >= 8 else ('😊' if score >= 5 else '😐')

    lines = [
        f"🐾 <b>{pet_name} — Денний звіт</b>",
        f"📅 {date_pretty}  {mood_emoji}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"🍖 <b>Годування</b>: {len(feed_events)} раз(и)",
    ]

    if feed_events:
        times = []
        for e in feed_events:
            dt2 = datetime.fromtimestamp(e['timestamp'])
            times.append(dt2.strftime('%H:%M'))
        lines.append(f"   ⏰ о {', '.join(times)}")

    lines += [
        "",
        f"🚶 <b>Прогулянки</b>: {walk_min} хв  {make_bar(walk_min, 60)}",
    ]
    if walk_events:
        for e in walk_events:
            dt2 = datetime.fromtimestamp(e['timestamp'])
            dur = (e['value'] or 0) // 60
            lines.append(f"   • {dt2.strftime('%H:%M')} — {dur} хв")

    lines += [
        "",
        f"😴 <b>Сон</b>: {sleep_hrs:.1f} год  {make_bar(sleep_hrs, 16)}",
    ]
    if sleep_events:
        for e in sleep_events:
            dt2 = datetime.fromtimestamp(e['timestamp'])
            dur = (e['value'] or 0) / 3600
            lines.append(f"   • {dt2.strftime('%H:%M')} — {dur:.1f} год")

    lines += [
        "",
        f"🚽 <b>Туалет</b>: 💧 Піся ×{pee}   💩 Кака ×{poop}",
    ]

    if behavior_events:
        lines += ["", f"⚠️ <b>Поведінка</b>: {len(behavior_events)} інцидент(ів)"]
        for e in behavior_events:
            lines.append(f"   • {e.get('subtype', 'Погана поведінка')}")
    else:
        lines += ["", "✅ <b>Поведінка</b>: без зауважень"]

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        f"<i>Оцінка дня: {score}/10 {mood_emoji}</i>"
    ]

    return "\n".join(lines)


def build_weekly_report_text(report, pet_name='Айла', damages=None, zoomies=None):
    walk_min = report.get('walk_seconds', 0) // 60
    sleep_hrs = report.get('sleep_seconds', 0) / 3600
    avg_walk = walk_min / 7
    avg_sleep = sleep_hrs / 7
    avg_feed = report.get('feed', 0) / 7

    lines = [
        f"🐾 <b>{pet_name} — Тижневий звіт</b>",
        f"📅 Останні 7 днів",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"🍖 <b>Годування</b>",
        f"   Всього: {report.get('feed', 0)} раз  |  В середньому: {avg_feed:.1f}/день",
        "",
        f"🚶 <b>Прогулянки</b>",
        f"   Всього: {walk_min} хв  |  В середньому: {avg_walk:.0f} хв/день",
        f"   {make_bar(avg_walk, 60, 14)}",
        "",
        f"😴 <b>Сон</b>",
        f"   Всього: {sleep_hrs:.1f} год  |  В середньому: {avg_sleep:.1f} год/день",
        f"   {make_bar(avg_sleep, 16, 14)}",
        "",
        f"🚽 <b>Туалет</b>: {report.get('toilet', 0)} разів за тиждень",
        "",
    ]

    if damages and damages.get('total', 0) > 0:
        lines += [
            f"💸 <b>Збитки</b>: {damages['total']:.0f} грн за тиждень",
            "",
        ]

    if zoomies and zoomies.get('count', 0) > 0:
        lines += [
            f"🐕 <b>Зуміси</b>: {zoomies['count']} разів",
            f"   Середня тривалість: {zoomies.get('avg_duration', 0)} хв",
            "",
        ]

    if report.get('training_count', 0) > 0:
        lines += [
            f"🏋️ <b>Тренування</b>: {report['training_count']} сесій",
            f"   Середній успіх: {report.get('training_avg', 0)}/5",
            "",
        ]

    if report.get('mental_minutes', 0) > 0:
        lines += [f"🧠 <b>Ментальна активність</b>: {report['mental_minutes']} хв за тиждень", ""]

    behavior = report.get('behavior', 0)
    if behavior == 0:
        lines.append("✅ <b>Поведінка</b>: чудовий тиждень, без інцидентів!")
    elif behavior <= 3:
        lines.append(f"⚠️ <b>Поведінка</b>: {behavior} інцидент(ів) — є над чим попрацювати")
    else:
        lines.append(f"❌ <b>Поведінка</b>: {behavior} інцидент(ів) — потрібна увага")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "<i>📊 Графік прогулянок і сну — вище ⬆️</i>"
    ]

    return "\n".join(lines)


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
        return jsonify(
            {'feed': 0, 'walk_seconds': 0, 'sleep_seconds': 0, 'toilet': 0, 'behavior': 0, 'pet_name': 'Айла',
             'age_months': 4})


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


# ========== ЗБИТКИ (DAMAGES) ==========

@app.route('/api/damages', methods=['GET', 'POST', 'DELETE'])
def api_damages():
    try:
        if request.method == 'POST':
            data = request.get_json()
            db.add_damage(data['item_name'], data['cost'], data.get('category'), data.get('note'))
            return jsonify({'success': True})
        elif request.method == 'DELETE':
            data = request.get_json()
            db.delete_damage(data['id'])
            return jsonify({'success': True})
        else:
            damages = db.get_damages(100)
            stats = db.get_damages_stats(30)
            return jsonify({'damages': damages, 'stats': stats})
    except Exception as e:
        return jsonify({'damages': [], 'stats': {'total': 0, 'count': 0}})


# ========== ЗУМІСИ (ZOOMIES) ==========

@app.route('/api/zoomies', methods=['GET', 'POST', 'DELETE'])
def api_zoomies():
    try:
        if request.method == 'POST':
            data = request.get_json()
            db.add_zoomie(data['duration'], data.get('intensity', 3), data.get('note'))
            return jsonify({'success': True})
        elif request.method == 'DELETE':
            data = request.get_json()
            db.delete_zoomie(data['id'])
            return jsonify({'success': True})
        else:
            zoomies = db.get_zoomies(100)
            stats = db.get_zoomies_stats(30)
            return jsonify({'zoomies': zoomies, 'stats': stats})
    except Exception as e:
        return jsonify({'zoomies': [], 'stats': {'count': 0, 'avg_duration': 0}})


# ========== КАРАНТИН (QUARANTINE) ==========

@app.route('/api/quarantine', methods=['GET', 'POST'])
def api_quarantine():
    try:
        if request.method == 'POST':
            data = request.get_json()
            db.set_last_vaccination(data['vaccination_date'])
            return jsonify({'success': True})
        else:
            return jsonify(db.get_quarantine_status())
    except Exception as e:
        return jsonify({'in_quarantine': False, 'days_left': 0, 'message': 'Помилка'})


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
        return jsonify(
            {'dates': [], 'durations': [], 'activities': [], 'types': [], 'potty_types': [], 'potty_counts': [],
             'avg_mental': 0})


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
        if not data or not data.get('title'):
            return jsonify({'success': False, 'error': 'Missing title'})
        interval = int(data['interval_days']) if data.get('interval_days') else 0
        db.add_medical_reminder(data['title'], data.get('description', ''), interval,
                                data.get('reminder_time', '09:00'))
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
                                       height_cm=data.get('height_cm'), note=data.get('note'),
                                       new_timestamp=new_timestamp)
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
        report = db.get_full_report(7)
        damages = db.get_damages_stats(7)
        zoomies = db.get_zoomies_stats(7)
        return jsonify({
            **report,
            'damages_total': damages['total'],
            'damages_count': damages['count'],
            'zoomies_count': zoomies['count'],
            'zoomies_avg_duration': zoomies['avg_duration']
        })
    except Exception as e:
        return jsonify({'days': 7, 'feed': 0, 'walk_seconds': 0, 'toilet': 0, 'sleep_seconds': 0,
                        'mental_minutes': 0, 'training_count': 0, 'training_avg': 0, 'behavior': 0,
                        'damages_total': 0, 'damages_count': 0, 'zoomies_count': 0, 'zoomies_avg_duration': 0})


@app.route('/api/send_report', methods=['POST'])
def api_send_report():
    try:
        pet_name = db.get_setting('pet_name', 'Айла')
        report = db.get_full_report(7)
        damages = db.get_damages_stats(7)
        zoomies = db.get_zoomies_stats(7)
        weekly_data = db.get_weekly_chart_data()

        text = build_weekly_report_text(report, pet_name, damages, zoomies)
        chart_bytes = generate_weekly_chart(weekly_data)

        recipients = [None] + [g['chat_id'] for g in db.get_group_chats()]
        success_count = 0

        for chat_id in recipients:
            if chat_id is None and not db.get_setting('telegram_chat_id'):
                continue
            if chart_bytes:
                if send_telegram_photo(chart_bytes, text, chat_id):
                    success_count += 1
            else:
                if send_telegram(text, chat_id):
                    success_count += 1

        return jsonify({'message': f'✅ Звіт надіслано {success_count} отримувачам!'})
    except Exception as e:
        logger.error(f"Send report error: {e}")
        return jsonify({'message': '❌ Помилка надсилання'})


@app.route('/api/send_daily_report', methods=['POST'])
def api_send_daily_report():
    try:
        data = request.get_json()
        date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
        pet_name = db.get_setting('pet_name', 'Айла')
        events = db.get_events_by_date_range(date, date)

        text = build_daily_report_text(date, events, pet_name)
        chat_id = data.get('chat_id')

        if send_telegram(text, chat_id):
            return jsonify({'message': '✅ Денний звіт надіслано!'})
        return jsonify({'message': '❌ Помилка надсилання'})
    except Exception as e:
        logger.error(f"Send daily report error: {e}")
        return jsonify({'message': '❌ Помилка надсилання'})


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

        # Додаємо статус карантину
        quarantine = db.get_quarantine_status()
        if quarantine['in_quarantine']:
            insight += f" 🚨 Карантин: {quarantine['days_left']} днів."

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
        response = requests.post(url, json={'chat_id': chat_id, 'text': '🐾 Тестове повідомлення від Ayla Tracker! ✅'},
                                 timeout=10)
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
                                      data.get('parasite_type'), data.get('medication'), data.get('dosage'),
                                      data.get('notes'))
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
            db.add_family_member(data['name'], data.get('role', 'member'), data.get('chat_id'),
                                 data.get('notify', True))
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