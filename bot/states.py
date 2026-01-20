from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    from_address = State()
    to_address = State()
    comment = State()
    confirm = State()


class DriverRegStates(StatesGroup):
    car_info = State()
