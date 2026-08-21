from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot import texts, ui, views
from bot.api_client import ShadowTraderApi, TelegramNotLinkedError

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, api: ShadowTraderApi, state: FSMContext):
    await state.clear()
    await views.show_start(message, api, message.from_user.id)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(texts.CANCELLED)


# Кнопки постоянной клавиатуры приходят обычным текстом. Этот роутер подключён
# раньше FSM-хэндлеров, поэтому меню работает из любого шага диалога —
# незавершённый ввод (токен, почта и т.п.) при этом сбрасывается.

@router.message(Command("strategies"))
@router.message(F.text == ui.BTN_STRATEGIES)
async def cmd_strategies(message: Message, api: ShadowTraderApi, state: FSMContext):
    await state.clear()
    try:
        await views.show_strategies(message, api, message.from_user.id)
    except TelegramNotLinkedError:
        await message.answer(texts.NOT_LINKED)


@router.message(Command("bonds"))
@router.message(F.text == ui.BTN_BONDS)
async def cmd_bonds(message: Message, api: ShadowTraderApi, state: FSMContext):
    await state.clear()
    try:
        await views.show_accounts(message, api, message.from_user.id, purpose="bonds")
    except TelegramNotLinkedError:
        await message.answer(texts.NOT_LINKED)


@router.message(Command("settings"))
@router.message(F.text == ui.BTN_SETTINGS)
async def cmd_settings(message: Message, api: ShadowTraderApi, state: FSMContext):
    await state.clear()
    try:
        await views.show_settings(message, api, message.from_user.id)
    except TelegramNotLinkedError:
        await message.answer(texts.NOT_LINKED)
