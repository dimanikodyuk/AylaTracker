#!/usr/bin/env python3
"""
Ayla Tracker - Головний модуль запуску
"""

import threading
import time
import logging
import os
import sys
import signal
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def signal_handler(sig, frame):
    logger.info("👋 Отримано сигнал завершення...")
    sys.exit(0)


def main():
    pid_file = "ayla_tracker.pid"
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                old_pid = int(f.read())
            os.kill(old_pid, 0)
            logger.warning("⚠️ Бот вже запущено!")
            sys.exit(1)
        except:
            pass

    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("🐶 Запуск Ayla Tracker System")

    try:
        from web_app import run_web
        from simple_bot import run_bot

        web_thread = threading.Thread(target=run_web, daemon=True)
        web_thread.start()
        logger.info("✅ Веб-сервер запущено")

        time.sleep(2)

        logger.info("🚀 Запуск Telegram бота...")
        run_bot()

    except KeyboardInterrupt:
        logger.info("👋 Завершення роботи...")
    except Exception as e:
        logger.error(f"❌ Помилка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if os.path.exists(pid_file):
            os.remove(pid_file)


if __name__ == '__main__':
    main()