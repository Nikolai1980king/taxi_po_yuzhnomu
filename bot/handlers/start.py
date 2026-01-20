from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot import database as db
from bot.keyboards import main_driver_keyboard, main_passenger_keyboard, role_keyboard, switch_role_keyboard
from bot.config import ROLE_DRIVER, ROLE_PASSENGER

router = Router()


@router.message(Command("cancel"))
async def cmd_cancel(msg: Message, state: FSMContext) -> None:
    await state.clear()
    await msg.answer("Отменено.")


@router.message(CommandStart())
async def cmd_start(msg: Message) -> None:
    user = await db.get_user(msg.from_user.id)
    if user:
        if user["role"] == ROLE_PASSENGER:
            await msg.answer(
                "С возвращением! Чем могу помочь?",
                reply_markup=main_passenger_keyboard(),
            )
        else:
            status = "на линии" if user.get("is_driver_online") else "вне линии"
            await msg.answer(
                f"С возвращением! Вы сейчас {status}.",
                reply_markup=main_driver_keyboard(),
            )
        return
    await msg.answer(
        "👋 Добро пожаловать в бот заказа такси!\n\n"
        "Выберите вашу роль:",
        reply_markup=role_keyboard(),
    )


@router.callback_query(F.data.startswith("role:"))
async def choose_role(cb: CallbackQuery) -> None:
    role = cb.data.split(":", 1)[1]
    if role not in (ROLE_DRIVER, ROLE_PASSENGER):
        await cb.answer("Неверный выбор")
        return
    user = await db.get_user(cb.from_user.id)
    if user:
        await cb.answer("Вы уже зарегистрированы")
        return
    if role == ROLE_PASSENGER:
        await db.create_user(
            telegram_id=cb.from_user.id,
            role=ROLE_PASSENGER,
            username=cb.from_user.username,
            first_name=cb.from_user.first_name,
        )
        await cb.message.edit_text("✅ Вы зарегистрированы как пассажир. Чем могу помочь?")
        await cb.message.answer("Выберите действие:", reply_markup=main_passenger_keyboard())
    else:
        await db.create_user(
            telegram_id=cb.from_user.id,
            role=ROLE_DRIVER,
            username=cb.from_user.username,
            first_name=cb.from_user.first_name,
            car_info="",
        )
        await cb.message.edit_text("✅ Вы зарегистрированы как водитель.")
        await cb.message.answer(
            "Нажмите «🟢 Выйти на линию», чтобы получать заказы.",
            reply_markup=main_driver_keyboard(),
        )
    await cb.answer()


@router.message(F.text == "🔄 Сменить роль")
async def switch_role_menu(msg: Message) -> None:
    user = await db.get_user(msg.from_user.id)
    if not user:
        await msg.answer("Сначала нажмите /start и выберите роль.")
        return
    await msg.answer("Выберите роль:", reply_markup=switch_role_keyboard())


@router.callback_query(F.data.startswith("switch_role:"))
async def switch_role_do(cb: CallbackQuery) -> None:
    role = cb.data.split(":", 1)[1]
    if role not in (ROLE_DRIVER, ROLE_PASSENGER):
        await cb.answer("Неверный выбор")
        return
    user = await db.get_user(cb.from_user.id)
    if not user:
        await cb.answer("Сначала /start")
        return
    await db.update_user_role(cb.from_user.id, role)
    if role == ROLE_DRIVER:
        await db.set_driver_online(cb.from_user.id, False)
        await cb.message.edit_text("✅ Теперь вы водитель.")
        await cb.message.answer("Нажмите «🟢 Выйти на линию», чтобы получать заказы.", reply_markup=main_driver_keyboard())
    else:
        await cb.message.edit_text("✅ Теперь вы пассажир.")
        await cb.message.answer("Чем могу помочь?", reply_markup=main_passenger_keyboard())
    await cb.answer()
