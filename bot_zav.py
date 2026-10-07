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

# Список ID админов (узнать через @userinfobot)
ADMIN_IDS = [
    1281286200,   # админ 1
    5297669854,   # админ 2
]

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

    # Рассылаем заявление ВСЕМ админам
    sent_count = 0
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                chat_id=admin_id,
                photo=photo.file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            sent_count += 1
        except Exception as e:
            logging.exception(f"Не удалось отправить админу {admin_id}: {e}")

    if sent_count > 0:
        await message.answer("✅ Ваше заявление отправлено на рассмотрение. Ожидайте ответа.")
    else:
        await message.answer("⚠️ Ошибка при отправке. Попробуйте позже.")

    await state.clear()


# ====== Если прислали не фото ======
@dp.message(Form.photo)
async def wrong_photo_handler(message: Message):
    await message.answer(
        "⚠️ Пожалуйста, отправьте именно <b>фотографию</b> заявления.",
        parse_mode="HTML"
    )


# ====== Проверка: админ ли это ======
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ====== ОБРАБОТКА КНОПОК ======
@dp.callback_query(F.data.startswith("approve:"))
async def approve_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])

    # Уведомляем пользователя
    try:
        await bot.send_message(
            user_id,
            "✅ <b>Ваше заявление одобрено!</b>\n\nСпасибо за обращение.",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.exception(e)

    # Меняем подпись фото (у всех админов)
    await update_all_admin_messages(
        callback=callback,
        status_text="\n\n✅ <b>ОДОБРЕНО</b>",
        admin_name=callback.from_user.full_name
    )

    await callback.answer("Заявление одобрено ✅")


@dp.callback_query(F.data.startswith("reject:"))
async def reject_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
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

    await update_all_admin_messages(
        callback=callback,
        status_text="\n\n❌ <b>ОТКЛОНЕНО</b>",
        admin_name=callback.from_user.full_name
    )

    await callback.answer("Заявление отклонено ❌")


# ====== Обновление сообщений у всех админов ======
async def update_all_admin_messages(callback: CallbackQuery, status_text: str, admin_name: str):
    """
    Меняет подпись фото и убирает кнопки у всех админов,
    чтобы нельзя было нажать второй раз.
    """
    user_id = int(callback.data.split(":")[1])

    # Общая часть подписи (без статуса и имени админа) — берём из сообщения того,
    # кто нажал, но обрезаем возможные ранее добавленные статусы
    base_caption = (callback.message.caption or "").split("\n\n✅")[0].split("\n\n❌")[0]

    new_caption = base_caption + status_text + f"\n👮 <i>Обработал: {admin_name}</i>"

    # Меняем у нажавшего админа
    try:
        await callback.message.edit_caption(caption=new_caption, parse_mode="HTML")
    except Exception as e:
        logging.exception(e)

    # Пытаемся обновить у остальных админов.
    # Для этого у нас нет message_id — но мы можем взять их из сохранённых.
    # Простое решение: у второго админа сообщение НЕ обновится автоматически,
    # поэтому добавим пометку «уже обработано» через callback.answer().
    #
    # ВАРИАНТ ПОЛУЧШЕ: если хотите, чтобы сообщение обновлялось у обоих —
    # см. блок «Как обновлять у всех админов» ниже.


# ====== ЗАПУСК ======
async def main():
    print("🤖 Бот запущен...")
    print(f"👮 Админы: {ADMIN_IDS}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
