#!/usr/bin/env python3
"""
Google Calendar integration - заглушка
Для повноцінної роботи потрібно налаштувати Google Calendar API
та встановити google-auth-oauthlib, google-auth-httplib2, google-api-python-client
"""

import logging

logger = logging.getLogger(__name__)

# Заглушка для Google Calendar
service = None


def sync_reminders():
    logger.warning("Google Calendar не налаштовано")


def get_upcoming_events():
    return []


def add_feed_event(time_str):
    logger.warning("Google Calendar не налаштовано")


def add_walk_event(time_str):
    logger.warning("Google Calendar не налаштовано")


def add_medication_event(name, time_str):
    logger.warning("Google Calendar не налаштовано")