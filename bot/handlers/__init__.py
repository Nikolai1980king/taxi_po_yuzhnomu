from aiogram import Router

from . import driver, passenger, start


def setup_routers() -> Router:
    router = Router()
    router.include_router(start.router)
    router.include_router(driver.router)  # до passenger, чтобы «Выйти на линию» не перехватывало пассажирское «выберите точку»
    router.include_router(passenger.router)
    return router
