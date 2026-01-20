import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///taxi.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ORDER_TIMEOUT_SECONDS = 60  # 1 минута на принятие заказа
    SOCKETIO_CORS_ALLOWED_ORIGINS = "*"
    # Ключ API Яндекс.Карт: https://developer.tech.yandex.ru/ — без ключа используется Leaflet (OSM)
    YANDEX_MAPS_API_KEY = os.environ.get('YANDEX_MAPS_API_KEY', 'df6f0239-66a8-4976-9d42-c4292899fec5')
