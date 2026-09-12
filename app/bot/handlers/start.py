from aiogram import F, Router
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.main import main_menu_kb, greeting_text
from app.database.models import User
from app.services.referral_service import parse_ref_payload, register_referral

router = Router(name="start")

BANNER_FILE_ID_SETTING_KEY = "start_banner_file_id"  # set by admin via bot settings, optional


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, session: AsyncSession, db_user: User) -> None:
    ref_id = parse_ref_payload(command.args)
    if ref_id and db_user.referred_by is None:
        if await register_referral(session, ref_id, db_user):
            db_user.referred_by = ref_id
            await session.commit()

    if command.args and command.args.startswith("anime_"):
        raw = command.args.removeprefix("anime_")
        if raw.isdigit():
            from app.services import anime_service
            from app.bot.handlers.anime import send_anime_card

            anime = await anime_service.find_by_code(session, int(raw))
            if anime is not None:
                await send_anime_card(message, session, anime, back_cb="menu:home")
                return

    await send_main_panel(message, db_user)


async def send_main_panel(message: Message, db_user: User) -> None:
    text = greeting_text(db_user)
    # Banner is optional -- admin uploads it once via admin panel and stores the file_id in Settings.
    try:
        await message.answer_photo(
            photo="https://placehold.co/1024x512/0b1220/ffffff?text=AniNovaX",
            caption=text, reply_markup=main_menu_kb(),
        )
    except Exception:
        await message.answer(text, reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu:home")
async def back_to_home(callback: CallbackQuery, db_user: User) -> None:
    text = greeting_text(db_user)
    try:
        await callback.message.edit_caption(caption=text, reply_markup=main_menu_kb())
    except Exception:
        await callback.message.edit_text(text, reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "sub:check")
async def sub_check(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    from app.services.channel_service import check_subscription, subscription_kb

    missing = await check_subscription(callback.bot, session, db_user.id)
    if missing:
        await callback.answer("Hali barcha kanallarga obuna bo'lmadingiz ❌", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=subscription_kb(missing))
        return

    await callback.answer("Obuna tasdiqlandi ✅")
    await callback.message.delete()
    await send_main_panel(callback.message, db_user)
