import asyncio

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from bot import database as db
from bot.config import ROLE_PASSENGER
from bot.geocoding import reverse_geocode
from bot.keyboards import (
    cancel_order_keyboard,
    comment_request_keyboard,
    confirm_order_keyboard,
    location_request_keyboard,
    main_passenger_keyboard,
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
    s += f"📍 Откуда: {o.get('from_address') or '—'}\n"
    s += f"📍 Куда: {o.get('to_address') or '—'}\n"
    if o.get("comment"):
        s += f"💬 {o['comment']}\n"
    s += f"📌 {STATUS_LABELS.get(o['status'], o['status'])}\n"
    if for_passenger and o.get("driver_name"):
        s += f"🚗 Водитель: {o['driver_name']}\n"
    return s


# --- Заказать такси ---

@router.message(F.text == "🚕 Заказать такси")
async def order_start(msg: Message, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user(msg.from_user.id)
    if not user or user["role"] != ROLE_PASSENGER:
        return
    await state.set_state(OrderStates.from_location)
    await state.set_data({})
    await msg.answer(
        "📍 Точка отправления (откуда забрать)\n\n"
        "Нажмите кнопку ниже. В открывшейся карте можно:\n"
        "• выбрать точку на карте\n"
        "• или отправить текущее местоположение",
        reply_markup=location_request_keyboard(show_change_from=False),
    )


@router.message(F.text == "📋 Мои заказы")
async def my_orders(msg: Message, state: FSMContext) -> None:
    await state.clear()
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


@router.message(F.text == "❌ Отменить заказ")
async def cancel_order_menu(msg: Message, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user(msg.from_user.id)
    if not user or user["role"] != ROLE_PASSENGER:
        return
    orders = await db.get_orders_by_passenger(msg.from_user.id, status="searching")
    if not orders:
        await msg.answer("Нет заказов в поиске водителя.")
        return
    for o in orders:
        await msg.answer(_format_order(o), reply_markup=cancel_order_keyboard(o["id"]))


@router.message(StateFilter(OrderStates.from_location), F.location)
async def order_from_location(msg: Message, state: FSMContext) -> None:
    lat, lon = msg.location.latitude, msg.location.longitude
    await state.update_data(from_lat=lat, from_lon=lon)
    await state.set_state(OrderStates.to_location)
    await msg.answer(
        "📍 Точка назначения (куда ехать)\n\n"
        "Нажмите кнопку и в карте выберите точку или отправьте своё местоположение.\n"
        "Если ошиблись с «откуда» — нажмите «Изменить «откуда»».",
        reply_markup=location_request_keyboard(show_change_from=True),
    )


@router.message(StateFilter(OrderStates.from_location), F.text)
async def order_from_location_wrong(msg: Message) -> None:
    await msg.answer("Нажмите кнопку 📍 «Указать точку на карте» — в карте выберите точку или отправьте местоположение.")


@router.message(StateFilter(OrderStates.to_location), F.text == "↩️ Изменить «откуда»")
async def order_to_location_change_from(msg: Message, state: FSMContext) -> None:
    await state.set_data({})
    await state.set_state(OrderStates.from_location)
    await msg.answer(
        "↩️ Выберите точку отправления заново:\n\n"
        "Нажмите кнопку — в карте выберите точку или отправьте текущее местоположение.",
        reply_markup=location_request_keyboard(show_change_from=False),
    )


@router.message(StateFilter(OrderStates.to_location), F.location)
async def order_to_location(msg: Message, state: FSMContext) -> None:
    to_lat, to_lon = msg.location.latitude, msg.location.longitude
    data = await state.get_data()
    from_lat, from_lon = data["from_lat"], data["from_lon"]
    await msg.answer("Определяю адреса…")
    from_addr = await asyncio.to_thread(reverse_geocode, from_lat, from_lon)
    await asyncio.sleep(1.1)
    to_addr = await asyncio.to_thread(reverse_geocode, to_lat, to_lon)
    await state.update_data(
        to_lat=to_lat, to_lon=to_lon,
        from_address=from_addr, to_address=to_addr,
    )
    await state.set_state(OrderStates.comment)
    await msg.answer(
        "💬 Комментарий к заказу (или нажмите «Пропустить»):",
        reply_markup=comment_request_keyboard(),
    )


@router.message(StateFilter(OrderStates.to_location), F.text)
async def order_to_location_wrong(msg: Message) -> None:
    await msg.answer(
        "Нажмите кнопку 📍 «Указать точку на карте» для точки назначения.\n"
        "Или «↩️ Изменить «откуда»», чтобы заново выбрать точку отправления."
    )


@router.message(StateFilter(OrderStates.comment), F.text == "⏭ Пропустить")
async def order_comment_skip(msg: Message, state: FSMContext) -> None:
    await state.update_data(comment="")
    await _order_confirm(msg, state, is_callback=False, cb=None)


@router.message(StateFilter(OrderStates.comment), F.text)
async def order_comment(msg: Message, state: FSMContext) -> None:
    await state.update_data(comment=msg.text.strip())
    await _order_confirm(msg, state, is_callback=False, cb=None)


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


@router.callback_query(F.data == "change_points", StateFilter(OrderStates.confirm))
async def order_confirm_change_points(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_data({})
    await state.set_state(OrderStates.from_location)
    await cb.message.edit_text("↩️ Обе точки сброшены. Выберите заново.")
    await cb.message.answer(
        "📍 Точка отправления (откуда забрать)\n\n"
        "Нажмите кнопку — в карте выберите точку или отправьте текущее местоположение.",
        reply_markup=location_request_keyboard(show_change_from=False),
    )
    await cb.answer()


@router.callback_query(F.data == "change_from_only", StateFilter(OrderStates.confirm))
async def order_confirm_change_from_only(cb: CallbackQuery, state: FSMContext) -> None:
    data = {k: v for k, v in (await state.get_data()).items() if k not in ("from_lat", "from_lon", "from_address")}
    await state.set_data(data)
    await state.set_state(OrderStates.from_location)
    await cb.message.edit_text("✏️ Измените точку «откуда».")
    await cb.message.answer(
        "📍 Точка отправления (откуда забрать)\n\n"
        "Нажмите кнопку — в карте выберите точку или отправьте текущее местоположение.",
        reply_markup=location_request_keyboard(show_change_from=False),
    )
    await cb.answer()


@router.callback_query(F.data == "change_to_only", StateFilter(OrderStates.confirm))
async def order_confirm_change_to_only(cb: CallbackQuery, state: FSMContext) -> None:
    data = {k: v for k, v in (await state.get_data()).items() if k not in ("to_lat", "to_lon", "to_address")}
    await state.set_data(data)
    await state.set_state(OrderStates.to_location)
    await cb.message.edit_text("✏️ Измените точку «куда».")
    await cb.message.answer(
        "📍 Точка назначения (куда ехать)\n\n"
        "Нажмите кнопку и в карте выберите точку или отправьте местоположение.",
        reply_markup=location_request_keyboard(show_change_from=True),
    )
    await cb.answer()


@router.callback_query(F.data == "confirm_order", StateFilter(OrderStates.confirm))
async def order_confirm_yes(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    try:
        oid = await db.create_order(
            passenger_telegram_id=cb.from_user.id,
            from_address=data["from_address"],
            to_address=data["to_address"],
            from_lat=data.get("from_lat"),
            from_lon=data.get("from_lon"),
            to_lat=data.get("to_lat"),
            to_lon=data.get("to_lon"),
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
