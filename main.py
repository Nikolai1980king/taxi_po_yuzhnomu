"""Точка входа: инициализация БД и запуск приложения."""
import os
from app import app, socketio, init_db, rebuild_driver_queue

if __name__ == '__main__':
    init_db()
    rebuild_driver_queue()
    ssl = (os.environ.get('USE_HTTPS') == '1')
    if ssl:
        socketio.run(app, debug=True, host='0.0.0.0', port=5000, ssl_context='adhoc', allow_unsafe_werkzeug=True)
    else:
        socketio.run(app, debug=True, host='0.0.0.0', port=5000)
