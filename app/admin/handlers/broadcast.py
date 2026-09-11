import asyncio

from aiogram import F, Router
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.filters import IsAdmin
from app.admin.handlers.panel import log_admin_action
from app.bot.states.states import AdminBroadcastStates
from app.database.models import Broadcast, BroadcastStatus, User

router = Router(name="admin_broadcast")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:broadcast_start")
async def broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminBroadcastStates.waiting_content)
    await callback.message.answer("📨 Xabar matnini, rasm/video/GIFni yuboring:")
    await callback.answer()


@router.message(AdminBroadcastStates.waiting_content, F.text)
async def broadcast_text(message: Message, state: FSMContext) -> None:
    await state.update_data(content_type="text", text=message.text, file_id=None)
    await ask_button(message, state)


@router.message(AdminBroadcastStates.waiting_content, F.photo)
async def broadcast_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(content_type="photo", text=message.caption, file_id=message.photo[-1].file_id)
    await ask_button(message, state)


@router.message(AdminBroadcastStates.waiting_content, F.video)
async def broadcast_video(message: Message, state: FSMContext) -> None:
    await state.update_data(content_type="video", text=message.caption, file_id=message.video.file_id)
    await ask_button(message, state)


@router.message(AdminBroadcastStates.waiting_content, F.animation)
async def broadcast_gif(message: Message, state: FSMContext) -> None:
    await state.update_data(content_type="animation", text=message.caption, file_id=message.animation.file_id)
    await ask_button(message, state)


async def ask_button(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminBroadcastStates.waiting_button)
    await message.answer("🔗 Tugma qo'shmoqchimisiz? Matn|Havola formatida yuboring, yoki /skip")


@router.message(AdminBroadcastStates.waiting_button, F.text)
async def broadcast_button(message: Message, state: FSMContext) -> None:
    button_text = button_url = None
    if message.text.strip() != "/skip" and "|" in message.text:
        button_text, button_url = [p.strip() for p in message.text.split("|", 1)]
    await state.update_data(button_text=button_text, button_url=button_url)
    await state.set_state(AdminBroadcastStates.confirm)

    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Yuborish", callback_data="adm:broadcast_confirm"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm:home"),
    ]])
 content_preview = data.get("text") or "(yo'q)"
    await message.answer(f"📨 Tayyor. Yuborilsinmi?\n\nMatn: {content_preview}", reply_markup=kb)   


@router.callback_query(AdminBroadcastStates.confirm, F.data == "adm:broadcast_confirm")
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await state.clear()

    result = await session.execute(select(User.id).where(User.is_banned.is_(False)))
    user_ids = [row[0] for row in result.all()]

    record = Broadcast(
        admin_id=callback.from_user.id, content_type=data["content_type"], text=data.get("text"),
        file_id=data.get("file_id"), button_text=data.get("button_text"), button_url=data.get("button_url"),
        status=BroadcastStatus.RUNNING, total_count=len(user_ids),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)

    progress_msg = await callback.message.answer("📨 Yuborilmoqda...\n░░░░░░░░░░ 0%")
    await callback.answer()

    kb = None
    if data.get("button_text") and data.get("button_url"):
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=data["button_text"], url=data["button_url"])]])

    sent, failed = 0, 0
    bot = callback.bot
    for i, user_id in enumerate(user_ids, start=1):
        try:
            if data["content_type"] == "text":
                await bot.send_message(user_id, data["text"] or "", reply_markup=kb)
            elif data["content_type"] == "photo":
                await bot.send_photo(user_id, data["file_id"], caption=data.get("text"), reply_markup=kb)
            elif data["content_type"] == "video":
                await bot.send_video(user_id, data["file_id"], caption=data.get("text"), reply_markup=kb)
            elif data["content_type"] == "animation":
                await bot.send_animation(user_id, data["file_id"], caption=data.get("text"), reply_markup=kb)
            sent += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            failed += 1
        except TelegramForbiddenError:
            failed += 1
        except Exception:
            failed += 1

        if i % 25 == 0 or i == len(user_ids):
            pct = int(i / len(user_ids) * 100) if user_ids else 100
            filled = pct // 10
            bar = "█" * filled + "░" * (10 - filled)
            try:
                await progress_msg.edit_text(f"📨 Yuborilmoqda...\n{bar} {pct}%")
            except Exception:
                pass
        await asyncio.sleep(0.05)  # basic flood protection

    record.sent_count, record.failed_count, record.status = sent, failed, BroadcastStatus.DONE
    await session.commit()
    await log_admin_action(session, callback.from_user.id, "broadcast_sent", f"sent={sent} failed={failed}")

    await progress_msg.edit_text(f"✅ Yakunlandi!\n\n📨 Yuborildi: {sent}\n❌ Xatolik: {failed}")
