from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot import database as db
from bot.config import ROLE_DRIVER
from bot.keyboards import available_orders_keyboard, driver_order_actions_keyboard, main_driver_keyboard

router = Router()

STATUS_LABELS = {
    "accepted": "✅ Принят",
    "driver_coming": "🚗 В пути к пассажиру",
    "in_progress": "👤 Пассажир в машине",
    "completed": "✔️ Завершён",
}


def _format_order(o: dict) -> str:
    s = f"Заказ #{o['id']}\n"
    s += f"📍 Откуда: {o.get('from_address') or '—'}\n"
    s += f"📍 Куда: {o.get('to_address') or '—'}\n"
    if o.get("comment"):
        s += f"💬 {o['comment']}\n"
    s += f"👤 Пассажир: {o.get('passenger_name', '—')}\n"
    s += f"📌 {STATUS_LABELS.get(o['status'], o['status'])}\n"
    fl, fln, tl, tln = o.get("from_lat"), o.get("from_lon"), o.get("to_lat"), o.get("to_lon")
    if fl is not None and fln is not None and tl is not None and tln is not None:
        s += f"\n🗺 Маршрут: https://yandex.ru/maps/?rtext={fl},{fln}~{tl},{tln}&rtt=auto\n"
    return s


# --- Выйти на линию / Сойти с линии ---

def _drivers_plural(n: int) -> str:
    if n == 1:
        return "1 водитель"
    if 2 <= n <= 4:
        return f"{n} водителя"
    return f"{n} водителей"


@router.message(F.text == "🟢 Выйти на линию")
async def driver_online(msg: Message, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user(msg.from_user.id)
    if not user or user["role"] != ROLE_DRIVER:
        return
    await db.set_driver_online(msg.from_user.id, True)
    n = len(await db.get_online_drivers())
    await msg.answer(
        f"🟢 Вы на линии. Сейчас на линии: {_drivers_plural(n)}.\nЗаказы — в «Доступные заказы».",
        reply_markup=main_driver_keyboard(),
    )


@router.message(F.text == "🔴 Сойти с линии")
async def driver_offline(msg: Message) -> None:
    user = await db.get_user(msg.from_user.id)
    if not user or user["role"] != ROLE_DRIVER:
        return
    active = await db.get_driver_active_order(msg.from_user.id)
    if active:
        await msg.answer("Сначала завершите текущий заказ или отмените его.")
        return
    await db.set_driver_online(msg.from_user.id, False)
    await msg.answer("🔴 Вы сняты с линии.", reply_markup=main_driver_keyboard())


# --- Доступные заказы ---

@router.message(F.text == "📋 Доступные заказы")
async def available_orders(msg: Message, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user(msg.from_user.id)
    if not user or user["role"] != ROLE_DRIVER:
        return
    if not user.get("is_driver_online"):
        await msg.answer("Сначала нажмите «🟢 Выйти на линию».")
        return
    active = await db.get_driver_active_order(msg.from_user.id)
    if active:
        n = len(await db.get_online_drivers())
        await msg.answer(
            f"На линии: {_drivers_plural(n)}.\n\nУ вас есть активный заказ:\n\n" + _format_order(active),
            reply_markup=driver_order_actions_keyboard(active["id"], active["status"]),
        )
        return
    orders = await db.get_available_orders()
    n = len(await db.get_online_drivers())
    if not orders:
        await msg.answer(f"Пока нет свободных заказов. На линии: {_drivers_plural(n)}. Проверьте позже.")
        return
    text = f"На линии: {_drivers_plural(n)}.\n\nСвободные заказы (нажмите, чтобы взять):\n"
    for o in orders:
        fa, ta = (o.get("from_address") or "?")[:40], (o.get("to_address") or "?")[:30]
        text += f"\n#{o['id']} | {fa} → {ta}\n"
    await msg.answer(text, reply_markup=available_orders_keyboard(orders))


# --- Взять заказ ---

@router.callback_query(F.data.startswith("take_order:"))
async def take_order(cb: CallbackQuery) -> None:
    oid = int(cb.data.split(":")[1])
    user = await db.get_user(cb.from_user.id)
    if not user or user["role"] != ROLE_DRIVER:
        await cb.answer("Доступно только водителям")
        return
    if not user.get("is_driver_online"):
        await cb.answer("Выйдите на линию")
        return
    ok = await db.accept_order(oid, cb.from_user.id)
    if not ok:
        await cb.answer("Заказ уже взят или отменён")
        return
    order = await db.get_order(oid)
    pass_tid = order["passenger_telegram_id"]
    try:
        await cb.bot.send_message(
            pass_tid,
            f"✅ Водитель принял заказ #{oid}. Ожидайте, он скоро будет.\n"
            f"Водитель: {user.get('first_name') or 'Водитель'}",
        )
    except Exception:
        pass
    await cb.message.edit_text(
        f"✅ Вы взяли заказ #{oid}.\n\n" + _format_order(order),
        reply_markup=driver_order_actions_keyboard(oid, "accepted"),
    )
    await cb.answer()


# --- Действия по заказу: в пути / в машине / завершить ---

@router.callback_query(F.data.startswith("order_status:"))
async def order_status(cb: CallbackQuery) -> None:
    parts = cb.data.split(":")
    if len(parts) != 3:
        await cb.answer()
        return
    oid, new_status = int(parts[1]), parts[2]
    if new_status not in ("driver_coming", "in_progress", "completed"):
        await cb.answer("Неверный статус")
        return
    order = await db.get_order(oid)
    if not order or order["driver_telegram_id"] != cb.from_user.id:
        await cb.answer("Заказ не найден")
        return
    await db.update_order_status(oid, new_status)
    order = await db.get_order(oid)
    pass_tid = order["passenger_telegram_id"]
    labels = {
        "driver_coming": "🚗 Водитель в пути к вам.",
        "in_progress": "👤 Поездка началась.",
        "completed": "✔️ Поездка завершена. Спасибо!",
    }
    try:
        await cb.bot.send_message(pass_tid, labels.get(new_status, f"Статус: {new_status}"))
    except Exception:
        pass
    if new_status == "completed":
        await cb.message.edit_text(f"✔️ Заказ #{oid} завершён.\n\n" + _format_order(order))
    else:
        await cb.message.edit_text(
            _format_order(order),
            reply_markup=driver_order_actions_keyboard(oid, new_status),
        )
    await cb.answer()


# --- Мой заказ ---

@router.message(F.text == "📌 Мой заказ")
async def my_order(msg: Message, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user(msg.from_user.id)
    if not user or user["role"] != ROLE_DRIVER:
        return
    active = await db.get_driver_active_order(msg.from_user.id)
    if not active:
        n = len(await db.get_online_drivers())
        await msg.answer(f"Нет активного заказа. На линии: {_drivers_plural(n)}. Смотрите «Доступные заказы».")
        return
    n = len(await db.get_online_drivers())
    await msg.answer(
        f"На линии: {_drivers_plural(n)}.\n\n" + _format_order(active),
        reply_markup=driver_order_actions_keyboard(active["id"], active["status"]),
    )
