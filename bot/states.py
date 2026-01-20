from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    from_location = State()
    to_location = State()
    comment = State()
    confirm = State()


class DriverRegStates(StatesGroup):
    car_info = State()
