"""Daily weather for an entry's place and date, from Open-Meteo (free, no API key)."""
from datetime import date

import requests

DAILY = 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max'


def lookup(lat, lng, day):
    """Return {'code','tmax','tmin','precip','wind'} for that day, or None if unavailable."""
    if lat is None or lng is None or day is None or day > date.today():
        return None
    # The archive lags a few days behind; the forecast API covers the recent past.
    recent = (date.today() - day).days < 60
    url = ('https://api.open-meteo.com/v1/forecast' if recent
           else 'https://archive-api.open-meteo.com/v1/archive')
    try:
        r = requests.get(url, params={
            'latitude': round(lat, 4), 'longitude': round(lng, 4),
            'start_date': day.isoformat(), 'end_date': day.isoformat(),
            'daily': DAILY, 'timezone': 'auto',
        }, timeout=8)
        d = r.json().get('daily') or {}
        if not d.get('weather_code') or d['weather_code'][0] is None:
            return None
        return {
            'code':   d['weather_code'][0],
            'tmax':   d['temperature_2m_max'][0],
            'tmin':   d['temperature_2m_min'][0],
            'precip': d['precipitation_sum'][0],
            'wind':   d['wind_speed_10m_max'][0],
        }
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None
