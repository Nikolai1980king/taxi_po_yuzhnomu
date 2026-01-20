from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def role_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🚗 Я водитель", callback_data="role:driver"),
        InlineKeyboardButton(text="🧑‍💼 Я пассажир", callback_data="role:passenger"),
    )
    return builder.as_markup()


def switch_role_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🚗 Я водитель", callback_data="switch_role:driver"),
        InlineKeyboardButton(text="🧑‍💼 Я пассажир", callback_data="switch_role:passenger"),
    )
    return builder.as_markup()


def main_passenger_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🚕 Заказать такси"),
        KeyboardButton(text="📋 Мои заказы"),
    )
    builder.row(KeyboardButton(text="❌ Отменить заказ"))
    builder.row(KeyboardButton(text="🔄 Сменить роль"))
    return builder.as_markup(resize_keyboard=True)


def main_driver_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📋 Доступные заказы"),
        KeyboardButton(text="📌 Мой заказ"),
    )
    builder.row(
        KeyboardButton(text="🟢 Выйти на линию"),
        KeyboardButton(text="🔴 Сойти с линии"),
    )
    builder.row(KeyboardButton(text="🔄 Сменить роль"))
    return builder.as_markup(resize_keyboard=True)


def cancel_order_keyboard(order_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"cancel_order:{order_id}"))
    return builder.as_markup()


def available_orders_keyboard(orders: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for o in orders:
        short_from = (o.get("from_address") or "?")[:25] + ("…" if len(o.get("from_address") or "?") > 25 else "")
        builder.row(
            InlineKeyboardButton(
                text=f"#{o['id']} {short_from}",
                callback_data=f"take_order:{o['id']}",
            )
        )
    if not orders:
        builder.row(InlineKeyboardButton(text="Нет заказов", callback_data="noop"))
    return builder.as_markup()


def take_order_keyboard(order_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Взять заказ", callback_data=f"take_order:{order_id}"))
    return builder.as_markup()


def driver_order_actions_keyboard(order_id: int, status: str) -> InlineKeyboardMarkup:
    """Кнопки в зависимости от статуса: accepted -> driver_coming -> in_progress -> completed."""
    builder = InlineKeyboardBuilder()
    if status == "accepted":
        builder.row(
            InlineKeyboardButton(text="🚗 В пути к пассажиру", callback_data=f"order_status:{order_id}:driver_coming"),
        )
    elif status == "driver_coming":
        builder.row(
            InlineKeyboardButton(text="👤 Пассажир в машине", callback_data=f"order_status:{order_id}:in_progress"),
        )
    elif status == "in_progress":
        builder.row(
            InlineKeyboardButton(text="✅ Завершить поездку", callback_data=f"order_status:{order_id}:completed"),
        )
    return builder.as_markup()


def location_request_keyboard(show_change_from: bool = False) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📍 Указать точку на карте", request_location=True))
    if show_change_from:
        builder.row(KeyboardButton(text="↩️ Изменить «откуда»"))
    return builder.as_markup(resize_keyboard=True)


def comment_request_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="⏭ Пропустить"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def skip_comment_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_comment"))
    return builder.as_markup()


def confirm_order_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_order"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_new_order"),
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Изменить «откуда»", callback_data="change_from_only"),
        InlineKeyboardButton(text="✏️ Изменить «куда»", callback_data="change_to_only"),
    )
    builder.row(InlineKeyboardButton(text="↩️ Заново обе точки", callback_data="change_points"))
    return builder.as_markup()
