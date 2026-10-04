import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# ====== НАСТРОЙКИ ======
BOT_TOKEN = "ВАШ_ТОКЕН_БОТА"
ADMIN_ID = 1281286200                   # ваш Telegram ID

# ====== ЛОГИ ======
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ====== СОСТОЯНИЯ ======
class Form(StatesGroup):
    fio = State()
    photo = State()


# ====== /start ======
@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Здравствуйте!\n\n"
        "Этот бот принимает заявления с фотографией.\n\n"
        "Шаг 1️⃣ — напишите ваше <b>ФИО</b> (Фамилия Имя Отчество):",
        parse_mode="HTML"
    )
    await state.set_state(Form.fio)


# ====== /cancel ======
@dp.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено. Чтобы начать заново — /start")


# ====== ШАГ 1: ФИО ======
@dp.message(Form.fio, F.text)
async def fio_handler(message: Message, state: FSMContext):
    fio = message.text.strip()
    if len(fio) < 5 or len(fio.split()) < 2:
        await message.answer("⚠️ Пожалуйста, введите полное ФИО (минимум Имя и Фамилия).")
        return

    await state.update_data(fio=fio)
    await message.answer(
        "📸 Шаг 2️⃣ — отправьте <b>фотографию заявления</b>.",
        parse_mode="HTML"
    )
    await state.set_state(Form.photo)


# ====== ШАГ 2: Фото заявления ======
@dp.message(Form.photo, F.photo)
async def photo_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    fio = data["fio"]
    user = message.from_user

    username = f"@{user.username}" if user.username else "нет username"
    photo = message.photo[-1]

    caption = (
        "📨 <b>НОВОЕ ЗАЯВЛЕНИЕ</b>\n\n"
        f"👤 <b>ФИО:</b> {fio}\n"
        f"🆔 <b>Отправитель:</b> {user.full_name}\n"
        f"🔗 <b>Username:</b> {username}\n"
        f"📱 <b>ID:</b> <code>{user.id}</code>"
    )
    if message.caption:
        caption += f"\n\n💬 <b>Комментарий:</b> {message.caption}"

    # Кнопки Одобрить / Отклонить (в callback_data кладём ID юзера)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve:{user.id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{user.id}"),
            ]
        ]
    )

    try:
        await bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo.file_id,
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await message.answer("✅ Ваше заявление отправлено на рассмотрение. Ожидайте ответа.")
    except Exception as e:
        logging.exception(e)
        await message.answer("⚠️ Ошибка при отправке. Попробуйте позже.")

    await state.clear()


# ====== Если прислали не фото ======
@dp.message(Form.photo)
async def wrong_photo_handler(message: Message):
    await message.answer(
        "⚠️ Пожалуйста, отправьте именно <b>фотографию</b> заявления.",
        parse_mode="HTML"
    )


# ====== ОБРАБОТКА КНОПОК АДМИНА ======
@dp.callback_query(F.data.startswith("approve:"))
async def approve_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    try:
        await bot.send_message(
            user_id,
            "✅ <b>Ваше заявление одобрено!</b>\n\nСпасибо за обращение.",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.exception(e)
        await callback.answer("⚠️ Не удалось отправить сообщение пользователю", show_alert=True)
        return

    # Меняем подпись и убираем кнопки
    new_caption = (callback.message.caption or "") + "\n\n✅ <b>ОДОБРЕНО</b>"
    try:
        await callback.message.edit_caption(caption=new_caption, parse_mode="HTML")
    except Exception:
        pass

    await callback.answer("Заявление одобрено ✅")


@dp.callback_query(F.data.startswith("reject:"))
async def reject_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    try:
        await bot.send_message(
            user_id,
            "❌ <b>Ваше заявление отклонено.</b>\n\n"
            "Если считаете это ошибкой — свяжитесь с администратором.",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.exception(e)
        await callback.answer("⚠️ Не удалось отправить сообщение пользователю", show_alert=True)
        return

    new_caption = (callback.message.caption or "") + "\n\n❌ <b>ОТКЛОНЕНО</b>"
    try:
        await callback.message.edit_caption(caption=new_caption, parse_mode="HTML")
    except Exception:
        pass

    await callback.answer("Заявление отклонено ❌")


# ====== ЗАПУСК ======
async def main():
    print("🤖 Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
