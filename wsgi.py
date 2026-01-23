"""
WSGI entrypoint for production (gunicorn).

Important: when running via gunicorn, the __main__ blocks in main.py/app.py are NOT executed,
so we initialize the database and rebuild the in-memory driver queue here.
"""

from app import app, init_db, rebuild_driver_queue

init_db()
rebuild_driver_queue()

# gunicorn looks for `app` here: `wsgi:app`

