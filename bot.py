import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from datetime import datetime

TOKEN = "7332518920:AAEWuJsLMhkl-e89IvqK2WF1iJyizLNomfE"
ADMIN_ID = 1256548616  # Ваш Telegram ID
DB_PATH = "shop.db"

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class CategoryState(StatesGroup):
    name = State()

class ProductState(StatesGroup):
    name = State()
    description = State()
    content = State()
    price = State()
    quantity = State()
    category_id = State()

def setup_db():
    with sqlite3.connect(DB_PATH) as db:
        # Таблица категорий
        db.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            )
        """)
        # Таблица товаров
        db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL, -- Описание товара
                content TEXT NOT NULL,     -- Содержимое товара
                price INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                category_id INTEGER,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                registration_date TEXT,
                main_balance INTEGER DEFAULT 0,
                partner_balance INTEGER DEFAULT 0,
                total_purchases INTEGER DEFAULT 0,
                referrer_id INTEGER DEFAULT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                purchase_date TEXT NOT NULL,
                price INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        """)
        db.commit()

def ensure_quantity_column():
    with sqlite3.connect(DB_PATH) as db:
        # Проверяем, существует ли колонка quantity
        cursor = db.execute("PRAGMA table_info(products);")
        columns = [col[1] for col in cursor.fetchall()]
        if "quantity" not in columns:
            # Если нет, добавляем её
            db.execute("""
                ALTER TABLE products ADD COLUMN quantity INTEGER DEFAULT 0
            """)
            db.commit()

#--------<Генерация реферальной ссылки>
def generate_referral_link(user_id):
    return f"https://t.me/FlexStoreBot?start={user_id}"
#--------

# Главное меню
def get_main_menu(is_admin=False):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📦  Каталог товаров", callback_data="catalog"),
        InlineKeyboardButton("💰  Пополнить баланс", callback_data="top_up"),
        InlineKeyboardButton("👤  Мой профиль", callback_data="profile"),
        InlineKeyboardButton("📩  Связаться", callback_data="contact")
    )
    if is_admin:  # Добавляем кнопку "Админ" только для администратора
        markup.add(InlineKeyboardButton("🔑 Админ", callback_data="admin_panel"))
    return markup

# Меню реферальной программы
@dp.callback_query_handler(lambda c: c.data == "referral_program")
async def referral_program(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    referral_link = generate_referral_link(user_id)
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
    )

    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute("""
            SELECT id, username, total_purchases
            FROM users WHERE referrer_id = ?
        """, (user_id,))
        referrals = cursor.fetchall()

    referral_text = f"🤝 Ваша реферальная ссылка:\n{referral_link}\n\n"
    if referrals:
        total_earnings = 0
        referral_text += "👥 Приглашённые пользователи:\n"
        for ref in referrals:
            ref_id, ref_username, ref_purchases = ref
            referral_text += f"- {ref_username} (ID: {ref_id}), потрачено: {ref_purchases} ₽\n"
            total_earnings += ref_purchases

        referral_text += f"\n💰 Общая сумма заработка с рефералов: {total_earnings} ₽"
    else:
        referral_text += "У вас пока нет рефералов."

    await callback_query.message.edit_text(referral_text, reply_markup=markup)
    await callback_query.answer()

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Без имени"
    registration_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Проверяем, есть ли реферальный код
    referrer_id = None
    args = message.get_args()
    if args.isdigit():
        referrer_id = int(args)

    # Добавляем пользователя в базу, если его там нет
    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not cursor.fetchone():
            db.execute("""
                INSERT INTO users (id, username, registration_date, referrer_id)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, registration_date, referrer_id))
            db.commit()

    is_admin = user_id == ADMIN_ID
    if is_admin:
        await message.answer("Добро пожаловать, администратор!", reply_markup=get_main_menu(is_admin=True))
    else:
        await message.answer("Добро пожаловать в магазин!", reply_markup=get_main_menu())

# Обработчик профиля
@dp.callback_query_handler(lambda c: c.data == "profile")
async def profile_menu(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    # Извлекаем данные пользователя
    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute("""
            SELECT username, registration_date, main_balance, partner_balance, total_purchases
            FROM users WHERE id = ?
        """, (user_id,))
        user = cursor.fetchone()

    if user:
        username, reg_date, main_balance, partner_balance, total_purchases = user
        profile_text = (
            f"👤 Профиль\n\n"
            f"Ник: {username}\n"
            f"ID: {user_id}\n"
            f"Регистрация: {reg_date}\n\n"
            f"💳 Основной баланс: {main_balance} ₽\n"
            f"🤝 Партнёрский баланс: {partner_balance} ₽\n\n"
            f"📊 Статистика\n"
            f"Всего покупок: {total_purchases}"
        )
    else:
        profile_text = "Ошибка: пользователь не найден."

    # Кнопки профиля
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🛍️ Мои заказы", callback_data="my_orders"),
        InlineKeyboardButton("💳 Пополнить", callback_data="top_up"),
        InlineKeyboardButton("🤝 Реферальная программа", callback_data="referral_program"),
        InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
    )

    await callback_query.message.edit_text(profile_text, reply_markup=markup)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "my_orders")
async def my_orders(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    markup = InlineKeyboardMarkup(row_width=1)
    
    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute("""
            SELECT id, product_id, price, purchase_date FROM orders WHERE user_id = ?
        """, (user_id,))
        orders = cursor.fetchall()
    
    if orders:
        total_purchases = 0
        for order in orders:
            order_id, product_id, price, purchase_date = order
            total_purchases += price
            cursor = db.execute("""
                SELECT name FROM products WHERE id = ?
            """, (product_id,))
            product_name = cursor.fetchone()[0]
            markup.add(InlineKeyboardButton(product_name, callback_data=f"order_{order_id}"))
        
        # Добавляем информацию о покупках
        await callback_query.message.edit_text(
            f"📦 Мои заказы\n\n"
            f"Количество покупок: {len(orders)}\n"
            f"Общая сумма: {total_purchases} ₽\n\n"
            "Выберите заказ, чтобы увидеть подробности:",
            reply_markup=markup
        )
    else:
        await callback_query.message.edit_text("У вас нет заказов.")
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("order_"))
async def order_details(callback_query: types.CallbackQuery):
    order_id = int(callback_query.data.split("_")[1])
    user_id = callback_query.from_user.id

    with sqlite3.connect(DB_PATH) as db:
        # Получаем данные о заказе
        cursor = db.execute("""
            SELECT product_id, price, purchase_date FROM orders WHERE id = ? AND user_id = ?
        """, (order_id, user_id))
        order = cursor.fetchone()

        if order:
            product_id, price, purchase_date = order
            # Получаем данные о товаре
            cursor = db.execute("""
                SELECT name, description, content FROM products WHERE id = ?
            """, (product_id,))
            product = cursor.fetchone()

            if product:
                product_name, product_description, product_content = product
                await callback_query.message.edit_text(
                    f"📦 Заказ: {product_name}\n\n"
                    f"Описание: {product_description}\n"
                    f"Содержимое: {product_content}\n"
                    f"Цена: {price} ₽\n"
                    f"Дата покупки: {purchase_date}\n\n"
                    "Выберите действие:",
                    reply_markup=InlineKeyboardMarkup().add(
                        InlineKeyboardButton("⬅️ Назад", callback_data="my_orders"),
                        InlineKeyboardButton("Главное меню", callback_data="back_to_main")
                    )
                )
        else:
            await callback_query.message.edit_text("Заказ не найден.")
    await callback_query.answer()

# Админ-панель
@dp.callback_query_handler(lambda c: c.data == "admin_panel")
async def admin_panel(callback_query: types.CallbackQuery):
    if callback_query.from_user.id == ADMIN_ID:
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("➕ Добавить товар", callback_data="add_product"),
            InlineKeyboardButton("❌ Удалить товар", callback_data="delete_product"),
            InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"),
            InlineKeyboardButton("➕ Добавить категорию", callback_data="add_category"),
        )
        await callback_query.message.edit_text("Админ-панель:", reply_markup=markup)
    await callback_query.answer()

# Возврат в главное меню
@dp.callback_query_handler(lambda c: c.data == "back_to_main")
async def back_to_main_menu(callback_query: types.CallbackQuery):
    is_admin = callback_query.from_user.id == ADMIN_ID
    await callback_query.message.edit_text("Главное меню:", reply_markup=get_main_menu(is_admin=is_admin))
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "catalog")
async def catalog_menu(callback_query: types.CallbackQuery):
    markup = InlineKeyboardMarkup(row_width=2)
    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute("SELECT id, name FROM categories")
        categories = cursor.fetchall()

    if categories:
        for category in categories:
            markup.add(InlineKeyboardButton(category[1], callback_data=f"category_{category[0]}"))
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
        await callback_query.message.edit_text("Выберите категорию:", reply_markup=markup)
    else:
        await callback_query.message.edit_text(
            "Каталог пуст. Добавьте категории.",
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
        )
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("category_"))
async def show_category(callback_query: types.CallbackQuery):
    category_id = int(callback_query.data.split("_")[1])
    markup = InlineKeyboardMarkup(row_width=2)
    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute("""
            SELECT id, name, price, quantity
            FROM products
            WHERE category_id = ? AND quantity > 0
        """, (category_id,))
        products = cursor.fetchall()

    if products:
        for product in products:
            button_text = f"{product[1]} - {product[2]} ₽ (осталось: {product[3]})"
            markup.add(InlineKeyboardButton(button_text, callback_data=f"buy_{product[0]}"))
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="catalog"))
        await callback_query.message.edit_text("Выберите товар:", reply_markup=markup)
    else:
        await callback_query.message.edit_text(
            "В категории нет доступных товаров.",
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Назад", callback_data="catalog"))
        )
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("buy_"))
async def buy_product_preview(callback_query: types.CallbackQuery):
    product_id = int(callback_query.data.split("_")[1])

    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute("""
            SELECT name, description, price FROM products WHERE id = ?
        """, (product_id,))
        product = cursor.fetchone()

    if product:
        product_name, product_description, product_price = product
        markup = InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("Купить", callback_data=f"confirm_buy_{product_id}"),
            InlineKeyboardButton("Назад", callback_data="catalog")
        )
        await callback_query.message.edit_text(
            f"Товар: {product_name}\n\nОписание: {product_description}\nЦена: {product_price} ₽\n\nПодтверждаете покупку?",
            reply_markup=markup
        )
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_buy_"))
async def confirm_buy_product(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    product_id = int(callback_query.data.split("_")[2])

    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute("""
            SELECT name, price, content, quantity FROM products WHERE id = ?
        """, (product_id,))
        product = cursor.fetchone()

        cursor = db.execute("""
            SELECT main_balance FROM users WHERE id = ?
        """, (user_id,))
        user_balance = cursor.fetchone()[0]

    if product and user_balance is not None:
        product_name, product_price, product_content, product_quantity = product

        if user_balance >= product_price and product_quantity > 0:
            new_balance = user_balance - product_price
            with sqlite3.connect(DB_PATH) as db:
                db.execute("""
                    UPDATE users SET main_balance = ? WHERE id = ?
                """, (new_balance, user_id))
                db.execute("""
                    UPDATE products SET quantity = ? WHERE id = ?
                """, (product_quantity - 1, product_id))
                db.execute("""
                    INSERT INTO orders (user_id, product_id, purchase_date, price)
                    VALUES (?, ?, ?, ?)
                """, (user_id, product_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), product_price))
                db.commit()

            await callback_query.message.edit_text(
                f"✅ Покупка успешна!\n\nВы купили: {product_name}\nОстаток на балансе: {new_balance} ₽"
            )
            await bot.send_message(user_id, f"Ваш товар:\n{product_content}")
        else:
            await callback_query.message.edit_text("❌ Недостаточно средств или товар закончился.")
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "add_category")
async def add_category(callback_query: types.CallbackQuery):
    if callback_query.from_user.id == ADMIN_ID:
        await callback_query.message.answer("Введите название категории:")
        await CategoryState.name.set()
    await callback_query.answer()

@dp.message_handler(state=CategoryState.name)
async def process_category_name(message: types.Message, state: FSMContext):
    category_name = message.text
    with sqlite3.connect(DB_PATH) as db:
        db.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
        db.commit()
    await message.answer("Категория успешно добавлена!")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "add_product")
async def add_product(callback_query: types.CallbackQuery):
    if callback_query.from_user.id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        with sqlite3.connect(DB_PATH) as db:
            cursor = db.execute("SELECT id, name FROM categories")
            for category in cursor.fetchall():
                markup.add(InlineKeyboardButton(category[1], callback_data=f"select_category_{category[0]}"))
        await callback_query.message.answer("Выберите категорию для товара:", reply_markup=markup)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("select_category_"))
async def select_category(callback_query: types.CallbackQuery, state: FSMContext):
    category_id = int(callback_query.data.split("_")[2])
    await state.update_data(category_id=category_id)
    await callback_query.message.answer("Введите название товара:")
    await ProductState.name.set()

# Добавление товара
@dp.message_handler(state=ProductState.name)
async def process_product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите описание товара:")
    await ProductState.description.set()

@dp.message_handler(state=ProductState.description)
async def process_product_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Введите содержимое товара (текст или файл):")
    await ProductState.content.set()

@dp.message_handler(state=ProductState.content, content_types=[types.ContentType.TEXT, types.ContentType.DOCUMENT, types.ContentType.PHOTO])
async def process_product_content(message: types.Message, state: FSMContext):
    if message.content_type == types.ContentType.TEXT:
        content = message.text
    elif message.content_type == types.ContentType.DOCUMENT:
        # Сохранение файла
        content = message.document.file_id
    elif message.content_type == types.ContentType.PHOTO:
        # Сохранение фото
        content = message.photo[-1].file_id

    await state.update_data(content=content)
    await message.answer("Введите цену товара:")
    await ProductState.price.set()

@dp.message_handler(state=ProductState.price)
async def process_product_price(message: types.Message, state: FSMContext):
    try:
        price = int(message.text)
        await state.update_data(price=price)
        await message.answer("Введите количество товара:")
        await ProductState.quantity.set()
    except ValueError:
        await message.answer("Цена должна быть числом. Попробуйте снова.")

@dp.message_handler(state=ProductState.quantity)
async def process_product_quantity(message: types.Message, state: FSMContext):
    try:
        quantity = int(message.text)
        data = await state.get_data()
        name = data["name"]
        description = data["description"]
        content = data["content"]
        price = data["price"]
        category_id = data["category_id"]

        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                INSERT INTO products (name, description, content, price, quantity, category_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, description, content, price, quantity, category_id))
            db.commit()

        await message.answer("Товар успешно добавлен!", reply_markup=get_main_menu())
    except ValueError:
        await message.answer("Количество должно быть числом. Попробуйте снова.")
    finally:
        await state.finish()

# Удаление товара
@dp.callback_query_handler(lambda c: c.data == "delete_product")
async def delete_product(callback_query: types.CallbackQuery):
    if callback_query.from_user.id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        with sqlite3.connect(DB_PATH) as db:
            cursor = db.execute("SELECT id, name FROM products")
            for row in cursor.fetchall():
                markup.add(InlineKeyboardButton(row[1], callback_data=f"delete_{row[0]}"))
        markup.add(InlineKeyboardButton("Отмена", callback_data="cancel"))
        await callback_query.message.answer("Выберите товар для удаления:", reply_markup=markup)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("delete_"))
async def delete_selected_product(callback_query: types.CallbackQuery):
    product_id = int(callback_query.data.split("_")[1])
    with sqlite3.connect(DB_PATH) as db:
        db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        db.commit()
    await callback_query.message.answer("Товар удалён!", reply_markup=get_main_menu())
    await callback_query.answer()

# Отмена действия
@dp.callback_query_handler(lambda c: c.data == "cancel")
async def cancel_action(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Действие отменено.", reply_markup=get_main_menu())
    await callback_query.answer()

# Запуск бота
if __name__ == "__main__":
    setup_db()
    ensure_quantity_column()
    executor.start_polling(dp, skip_updates=True)
