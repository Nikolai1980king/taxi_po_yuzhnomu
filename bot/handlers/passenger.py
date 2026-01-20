from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import database as db
from bot.config import ROLE_PASSENGER
from bot.keyboards import (
    cancel_order_keyboard,
    confirm_order_keyboard,
    main_passenger_keyboard,
    skip_comment_keyboard,
)
from bot.states import OrderStates

router = Router()

STATUS_LABELS = {
    "searching": "🔍 Ищет водителя",
    "accepted": "✅ Водитель принял",
    "driver_coming": "🚗 Водитель в пути",
    "in_progress": "👤 Поездка",
    "completed": "✔️ Завершён",
    "cancelled": "❌ Отменён",
}


def _format_order(o: dict, for_passenger: bool = True) -> str:
    s = f"Заказ #{o['id']}\n"
    s += f"📍 Откуда: {o['from_address']}\n"
    s += f"📍 Куда: {o['to_address']}\n"
    if o.get("comment"):
        s += f"💬 {o['comment']}\n"
    s += f"📌 {STATUS_LABELS.get(o['status'], o['status'])}\n"
    if for_passenger and o.get("driver_name"):
        s += f"🚗 Водитель: {o['driver_name']}\n"
    return s


# --- Заказать такси ---

@router.message(F.text == "🚕 Заказать такси")
async def order_start(msg: Message, state: FSMContext) -> None:
    user = await db.get_user(msg.from_user.id)
    if not user or user["role"] != ROLE_PASSENGER:
        return
    await state.set_state(OrderStates.from_address)
    await state.set_data({})
    await msg.answer("📍 Введите адрес отправления:")


@router.message(StateFilter(OrderStates.from_address), F.text)
async def order_from(msg: Message, state: FSMContext) -> None:
    await state.update_data(from_address=msg.text.strip())
    await state.set_state(OrderStates.to_address)
    await msg.answer("📍 Введите адрес назначения:")


@router.message(StateFilter(OrderStates.to_address), F.text)
async def order_to(msg: Message, state: FSMContext) -> None:
    await state.update_data(to_address=msg.text.strip())
    await state.set_state(OrderStates.comment)
    await msg.answer("💬 Комментарий к заказу (или нажмите «Пропустить»):", reply_markup=skip_comment_keyboard())


@router.callback_query(F.data == "skip_comment", StateFilter(OrderStates.comment))
async def order_comment_skip(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(comment="")
    await _order_confirm(cb.message, state, is_callback=True, cb=cb)


@router.message(StateFilter(OrderStates.comment), F.text)
async def order_comment(msg: Message, state: FSMContext) -> None:
    await state.update_data(comment=msg.text.strip())
    await _order_confirm(msg, state, is_callback=False)


async def _order_confirm(target, state: FSMContext, *, is_callback: bool, cb: CallbackQuery | None = None) -> None:
    data = await state.get_data()
    text = (
        "📋 Проверьте заказ:\n\n"
        f"📍 Откуда: {data['from_address']}\n"
        f"📍 Куда: {data['to_address']}\n"
    )
    if data.get("comment"):
        text += f"💬 {data['comment']}\n"
    text += "\nПодтвердить?"
    await state.set_state(OrderStates.confirm)
    if is_callback and cb:
        await cb.message.edit_text(text, reply_markup=confirm_order_keyboard())
        await cb.answer()
    else:
        await target.answer(text, reply_markup=confirm_order_keyboard())


@router.callback_query(F.data == "confirm_order", StateFilter(OrderStates.confirm))
async def order_confirm_yes(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    try:
        oid = await db.create_order(
            passenger_telegram_id=cb.from_user.id,
            from_address=data["from_address"],
            to_address=data["to_address"],
            comment=data.get("comment"),
        )
    except Exception as e:
        await cb.message.edit_text(f"Ошибка: {e}")
        await cb.answer()
        return
    await cb.message.edit_text(
        f"✅ Заказ #{oid} создан. Ищем водителя...\n\n"
        "Обновляйте «Мои заказы» или ожидайте уведомления.",
        reply_markup=cancel_order_keyboard(oid),
    )
    await cb.answer()


@router.callback_query(F.data == "cancel_new_order", StateFilter(OrderStates.confirm))
async def order_confirm_no(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.edit_text("Заказ отменён.")
    await cb.answer()


# --- Отменить заказ ---

@router.message(F.text == "❌ Отменить заказ")
async def cancel_order_menu(msg: Message) -> None:
    user = await db.get_user(msg.from_user.id)
    if not user or user["role"] != ROLE_PASSENGER:
        return
    orders = await db.get_orders_by_passenger(msg.from_user.id, status="searching")
    if not orders:
        await msg.answer("Нет заказов в поиске водителя.")
        return
    for o in orders:
        await msg.answer(_format_order(o), reply_markup=cancel_order_keyboard(o["id"]))


@router.callback_query(F.data.startswith("cancel_order:"))
async def cancel_order_do(cb: CallbackQuery) -> None:
    oid = int(cb.data.split(":")[1])
    order = await db.get_order(oid)
    if not order or order["passenger_telegram_id"] != cb.from_user.id:
        await cb.answer("Заказ не найден или не ваш")
        return
    if order["status"] != "searching":
        await cb.answer("Этот заказ уже принят водителем, отмена недоступна")
        return
    await db.cancel_order(oid, by_passenger=True)
    driver_tid = order.get("driver_telegram_id")
    if driver_tid:
        try:
            await cb.bot.send_message(driver_tid, f"Заказ #{oid} отменён пассажиром.")
        except Exception:
            pass
    await cb.message.edit_text(f"Заказ #{oid} отменён.")
    await cb.answer()


# --- Мои заказы ---

@router.message(F.text == "📋 Мои заказы")
async def my_orders(msg: Message) -> None:
    user = await db.get_user(msg.from_user.id)
    if not user or user["role"] != ROLE_PASSENGER:
        return
    orders = await db.get_orders_by_passenger(msg.from_user.id)
    if not orders:
        await msg.answer("У вас пока нет заказов.")
        return
    for o in orders:
        txt = _format_order(o)
        if o["status"] == "searching":
            await msg.answer(txt, reply_markup=cancel_order_keyboard(o["id"]))
        else:
            await msg.answer(txt)
