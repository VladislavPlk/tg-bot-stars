import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties

# Настройки
BOT_TOKEN = "8087779382:AAGkNBW1_uMsI2IKNFQUTVEJ8ryALb1aED4"
CHANNEL_ID = -1002259252156  # ID канала для подписки
ADMIN_CHANNEL_ID = -1002395805594  # ID канала для заявок
ADMIN_IDS = [1098000915]  # ID администраторов

# Количество звезд за приглашение
REFERRAL_REWARD = 2

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()


# Кеш для username канала
channel_username_cache = None


# Инициализация БД
def init_db():
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()

    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance INTEGER DEFAULT 0,
        referrals INTEGER DEFAULT 0,
        invited_by INTEGER DEFAULT NULL
    )''')

    cur.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        status TEXT DEFAULT 'pending',
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()


init_db()


# Получение username канала
async def get_channel_username():
    global channel_username_cache
    if channel_username_cache is None:
        try:
            chat = await bot.get_chat(CHANNEL_ID)
            channel_username_cache = chat.username
        except Exception as e:
            logging.error(f"Ошибка получения username канала: {e}")
            channel_username_cache = "example_channel"  # Запасное значение
    return channel_username_cache


# Проверка подписки
async def check_subscription(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.error(f"Ошибка проверки подписки для {user_id}: {e}")
        return False


# Главное меню
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Профиль")],
            [KeyboardButton(text="🔗 Реферальная ссылка")],
            [KeyboardButton(text="💎 Вывод звёзд")],
            [KeyboardButton(text="📋 История выводов")]
        ],
        resize_keyboard=True
    )


# Меню вывода
def get_withdraw_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="15 звёзд"), KeyboardButton(text="25 звёзд")],
            [KeyboardButton(text="50 звёзд"), KeyboardButton(text="100 звёзд")],
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )


# Админ меню
def get_admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="📢 Рассылка")],
            [KeyboardButton(text="⭐ Начислить звёзды")],
            [KeyboardButton(text="📥 Заявки на вывод")],
            [KeyboardButton(text="🔙 Главное меню")]
        ],
        resize_keyboard=True
    )


# Меню отмены рассылки
def get_broadcast_cancel_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отменить рассылку")]
        ],
        resize_keyboard=True
    )


# Улучшенная реферальная система
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()

    # Обработка реферальной ссылки
    referrer_id = None
    if len(args) > 1:
        try:
            referrer_param = args[1]
            # Убираем возможные префиксы
            if referrer_param.startswith('ref'):
                referrer_param = referrer_param[3:]
            referrer_id = int(referrer_param)
        except ValueError:
            # Если не число, игнорируем
            pass

    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user_exists = cur.fetchone()

    if not user_exists:
        cur.execute("INSERT INTO users (user_id, username) VALUES (?, ?)",
                    (user_id, message.from_user.username))

        # Начисление звёзд рефереру (ИЗМЕНЕНО: 2 звезды вместо 1)
        if referrer_id and referrer_id != user_id:
            # Проверяем существует ли реферер
            cur.execute("SELECT * FROM users WHERE user_id = ?", (referrer_id,))
            if cur.fetchone():
                cur.execute("UPDATE users SET balance = balance + ?, referrals = referrals + 1 WHERE user_id = ?",
                            (REFERRAL_REWARD, referrer_id))
                cur.execute("UPDATE users SET invited_by = ? WHERE user_id = ?",
                            (referrer_id, user_id))

    conn.commit()
    conn.close()

    if not await check_subscription(user_id):
        keyboard = InlineKeyboardBuilder()

        # Получаем username канала корректно
        channel_username = await get_channel_username()
        subscribe_url = f"https://t.me/{channel_username}"

        keyboard.add(InlineKeyboardButton(text="📢 Подписаться на канал", url=subscribe_url))
        keyboard.add(InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription"))

        await message.answer(
            "📢 Для использования бота необходимо подписаться на наш канал!\n\n"
            "После подписки нажмите кнопку ниже:",
            reply_markup=keyboard.as_markup()
        )
    else:
        await message.answer(
            "🎉 Добро пожаловать! Выберите действие:",
            reply_markup=get_main_menu()
        )


@dp.callback_query(F.data == "check_subscription")
async def check_subscription_handler(callback: types.CallbackQuery):
    if await check_subscription(callback.from_user.id):
        await callback.message.edit_text(
            "✅ Отлично! Теперь вы можете использовать все функции бота:",
            reply_markup=None
        )
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=get_main_menu()
        )
    else:
        await callback.answer("Вы еще не подписались на канал!", show_alert=True)


@dp.message(F.text == "📊 Профиль")
async def profile_handler(message: types.Message):
    if not await check_subscription(message.from_user.id):
        await message.answer("Сначала подпишитесь на канал!")
        return

    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT balance, referrals FROM users WHERE user_id = ?",
                (message.from_user.id,))
    result = cur.fetchone()
    conn.close()

    if result:
        balance, referrals = result
        await message.answer(
            f"📊 Ваш профиль:\n\n"
            f"⭐ Звёзды: {balance}\n"
            f"👥 Рефералов: {referrals}\n"
            f"💎 Всего заработано с рефералов: {referrals * REFERRAL_REWARD} звёзд\n"
            f"💸 Доступно к выводу: {balance // 15 * 15}",
            reply_markup=get_main_menu()
        )
    else:
        await message.answer("❌ Ошибка получения данных профиля")


@dp.message(F.text == "🔗 Реферальная ссылка")
async def referral_handler(message: types.Message):
    if not await check_subscription(message.from_user.id):
        await message.answer("Сначала подпишитесь на канал!")
        return

    bot_info = await bot.get_me()
    user_id = message.from_user.id

    # Создаем несколько вариантов реферальных ссылок
    standard_link = f"https://t.me/{bot_info.username}?start={user_id}"
    #alt_link = f"https://t.me/{bot_info.username}?start=ref{user_id}"

    await message.answer(
        f"🔗 Ваши реферальные ссылки:\n\n"
        f"• Основная: {standard_link}\n"
       # f"• Для iOS: {alt_link}\n\n"
        f"📋 <b>Инструкция:</b>\n"
        f"• На Android: используйте первую ссылку\n"
        #f"• На iOS: попробуйте вторую ссылку\n\n"
        f"💎 <b>Вы получаете {REFERRAL_REWARD} звезды за каждого приглашенного друга!</b>",
    )


# Альтернативный метод для iOS - команда с реферальным кодом
@dp.message(Command("ref"))
async def ref_code_handler(message: types.Message):
    args = message.text.split()
    if len(args) > 1:
        # Обработка реферального кода через команду /ref
        try:
            referrer_id = int(args[1])
            user_id = message.from_user.id

            conn = sqlite3.connect('bot.db')
            cur = conn.cursor()

            # Проверяем не регистрировался ли уже пользователь
            cur.execute("SELECT invited_by FROM users WHERE user_id = ?", (user_id,))
            result = cur.fetchone()

            if result and result[0] is None:
                # Начисляем звёзды рефереру (ИЗМЕНЕНО: 2 звезды вместо 1)
                cur.execute("UPDATE users SET balance = balance + ?, referrals = referrals + 1 WHERE user_id = ?",
                            (REFERRAL_REWARD, referrer_id))
                cur.execute("UPDATE users SET invited_by = ? WHERE user_id = ?",
                            (referrer_id, user_id))
                conn.commit()

                await message.answer(
                    f"✅ Реферальный код применен! Вы помогли другу получить +{REFERRAL_REWARD} звезды!")
            else:
                await message.answer("ℹ️ Вы уже использовали реферальный код ранее.")

            conn.close()

        except ValueError:
            await message.answer("❌ Неверный формат реферального кода.")
    else:
        # Показываем реферальный код пользователя
        user_id = message.from_user.id
        await message.answer(
            f"📋 Ваш реферальный код: <code>{user_id}</code>\n\n"
            f"Друг может использовать команду:\n"
            f"<code>/ref {user_id}</code>\n\n"
            f"Или перейти по вашей реферальной ссылке из меню.\n\n"
            f"💎 За каждого приглашенного друга вы получите {REFERRAL_REWARD} звезды!"
        )


@dp.message(F.text == "💎 Вывод звёзд")
async def withdraw_handler(message: types.Message):
    if not await check_subscription(message.from_user.id):
        await message.answer("Сначала подпишитесь на канал!")
        return

    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,))
    result = cur.fetchone()
    conn.close()

    if result:
        balance = result[0]
        await message.answer(
            f"💰 Ваш баланс: {balance} звёзд\n\n"
            f"Выберите сумму для вывода:",
            reply_markup=get_withdraw_menu()
        )
    else:
        await message.answer("❌ Ошибка получения баланса")


@dp.message(F.text.in_(["15 звёзд", "25 звёзд", "50 звёзд", "100 звёзд"]))
async def withdraw_amount_handler(message: types.Message):
    amount_map = {
        "15 звёзд": 15,
        "25 звёзд": 25,
        "50 звёзд": 50,
        "100 звёзд": 100
    }

    amount = amount_map[message.text]
    user_id = message.from_user.id

    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()

    if not result:
        await message.answer("❌ Ошибка получения данных!")
        return

    balance = result[0]

    if balance < amount:
        await message.answer("❌ Недостаточно звёзд для вывода!", reply_markup=get_main_menu())
        return

    cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    cur.execute("INSERT INTO withdrawals (user_id, amount) VALUES (?, ?)", (user_id, amount))
    withdrawal_id = cur.lastrowid
    conn.commit()
    conn.close()

    # Отправка заявки в канал с кнопками подтверждения
    keyboard = InlineKeyboardBuilder()
    keyboard.add(
        InlineKeyboardButton(text="✅ Выплачено", callback_data=f"approve_{withdrawal_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{withdrawal_id}")
    )

    await bot.send_message(
        ADMIN_CHANNEL_ID,
        f"🆕 Новая заявка на вывод! (#{withdrawal_id})\n\n"
        f"👤 Пользователь: @{message.from_user.username or 'Нет username'}\n"
        f"🆔 ID: {user_id}\n"
        f"💎 Сумма: {amount} звёзд\n"
        f"📅 Время: {message.date.strftime('%Y-%m-%d %H:%M')}",
        reply_markup=keyboard.as_markup()
    )

    await message.answer(
        f"✅ Заявка на вывод {amount} звёзд создана!\n\n"
        f"Ожидайте подтверждения администратором.",
        reply_markup=get_main_menu()
    )


# Обработка подтверждения выплаты администратором
@dp.callback_query(F.data.startswith("approve_"))
async def approve_withdrawal_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен!", show_alert=True)
        return

    withdrawal_id = int(callback.data.split("_")[1])

    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()

    # Получаем информацию о заявке
    cur.execute("SELECT user_id, amount, status FROM withdrawals WHERE id = ?", (withdrawal_id,))
    withdrawal = cur.fetchone()

    if not withdrawal:
        await callback.answer("❌ Заявка не найдена!", show_alert=True)
        return

    user_id, amount, status = withdrawal

    if status != 'pending':
        await callback.answer("❌ Заявка уже обработана!", show_alert=True)
        return

    # Обновляем статус заявки
    cur.execute("UPDATE withdrawals SET status = 'approved' WHERE id = ?", (withdrawal_id,))

    # Получаем информацию о пользователе
    cur.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    user_result = cur.fetchone()
    username = user_result[0] if user_result else "Неизвестно"

    conn.commit()
    conn.close()

    # Уведомляем пользователя
    try:
        await bot.send_message(
            user_id,
            f"🎉 Ваша заявка на вывод {amount} звёзд подтверждена!\n\n"
            f"💎 Сумма: {amount} звёзд\n"
            f"✅ Статус: Выплачено\n\n"
            f"Спасибо за использование нашего бота! 🚀"
        )
    except Exception as e:
        logging.error(f"Не удалось уведомить пользователя {user_id}: {e}")

    # Обновляем сообщение в канале
    await callback.message.edit_text(
        f"✅ ВЫПЛАЧЕНО! (#{withdrawal_id})\n\n"
        f"👤 Пользователь: @{username}\n"
        f"🆔 ID: {user_id}\n"
        f"💎 Сумма: {amount} звёзд\n"
        f"👨‍💼 Подтвердил: @{callback.from_user.username}\n"
        f"📅 Время выплаты: {callback.message.date.strftime('%Y-%m-%d %H:%M')}",
        reply_markup=None
    )

    await callback.answer("✅ Выплата подтверждена!")


# Обработка отклонения выплаты администратором
@dp.callback_query(F.data.startswith("reject_"))
async def reject_withdrawal_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен!", show_alert=True)
        return

    withdrawal_id = int(callback.data.split("_")[1])

    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()

    # Получаем информацию о заявке
    cur.execute("SELECT user_id, amount, status FROM withdrawals WHERE id = ?", (withdrawal_id,))
    withdrawal = cur.fetchone()

    if not withdrawal:
        await callback.answer("❌ Заявка не найдена!", show_alert=True)
        return

    user_id, amount, status = withdrawal

    if status != 'pending':
        await callback.answer("❌ Заявка уже обработана!", show_alert=True)
        return

    # Возвращаем звезды пользователю и обновляем статус
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    cur.execute("UPDATE withdrawals SET status = 'rejected' WHERE id = ?", (withdrawal_id,))

    # Получаем информацию о пользователе
    cur.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    user_result = cur.fetchone()
    username = user_result[0] if user_result else "Неизвестно"

    conn.commit()
    conn.close()

    # Уведомляем пользователя
    try:
        await bot.send_message(
            user_id,
            f"❌ Ваша заявка на вывод {amount} звёзд отклонена.\n\n"
            f"💎 Сумма: {amount} звёзд\n"
            f"📝 Статус: Отклонено\n\n"
            f"Звёзды возвращены на ваш баланс."
        )
    except Exception as e:
        logging.error(f"Не удалось уведомить пользователя {user_id}: {e}")

    # Обновляем сообщение в канале
    await callback.message.edit_text(
        f"❌ ОТКЛОНЕНО! (#{withdrawal_id})\n\n"
        f"👤 Пользователь: @{username}\n"
        f"🆔 ID: {user_id}\n"
        f"💎 Сумма: {amount} звёзд\n"
        f"👨‍💼 Отклонил: @{callback.from_user.username}\n"
        f"📅 Время: {callback.message.date.strftime('%Y-%m-%d %H:%M')}",
        reply_markup=None
    )

    await callback.answer("❌ Выплата отклонена!")


@dp.message(F.text == "🔙 Назад")
async def back_handler(message: types.Message):
    await message.answer("Главное меню:", reply_markup=get_main_menu())


@dp.message(F.text == "📋 История выводов")
async def history_handler(message: types.Message):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT amount, status, date FROM withdrawals WHERE user_id = ? ORDER BY id DESC LIMIT 10",
                (message.from_user.id,))
    history = cur.fetchall()
    conn.close()

    if not history:
        await message.answer("📭 У вас еще не было заявок на вывод.", reply_markup=get_main_menu())
        return

    text = "📋 Последние 10 заявок:\n\n"
    for withdraw in history:
        status_emoji = "✅" if withdraw[1] == "approved" else "❌" if withdraw[1] == "rejected" else "⏳"
        status_text = "Выплачено" if withdraw[1] == "approved" else "Отклонено" if withdraw[
                                                                                       1] == "rejected" else "Ожидание"
        text += f"{status_emoji} {withdraw[0]} звёзд - {status_text} ({withdraw[2][:10]})\n"

    await message.answer(text, reply_markup=get_main_menu())


# Админ-панель
@dp.message(Command("admin"))
async def admin_handler(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Доступ запрещен!")
        return

    await message.answer("👨‍💻 Админ-панель:", reply_markup=get_admin_menu())


@dp.message(F.text == "📥 Заявки на вывод")
async def admin_withdrawals_handler(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()

    # Получаем ожидающие заявки
    cur.execute("""
        SELECT w.id, w.user_id, u.username, w.amount, w.date 
        FROM withdrawals w 
        LEFT JOIN users u ON w.user_id = u.user_id 
        WHERE w.status = 'pending' 
        ORDER BY w.date DESC
    """)
    pending_withdrawals = cur.fetchall()

    # Получаем статистику по заявкам
    cur.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'")
    pending_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'approved'")
    approved_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'rejected'")
    rejected_count = cur.fetchone()[0]

    conn.close()

    if not pending_withdrawals:
        await message.answer(
            f"📊 Статистика заявок:\n\n"
            f"⏳ Ожидающих: {pending_count}\n"
            f"✅ Выплаченных: {approved_count}\n"
            f"❌ Отклоненных: {rejected_count}\n\n"
            f"📭 Нет ожидающих заявок на вывод.",
            reply_markup=get_admin_menu()
        )
        return

    text = f"📥 Ожидающие заявки ({pending_count}):\n\n"
    for withdrawal in pending_withdrawals:
        withdrawal_id, user_id, username, amount, date = withdrawal
        text += f"#{withdrawal_id} - {amount} звёзд\n"
        text += f"👤 @{username or 'Нет username'} (ID: {user_id})\n"
        text += f"📅 {date[:16]}\n\n"

    await message.answer(text, reply_markup=get_admin_menu())


@dp.message(F.text == "📊 Статистика")
async def admin_stats_handler(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]
    cur.execute("SELECT SUM(balance) FROM users")
    total_stars = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'")
    pending_withdrawals = cur.fetchone()[0]
    cur.execute("SELECT SUM(referrals) FROM users")
    total_referrals = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'approved'")
    approved_withdrawals = cur.fetchone()[0]
    cur.execute("SELECT SUM(amount) FROM withdrawals WHERE status = 'approved'")
    total_paid = cur.fetchone()[0] or 0
    conn.close()

    await message.answer(
        f"📊 Статистика бота:\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"💎 Всего звёзд в системе: {total_stars}\n"
        f"📥 Ожидающих выводов: {pending_withdrawals}\n"
        f"✅ Выплаченных выводов: {approved_withdrawals}\n"
        f"💰 Всего выплачено: {total_paid} звёзд\n"
        f"👥 Всего рефералов: {total_referrals}\n"
        f"💎 Выдано за рефералов: {total_referrals * REFERRAL_REWARD} звёзд",
        reply_markup=get_admin_menu()
    )


@dp.message(F.text == "📢 Рассылка")
async def admin_broadcast_handler(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer(
        "📢 Отправьте сообщение для рассылки всем пользователям:\n\n"
        "Поддерживается HTML-разметка.\n"
        "Для отмены нажмите кнопку ниже:",
        reply_markup=get_broadcast_cancel_menu()
    )
    await dp.storage.set_state(message.from_user.id, "admin_broadcast")


@dp.message(F.text == "❌ Отменить рассылку")
async def cancel_broadcast_handler(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    await dp.storage.set_state(message.from_user.id, None)
    await message.answer(
        "✅ Рассылка отменена!",
        reply_markup=get_admin_menu()
    )


@dp.message(F.text == "⭐ Начислить звёзды")
async def admin_add_handler(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer(
        "Отправьте данные в формате:\n"
        "<code>@username количество</code>\n"
        "или\n"
        "<code>user_id количество</code>\n\n"
        "Пример: <code>123456789 10</code>",
        reply_markup=get_admin_menu()
    )
    await dp.storage.set_state(message.from_user.id, "admin_add_stars")


@dp.message(F.text == "🔙 Главное меню")
async def admin_back_handler(message: types.Message):
    await message.answer("Главное меню:", reply_markup=get_main_menu())


# Обработчик рассылки и начисления звёзд
@dp.message(F.text, F.from_user.id.in_(ADMIN_IDS))
async def admin_actions_handler(message: types.Message):
    state = await dp.storage.get_state(message.from_user.id)

    if state == "admin_broadcast":
        # Начинаем рассылку
        conn = sqlite3.connect('bot.db')
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users")
        users = cur.fetchall()
        conn.close()

        total_users = len(users)
        successful = 0
        failed = 0

        status_message = await message.answer(
            f"📤 Начинаем рассылку...\n"
            f"Всего пользователей: {total_users}\n"
            f"✅ Успешно: 0\n"
            f"❌ Ошибок: 0"
        )

        for user in users:
            user_id = user[0]
            try:
                await bot.send_message(user_id, message.text)
                successful += 1
            except Exception as e:
                failed += 1

            if (successful + failed) % 10 == 0:
                try:
                    await status_message.edit_text(
                        f"📤 Рассылка...\n"
                        f"Всего пользователей: {total_users}\n"
                        f"✅ Успешно: {successful}\n"
                        f"❌ Ошибок: {failed}\n"
                        f"📊 Прогресс: {successful + failed}/{total_users}"
                    )
                except:
                    pass

        await status_message.edit_text(
            f"✅ Рассылка завершена!\n\n"
            f"📊 Итоги:\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"✅ Успешно отправлено: {successful}\n"
            f"❌ Не удалось отправить: {failed}"
        )

        await dp.storage.set_state(message.from_user.id, None)
        await message.answer("Рассылка завершена!", reply_markup=get_admin_menu())

    elif state == "admin_add_stars":
        try:
            data = message.text.split()
            if len(data) != 2:
                raise ValueError

            identifier = data[0]
            amount = int(data[1])

            conn = sqlite3.connect('bot.db')
            cur = conn.cursor()

            if identifier.startswith('@'):
                cur.execute("UPDATE users SET balance = balance + ? WHERE username = ?",
                            (amount, identifier[1:]))
                target = identifier
            else:
                cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?",
                            (amount, int(identifier)))
                target = f"ID {identifier}"

            conn.commit()
            conn.close()

            await message.answer(f"✅ {amount} звёзд начислено пользователю {target}!")
            await dp.storage.set_state(message.from_user.id, None)

        except Exception as e:
            await message.answer("❌ Ошибка формата! Используйте: @username количество или user_id количество")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())