"""Точка входа: инициализация БД и запуск приложения."""
import os
from app import app, socketio, init_db, rebuild_driver_queue

if __name__ == '__main__':
    init_db()
    rebuild_driver_queue()
    ssl = (os.environ.get('USE_HTTPS') == '1')
    if ssl:
        # Важно: use_reloader=False, иначе Flask поднимает второй процесс и очередь "расслаивается"
        socketio.run(app, debug=True, host='0.0.0.0', port=5000, ssl_context='adhoc', allow_unsafe_werkzeug=True, use_reloader=False)
    else:
        socketio.run(app, debug=True, host='0.0.0.0', port=5000, use_reloader=False)
