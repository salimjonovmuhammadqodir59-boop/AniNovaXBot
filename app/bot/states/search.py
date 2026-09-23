from aiogram.fsm.state import State, StatesGroup


class SearchStates(StatesGroup):
    waiting_code = State()
    waiting_name = State()
    waiting_image = State()
