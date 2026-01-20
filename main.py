"""Точка входа: инициализация БД и запуск приложения."""
from app import app, socketio, init_db, rebuild_driver_queue

if __name__ == '__main__':
    init_db()
    rebuild_driver_queue()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
