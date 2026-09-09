from aiogram.fsm.state import State, StatesGroup


class SearchStates(StatesGroup):
    waiting_code = State()
    waiting_name = State()
    waiting_image = State()


class AdminAnimeStates(StatesGroup):
    title = State()
    poster = State()
    banner = State()
    description = State()
    year = State()
    genres = State()
    rating = State()
    quality = State()
    code = State()
    uploading_videos = State()
    edit_pick_field = State()
    edit_value = State()


class AdminUserStates(StatesGroup):
    find_user = State()
    grant_coins = State()
    deduct_coins = State()
    message_user = State()


class AdminSettingsStates(StatesGroup):
    waiting_value = State()


class AdminCoinPackageStates(StatesGroup):
    coins = State()
    price = State()


class AdminVipPlanStates(StatesGroup):
    days = State()
    price_coins = State()
    price_money = State()


class AdminChannelStates(StatesGroup):
    waiting_forward_or_username = State()


class AdminAdStates(StatesGroup):
    text = State()
    photo = State()
    button = State()


class AdminBroadcastStates(StatesGroup):
    waiting_content = State()
    waiting_button = State()
    confirm = State()
