import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import BOT_TOKEN
from bot.database import cancel_order_if_searching, get_expired_searching_orders, init_db
from bot.handlers import setup_routers

logging.basicConfig(level=logging.INFO)

ORDER_EXPIRE_MINUTES = 5
ORDER_EXPIRE_CHECK_INTERVAL = 30  # секунд


async def check_expired_orders(bot: Bot) -> None:
    """Раз в 30 сек отменяет заказы в поиске старше 5 минут и уведомляет пассажира."""
    while True:
        try:
            await asyncio.sleep(ORDER_EXPIRE_CHECK_INTERVAL)
            orders = await get_expired_searching_orders(limit_minutes=ORDER_EXPIRE_MINUTES)
            for o in orders:
                if not await cancel_order_if_searching(o["id"]):
                    continue
                try:
                    await bot.send_message(
                        o["passenger_telegram_id"],
                        f"⏱ За 5 минут водитель не нашёлся. Заказ #{o['id']} отменён.\n\n"
                        "Можете создать новый заказ.",
                    )
                except Exception:
                    pass
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.exception("check_expired_orders: %s", e)


async def main() -> None:
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(setup_routers())
    task = asyncio.create_task(check_expired_orders(bot))
    try:
        await dp.start_polling(bot)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
