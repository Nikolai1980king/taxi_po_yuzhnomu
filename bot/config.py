import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Токен из .env или значение по умолчанию для локальной разработки
BOT_TOKEN = os.getenv("BOT_TOKEN", "7651502885:AAF-r4Rcb7Pwb036oVfqSmQjTkn0GggxkDA")

# Путь к БД
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "taxi_bot.db"

# Состояния заказа
ORDER_SEARCHING = "searching"      # ищет водителя
ORDER_ACCEPTED = "accepted"       # водитель принял
ORDER_DRIVER_COMING = "driver_coming"  # водитель в пути к пассажиру
ORDER_IN_PROGRESS = "in_progress" # пассажир в машине
ORDER_COMPLETED = "completed"
ORDER_CANCELLED = "cancelled"

# Роли
ROLE_DRIVER = "driver"
ROLE_PASSENGER = "passenger"
