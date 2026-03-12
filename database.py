import sqlite3
import datetime
import base64
import asyncio
from typing import Optional, List, Tuple

# Глобальная переменная для задач фоновых проверок
_background_tasks = []

def init_db():
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()

    # ---------- Пользователи ----------
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            phone TEXT,
            full_name TEXT,
            referrer_id INTEGER DEFAULT NULL,
            balance INTEGER DEFAULT 0,
            reliability_rating INTEGER DEFAULT 100,
            blocked_until TIMESTAMP DEFAULT NULL,
            yookassa_payment_id TEXT DEFAULT NULL,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(referrer_id) REFERENCES users(user_id)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER NOT NULL,
            role TEXT CHECK(role IN ('user', 'reseller')),
            PRIMARY KEY (user_id, role),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS reseller_requests (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ---------- Категории, бренды, модели, характеристики ----------
    cur.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS brands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            name TEXT,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_id INTEGER,
            name TEXT,
            FOREIGN KEY(brand_id) REFERENCES brands(id)
        )
    ''')

    # Характеристики: цвет, память и т.д.
    cur.execute('''
        CREATE TABLE IF NOT EXISTS specs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            spec_type TEXT,  -- например, 'color', 'storage'
            spec_value TEXT,
            FOREIGN KEY(model_id) REFERENCES models(id)
        )
    ''')

    # ---------- Заявки на выкуп ----------
    cur.execute('''
        CREATE TABLE IF NOT EXISTS buyout_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category_id INTEGER,
            brand_id INTEGER,
            model_id INTEGER,
            specs TEXT,  -- строка с ID характеристик через запятую
            description TEXT,
            condition TEXT,
            photo_file_ids TEXT,
            video_file_id TEXT,
            desired_price INTEGER,
            battery_cycles INTEGER DEFAULT NULL,
            max_capacity INTEGER DEFAULT NULL,
            display_replaced TEXT DEFAULT NULL,
            defects TEXT DEFAULT NULL,
            accessories TEXT DEFAULT NULL,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed', 'cancelled', 'expired')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            winner_id INTEGER DEFAULT NULL,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            reseller_id INTEGER,
            price INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notified BOOLEAN DEFAULT 0,
            FOREIGN KEY(request_id) REFERENCES buyout_requests(id),
            FOREIGN KEY(reseller_id) REFERENCES users(user_id)
        )
    ''')

    # ---------- Объявления перекупов ----------
    cur.execute('''
        CREATE TABLE IF NOT EXISTS resale_lots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reseller_id INTEGER,
            category_id INTEGER,
            brand_id INTEGER,
            model_id INTEGER,
            specs TEXT,
            description TEXT,
            condition TEXT,
            photo_file_ids TEXT,
            video_file_id TEXT,
            price INTEGER,
            battery_cycles INTEGER DEFAULT NULL,
            max_capacity INTEGER DEFAULT NULL,
            display_replaced TEXT DEFAULT NULL,
            defects TEXT DEFAULT NULL,
            accessories TEXT DEFAULT NULL,
            views INTEGER DEFAULT 0,
            offers_count INTEGER DEFAULT 0,
            reserve_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'moderation' CHECK(status IN ('moderation', 'active', 'reserved', 'sold', 'rejected')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            buyer_id INTEGER DEFAULT NULL,
            sold_at TIMESTAMP DEFAULT NULL,
            FOREIGN KEY(reseller_id) REFERENCES users(user_id),
            FOREIGN KEY(buyer_id) REFERENCES users(user_id)
        )
    ''')

    # ---------- Отзывы ----------
    cur.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL,
            buyer_id INTEGER NOT NULL,
            lot_id INTEGER NOT NULL,
            rating INTEGER CHECK(rating >= 1 AND rating <= 5),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(seller_id) REFERENCES users(user_id),
            FOREIGN KEY(buyer_id) REFERENCES users(user_id),
            FOREIGN KEY(lot_id) REFERENCES resale_lots(id)
        )
    ''')

    # ---------- Подписки ----------
    cur.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category_id INTEGER DEFAULT NULL,
            notify_on_new BOOLEAN DEFAULT 1,
            notify_on_price_drop BOOLEAN DEFAULT 0,
            notify_on_auction_end BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, category_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )
    ''')

    # ---------- Рефералы ----------
    cur.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL UNIQUE,
            reward_given BOOLEAN DEFAULT 0,
            reward_amount INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(referrer_id) REFERENCES users(user_id),
            FOREIGN KEY(referred_id) REFERENCES users(user_id)
        )
    ''')

    # ---------- Избранное ----------
    cur.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            lot_id INTEGER NOT NULL,
            price_at_add INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, lot_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(lot_id) REFERENCES resale_lots(id)
        )
    ''')

    # ---------- Торг (предложения цены) ----------
    cur.execute('''
        CREATE TABLE IF NOT EXISTS price_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_id INTEGER NOT NULL,
            buyer_id INTEGER NOT NULL,
            price INTEGER NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'accepted', 'rejected')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(lot_id) REFERENCES resale_lots(id),
            FOREIGN KEY(buyer_id) REFERENCES users(user_id)
        )
    ''')

    # ---------- Логирование ----------
    cur.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')

    # ---------- Жалобы ----------
    cur.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complainant_id INTEGER NOT NULL,
            lot_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'reviewed', 'rejected')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(complainant_id) REFERENCES users(user_id),
            FOREIGN KEY(lot_id) REFERENCES resale_lots(id)
        )
    ''')

    # ---------- Поддержка ----------
    cur.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            replied BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')

    conn.commit()
    conn.close()

    add_default_categories()
    def populate_popular_data():
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()

    # Убедимся, что категория "Смартфоны" существует (обычно id=2)
    cur.execute("SELECT id FROM categories WHERE name='Смартфоны'")
    row = cur.fetchone()
    if not row:
        # Если категории нет, создаём
        cur.execute("INSERT INTO categories (name) VALUES ('Смартфоны')")
        smartphone_cat_id = cur.lastrowid
    else:
        smartphone_cat_id = row[0]

    # Добавляем бренд Apple
    cur.execute("INSERT OR IGNORE INTO brands (category_id, name) VALUES (?, 'Apple')", (smartphone_cat_id,))
    apple_id = cur.execute("SELECT id FROM brands WHERE name='Apple' AND category_id=?", (smartphone_cat_id,)).fetchone()[0]

    # Словарь моделей iPhone: (название модели, список цветов, список объёмов памяти)
    iphone_models = {
        "iPhone SE (1-го поколения)": (["Серый космос", "Серебристый", "Золотой", "Розовое золото"], ["16GB", "32GB", "64GB", "128GB"]),
        "iPhone SE (2-го поколения)": (["Чёрный", "Белый", "Красный (PRODUCT)RED"], ["64GB", "128GB", "256GB"]),
        "iPhone SE (3-го поколения)": (["Полночь", "Сияющая звезда", "Красный (PRODUCT)RED"], ["64GB", "128GB", "256GB"]),
        "iPhone 6": (["Серый космос", "Серебристый", "Золотой"], ["16GB", "32GB", "64GB", "128GB"]),
        "iPhone 6 Plus": (["Серый космос", "Серебристый", "Золотой"], ["16GB", "32GB", "64GB", "128GB"]),
        "iPhone 6s": (["Серый космос", "Серебристый", "Золотой", "Розовое золото"], ["16GB", "32GB", "64GB", "128GB"]),
        "iPhone 6s Plus": (["Серый космос", "Серебристый", "Золотой", "Розовое золото"], ["16GB", "32GB", "64GB", "128GB"]),
        "iPhone 7": (["Чёрный", "Чёрный оникс", "Серебристый", "Золотой", "Розовое золото", "Красный (PRODUCT)RED"], ["32GB", "128GB", "256GB"]),
        "iPhone 7 Plus": (["Чёрный", "Чёрный оникс", "Серебристый", "Золотой", "Розовое золото", "Красный (PRODUCT)RED"], ["32GB", "128GB", "256GB"]),
        "iPhone 8": (["Серый космос", "Серебристый", "Золотой", "Красный (PRODUCT)RED"], ["64GB", "128GB", "256GB"]),
        "iPhone 8 Plus": (["Серый космос", "Серебристый", "Золотой", "Красный (PRODUCT)RED"], ["64GB", "128GB", "256GB"]),
        "iPhone X": (["Серый космос", "Серебристый"], ["64GB", "256GB"]),
        "iPhone XR": (["Чёрный", "Белый", "Синий", "Жёлтый", "Коралловый", "Красный (PRODUCT)RED"], ["64GB", "128GB", "256GB"]),
        "iPhone XS": (["Серый космос", "Серебристый", "Золотой"], ["64GB", "256GB", "512GB"]),
        "iPhone XS Max": (["Серый космос", "Серебристый", "Золотой"], ["64GB", "256GB", "512GB"]),
        "iPhone 11": (["Чёрный", "Белый", "Фиолетовый", "Жёлтый", "Зелёный", "Красный (PRODUCT)RED"], ["64GB", "128GB", "256GB"]),
        "iPhone 11 Pro": (["Серый космос", "Серебристый", "Золотой", "Тёмно-зелёный"], ["64GB", "256GB", "512GB"]),
        "iPhone 11 Pro Max": (["Серый космос", "Серебристый", "Золотой", "Тёмно-зелёный"], ["64GB", "256GB", "512GB"]),
        "iPhone 12 mini": (["Чёрный", "Белый", "Красный (PRODUCT)RED", "Зелёный", "Синий", "Фиолетовый"], ["64GB", "128GB", "256GB"]),
        "iPhone 12": (["Чёрный", "Белый", "Красный (PRODUCT)RED", "Зелёный", "Синий", "Фиолетовый"], ["64GB", "128GB", "256GB"]),
        "iPhone 12 Pro": (["Серебристый", "Графитовый", "Золотой", "Тихоокеанский синий"], ["128GB", "256GB", "512GB"]),
        "iPhone 12 Pro Max": (["Серебристый", "Графитовый", "Золотой", "Тихоокеанский синий"], ["128GB", "256GB", "512GB"]),
        "iPhone 13 mini": (["Полночь", "Сияющая звезда", "Синий", "Розовый", "Красный (PRODUCT)RED", "Зелёный"], ["128GB", "256GB", "512GB"]),
        "iPhone 13": (["Полночь", "Сияющая звезда", "Синий", "Розовый", "Красный (PRODUCT)RED", "Зелёный"], ["128GB", "256GB", "512GB"]),
        "iPhone 13 Pro": (["Графитовый", "Золотой", "Серебристый", "Небесно-синий", "Альпийский зелёный"], ["128GB", "256GB", "512GB", "1TB"]),
        "iPhone 13 Pro Max": (["Графитовый", "Золотой", "Серебристый", "Небесно-синий", "Альпийский зелёный"], ["128GB", "256GB", "512GB", "1TB"]),
        "iPhone 14": (["Полночь", "Сияющая звезда", "Синий", "Фиолетовый", "Красный (PRODUCT)RED", "Жёлтый"], ["128GB", "256GB", "512GB"]),
        "iPhone 14 Plus": (["Полночь", "Сияющая звезда", "Синий", "Фиолетовый", "Красный (PRODUCT)RED", "Жёлтый"], ["128GB", "256GB", "512GB"]),
        "iPhone 14 Pro": (["Серебристый", "Золотой", "Тёмно-фиолетовый", "Космический чёрный"], ["128GB", "256GB", "512GB", "1TB"]),
        "iPhone 14 Pro Max": (["Серебристый", "Золотой", "Тёмно-фиолетовый", "Космический чёрный"], ["128GB", "256GB", "512GB", "1TB"]),
        "iPhone 15": (["Чёрный", "Синий", "Зелёный", "Жёлтый", "Розовый"], ["128GB", "256GB", "512GB"]),
        "iPhone 15 Plus": (["Чёрный", "Синий", "Зелёный", "Жёлтый", "Розовый"], ["128GB", "256GB", "512GB"]),
        "iPhone 15 Pro": (["Чёрный титан", "Белый титан", "Синий титан", "Натуральный титан"], ["128GB", "256GB", "512GB", "1TB"]),
        "iPhone 15 Pro Max": (["Чёрный титан", "Белый титан", "Синий титан", "Натуральный титан"], ["256GB", "512GB", "1TB"]),
    }

    for model_name, (colors, storages) in iphone_models.items():
        # Вставляем модель
        cur.execute("INSERT OR IGNORE INTO models (brand_id, name) VALUES (?, ?)", (apple_id, model_name))
        model_id = cur.execute("SELECT id FROM models WHERE brand_id=? AND name=?", (apple_id, model_name)).fetchone()[0]

        # Вставляем цвета
        for color in colors:
            cur.execute("INSERT OR IGNORE INTO specs (model_id, spec_type, spec_value) VALUES (?, 'color', ?)",
                        (model_id, color))

        # Вставляем объёмы памяти
        for storage in storages:
            cur.execute("INSERT OR IGNORE INTO specs (model_id, spec_type, spec_value) VALUES (?, 'storage', ?)",
                        (model_id, storage))

    conn.commit()
    conn.close()
    print("✅ База данных iPhone успешно заполнена.")
    start_background_tasks()


# ---------- Фоновые задачи ----------
def start_background_tasks():
    global _background_tasks
    # _background_tasks.append(asyncio.create_task(check_expired_requests()))
    _background_tasks.append(asyncio.create_task(check_price_drops()))


async def check_price_drops():
    while True:
        try:
            conn = sqlite3.connect('tech_auction.db')
            cur = conn.cursor()
            cur.execute('''
                SELECT f.user_id, f.lot_id, f.price_at_add, l.price
                FROM favorites f
                JOIN resale_lots l ON f.lot_id = l.id
                WHERE l.price < f.price_at_add
            ''')
            drops = cur.fetchall()
            for user_id, lot_id, old_price, new_price in drops:
                cur.execute('''
                    SELECT 1 FROM subscriptions 
                    WHERE user_id = ? AND (category_id IS NULL OR category_id = (SELECT category_id FROM resale_lots WHERE id = ?))
                    AND notify_on_price_drop = 1
                ''', (user_id, lot_id))
                if cur.fetchone():
                    # Здесь можно отправить уведомление (реализуется в хендлере)
                    pass
                cur.execute('''
                    UPDATE favorites SET price_at_add = ? WHERE user_id = ? AND lot_id = ?
                ''', (new_price, user_id, lot_id))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Ошибка в check_price_drops: {e}")
        await asyncio.sleep(600)


# ---------- Логирование ----------
def log_action(user_id: int, action: str, details: str = None):
    try:
        conn = sqlite3.connect('tech_auction.db')
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO logs (user_id, action, details) VALUES (?, ?, ?)
        ''', (user_id, action, details))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка логирования: {e}")

def get_logs(limit: int = 100):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT id, user_id, action, details, created_at
        FROM logs
        ORDER BY created_at DESC
        LIMIT ?
    ''', (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


# ---------- Категории, бренды, модели, характеристики ----------
def add_default_categories():
    categories = ['Ноутбуки', 'Смартфоны', 'Планшеты', 'Фототехника', 'Аудио/Видео', 'Игровые консоли', 'Комплектующие ПК', 'Инструменты']
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    for cat in categories:
        cur.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (cat,))
    conn.commit()
    conn.close()

def get_categories():
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT id, name FROM categories ORDER BY name')
    rows = cur.fetchall()
    conn.close()
    return rows

def get_brands_by_category(category_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT id, name FROM brands WHERE category_id = ? ORDER BY name', (category_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_models_by_brand(brand_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT id, name FROM models WHERE brand_id = ? ORDER BY name', (brand_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_specs_by_model(model_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT id, spec_type, spec_value FROM specs WHERE model_id = ?', (model_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_specs_by_model_and_type(model_id, spec_type):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT id, spec_value FROM specs WHERE model_id = ? AND spec_type = ?', (model_id, spec_type))
    rows = cur.fetchall()
    conn.close()
    return rows


# ---------- Пользователи ----------
def add_user(user_id, username, phone, full_name, referrer_id=None):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT OR REPLACE INTO users (user_id, username, phone, full_name, referrer_id, balance)
        VALUES (?, ?, ?, ?, ?, 0)
    ''', (user_id, username, phone, full_name, referrer_id))
    conn.commit()
    conn.close()
    log_action(user_id, 'REGISTER', f'Пользователь {full_name}')

def add_role(user_id, role):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, ?)', (user_id, role))
    conn.commit()
    conn.close()
    log_action(user_id, 'ADD_ROLE', role)

def has_role(user_id, role):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT 1 FROM user_roles WHERE user_id = ? AND role = ?', (user_id, role))
    row = cur.fetchone()
    conn.close()
    return row is not None

def user_exists(user_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None

def get_user_info(user_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT full_name, phone, username FROM users WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    return row if row else (None, None, None)

def get_user_contact(user_id):
    full_name, phone, username = get_user_info(user_id)
    if username:
        return f"@{username}"
    elif phone:
        return phone
    else:
        return str(user_id)

def get_user_balance(user_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0

def update_balance(user_id, amount):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()
    log_action(user_id, 'BALANCE_CHANGE', f'Изменение: {amount}')

def get_referrer(user_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT referrer_id FROM users WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def is_admin(user_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None

def add_admin(user_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()
    log_action(user_id, 'ADD_ADMIN', '')

def get_user_reliability(user_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT reliability_rating FROM users WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0

def update_reliability(user_id, delta):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('UPDATE users SET reliability_rating = reliability_rating + ? WHERE user_id = ?', (delta, user_id))
    conn.commit()
    conn.close()
    log_action(user_id, 'RELIABILITY_CHANGE', f'Изменение: {delta}')

def block_user(user_id, hours=24):
    block_until = datetime.datetime.now() + datetime.timedelta(hours=hours)
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('UPDATE users SET blocked_until = ? WHERE user_id = ?', (block_until, user_id))
    conn.commit()
    conn.close()
    log_action(user_id, 'BLOCK', f'Заблокирован до {block_until}')

def is_user_blocked(user_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT blocked_until FROM users WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    if row and row[0]:
        block_until = datetime.datetime.fromisoformat(row[0].replace(' ', 'T'))
        return block_until > datetime.datetime.now()
    return False


# ---------- Заявки на статус перекупа ----------
def add_reseller_request(user_id, username, full_name, phone):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT OR REPLACE INTO reseller_requests (user_id, username, full_name, phone)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, full_name, phone))
    conn.commit()
    conn.close()
    log_action(user_id, 'RESELLER_REQUEST', f'Заявка от {full_name}')

def get_all_requests():
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT user_id, username, full_name, phone, created_at FROM reseller_requests ORDER BY created_at')
    rows = cur.fetchall()
    conn.close()
    return rows

def get_request(user_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT full_name, phone, username FROM reseller_requests WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    return row if row else None

def delete_request(user_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('DELETE FROM reseller_requests WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    log_action(user_id, 'RESELLER_REQUEST_DELETE', '')


# ---------- Заявки на выкуп ----------
def create_buyout_request(user_id, category_id, brand_id, model_id, specs, description, condition,
                          photo_file_ids, video_file_id, desired_price,
                          battery_cycles=None, max_capacity=None, display_replaced=None,
                          defects=None, accessories=None):
    photo_str = ','.join(photo_file_ids) if photo_file_ids else ''
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO buyout_requests 
        (user_id, category_id, brand_id, model_id, specs, description, condition,
         photo_file_ids, video_file_id, desired_price,
         battery_cycles, max_capacity, display_replaced, defects, accessories)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, category_id, brand_id, model_id, specs, description, condition,
          photo_str, video_file_id, desired_price,
          battery_cycles, max_capacity, display_replaced, defects, accessories))
    request_id = cur.lastrowid
    conn.commit()
    conn.close()
    log_action(user_id, 'CREATE_BUYOUT_REQUEST', f'Заявка #{request_id}')
    return request_id

def get_user_buyout_requests(user_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT id, category_id, brand_id, model_id, specs, description, condition,
               photo_file_ids, video_file_id, desired_price,
               battery_cycles, max_capacity, display_replaced, defects, accessories,
               status, created_at
        FROM buyout_requests
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_active_buyout_requests():
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT id, user_id, category_id, brand_id, model_id, specs, description, condition,
               photo_file_ids, video_file_id, desired_price,
               battery_cycles, max_capacity, display_replaced, defects, accessories,
               created_at
        FROM buyout_requests
        WHERE status = 'active'
        ORDER BY created_at DESC
    ''')
    rows = cur.fetchall()
    conn.close()
    return rows

def get_buyout_request_by_id(req_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT id, user_id, category_id, brand_id, model_id, specs, description, condition,
               photo_file_ids, video_file_id, desired_price,
               battery_cycles, max_capacity, display_replaced, defects, accessories,
               status, created_at, winner_id
        FROM buyout_requests WHERE id = ?
    ''', (req_id,))
    row = cur.fetchone()
    conn.close()
    return row

def complete_buyout_request(req_id, winner_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        UPDATE buyout_requests SET status = 'completed', winner_id = ? WHERE id = ?
    ''', (winner_id, req_id))
    conn.commit()
    conn.close()
    log_action(winner_id, 'BUYOUT_COMPLETE', f'Заявка #{req_id}')

def cancel_buyout_request(req_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('UPDATE buyout_requests SET status = "cancelled" WHERE id = ?', (req_id,))
    conn.commit()
    conn.close()
    log_action(0, 'BUYOUT_CANCEL', f'Заявка #{req_id}')


# ---------- Предложения перекупов ----------
def get_offers_for_request(req_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT id, reseller_id, price, created_at FROM offers
        WHERE request_id = ?
        ORDER BY price DESC
    ''', (req_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def add_offer(request_id, reseller_id, price):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT 1 FROM offers WHERE request_id = ? AND reseller_id = ?', (request_id, reseller_id))
    if cur.fetchone():
        conn.close()
        return False
    cur.execute('''
        INSERT INTO offers (request_id, reseller_id, price) VALUES (?, ?, ?)
    ''', (request_id, reseller_id, price))
    conn.commit()
    conn.close()
    log_action(reseller_id, 'MAKE_OFFER', f'Заявка #{request_id}, цена {price}')
    return True

def mark_offer_notified(request_id, reseller_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        UPDATE offers SET notified = 1 WHERE request_id = ? AND reseller_id = ?
    ''', (request_id, reseller_id))
    conn.commit()
    conn.close()


# ---------- Объявления перекупов ----------
def create_resale_lot(
    reseller_id,
    category_id,
    brand_id,
    model_id,
    specs,
    description,
    condition,
    photo_file_ids,
    video_file_id,
    price,
    battery_cycles=None,
    max_capacity=None,
    display_replaced=None,
    defects=None,
    accessories=None
):
    photo_str = ','.join(photo_file_ids) if photo_file_ids else ''
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO resale_lots 
        (reseller_id, category_id, brand_id, model_id, specs, description, condition,
         photo_file_ids, video_file_id, price,
         battery_cycles, max_capacity, display_replaced, defects, accessories,
         status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'moderation')
    ''', (reseller_id, category_id, brand_id, model_id, specs, description, condition,
          photo_str, video_file_id, price,
          battery_cycles, max_capacity, display_replaced, defects, accessories))
    lot_id = cur.lastrowid
    conn.commit()
    conn.close()
    log_action(reseller_id, 'CREATE_RESALE_LOT', f'Лот #{lot_id}')
    return lot_id

def get_moderation_resale_lots():
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT id, reseller_id, category_id, brand_id, model_id, specs, description, condition,
               photo_file_ids, video_file_id, price,
               battery_cycles, max_capacity, display_replaced, defects, accessories,
               created_at
        FROM resale_lots
        WHERE status = 'moderation'
        ORDER BY created_at
    ''')
    rows = cur.fetchall()
    conn.close()
    return rows

def approve_resale_lot(lot_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        UPDATE resale_lots SET status = 'active' WHERE id = ? AND status = 'moderation'
    ''', (lot_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    if affected:
        log_action(0, 'APPROVE_LOT', f'Лот #{lot_id}')
    return affected > 0

def reject_resale_lot(lot_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        UPDATE resale_lots SET status = 'rejected' WHERE id = ? AND status = 'moderation'
    ''', (lot_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    if affected:
        log_action(0, 'REJECT_LOT', f'Лот #{lot_id}')
    return affected > 0

def get_active_resale_lots():
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT id, reseller_id, category_id, brand_id, model_id, specs, description, condition,
               photo_file_ids, video_file_id, price,
               battery_cycles, max_capacity, display_replaced, defects, accessories,
               views, offers_count, reserve_count, created_at, status
        FROM resale_lots
        WHERE status IN ('active', 'reserved')
        ORDER BY created_at DESC
    ''')
    rows = cur.fetchall()
    conn.close()
    return rows

def get_resale_lot_by_id(lot_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT id, reseller_id, category_id, brand_id, model_id, specs, description, condition,
               photo_file_ids, video_file_id, price,
               battery_cycles, max_capacity, display_replaced, defects, accessories,
               views, offers_count, reserve_count, status, created_at, buyer_id, sold_at
        FROM resale_lots WHERE id = ?
    ''', (lot_id,))
    row = cur.fetchone()
    conn.close()
    return row

def increment_lot_views(lot_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('UPDATE resale_lots SET views = views + 1 WHERE id = ?', (lot_id,))
    conn.commit()
    conn.close()

def increment_lot_offers_count(lot_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('UPDATE resale_lots SET offers_count = offers_count + 1 WHERE id = ?', (lot_id,))
    conn.commit()
    conn.close()

def increment_lot_reserve_count(lot_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('UPDATE resale_lots SET reserve_count = reserve_count + 1 WHERE id = ?', (lot_id,))
    conn.commit()
    conn.close()

def reserve_lot(lot_id, buyer_id):
    if reserve_lot_impl(lot_id, buyer_id):
        increment_lot_reserve_count(lot_id)
        log_action(buyer_id, 'RESERVE_LOT', f'Лот #{lot_id}')
        return True
    return False

def reserve_lot_impl(lot_id, buyer_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        UPDATE resale_lots SET status = 'reserved', buyer_id = ? WHERE id = ? AND status = 'active'
    ''', (buyer_id, lot_id))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def confirm_sale(lot_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        UPDATE resale_lots SET status = 'sold', sold_at = datetime('now') WHERE id = ? AND status = 'reserved'
    ''', (lot_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    if affected:
        log_action(0, 'CONFIRM_SALE', f'Лот #{lot_id}')
    return affected > 0

def cancel_reserve(lot_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        UPDATE resale_lots SET status = 'active', buyer_id = NULL WHERE id = ? AND status = 'reserved'
    ''', (lot_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    if affected:
        log_action(0, 'CANCEL_RESERVE', f'Лот #{lot_id}')
    return affected > 0


# ---------- Отзывы ----------
def add_review(seller_id, buyer_id, lot_id, rating, comment):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT 1 FROM reviews WHERE buyer_id = ? AND lot_id = ?', (buyer_id, lot_id))
    if cur.fetchone():
        conn.close()
        return False
    cur.execute('''
        INSERT INTO reviews (seller_id, buyer_id, lot_id, rating, comment)
        VALUES (?, ?, ?, ?, ?)
    ''', (seller_id, buyer_id, lot_id, rating, comment))
    conn.commit()
    conn.close()
    log_action(buyer_id, 'ADD_REVIEW', f'Лот #{lot_id}, оценка {rating}')
    return True

def get_seller_reviews(seller_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT r.rating, r.comment, r.created_at, u.username, u.full_name
        FROM reviews r
        LEFT JOIN users u ON r.buyer_id = u.user_id
        WHERE r.seller_id = ?
        ORDER BY r.created_at DESC
    ''', (seller_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_seller_rating(seller_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT AVG(rating), COUNT(*) FROM reviews WHERE seller_id = ?', (seller_id,))
    row = cur.fetchone()
    conn.close()
    if row and row[0]:
        return round(row[0], 2), row[1]
    return None, 0


# ---------- Рефералы ----------
def add_referral(referrer_id, referred_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)
    ''', (referrer_id, referred_id))
    conn.commit()
    conn.close()
    log_action(referrer_id, 'REFERRAL', f'Реферал {referred_id}')

def mark_reward_given(referral_id, amount):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        UPDATE referrals SET reward_given = 1, reward_amount = ? WHERE id = ?
    ''', (amount, referral_id))
    conn.commit()
    conn.close()

def get_pending_referral_by_referred(referred_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT id, referrer_id FROM referrals WHERE referred_id = ? AND reward_given = 0
    ''', (referred_id,))
    row = cur.fetchone()
    conn.close()
    return row

def encode_referrer_id(user_id):
    return base64.urlsafe_b64encode(str(user_id).encode()).decode().rstrip('=')

def decode_referrer_id(code):
    try:
        padding = 4 - (len(code) % 4)
        if padding != 4:
            code += '=' * padding
        decoded = base64.urlsafe_b64decode(code).decode()
        return int(decoded)
    except:
        return None


# ---------- Подписки ----------
def subscribe_user(user_id, category_id=None, notify_on_new=True, notify_on_price_drop=False, notify_on_auction_end=False):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT OR REPLACE INTO subscriptions (user_id, category_id, notify_on_new, notify_on_price_drop, notify_on_auction_end)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, category_id, notify_on_new, notify_on_price_drop, notify_on_auction_end))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()
    log_action(user_id, 'SUBSCRIBE', f'Категория {category_id}')

def unsubscribe_user(user_id, category_id=None):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    if category_id is None:
        cur.execute('DELETE FROM subscriptions WHERE user_id = ?', (user_id,))
    else:
        cur.execute('DELETE FROM subscriptions WHERE user_id = ? AND category_id = ?', (user_id, category_id))
    conn.commit()
    conn.close()
    log_action(user_id, 'UNSUBSCRIBE', f'Категория {category_id}')

def get_subscribers(category_id=None):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    if category_id is None:
        cur.execute('SELECT user_id FROM subscriptions WHERE category_id IS NULL AND notify_on_new = 1')
    else:
        cur.execute('''
            SELECT user_id FROM subscriptions 
            WHERE (category_id IS NULL OR category_id = ?) AND notify_on_new = 1
        ''', (category_id,))
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_user_subscriptions(user_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT category_id, notify_on_new, notify_on_price_drop, notify_on_auction_end FROM subscriptions WHERE user_id = ?', (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


# ---------- Избранное ----------
def add_favorite(user_id, lot_id, price):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT OR IGNORE INTO favorites (user_id, lot_id, price_at_add) VALUES (?, ?, ?)
    ''', (user_id, lot_id, price))
    conn.commit()
    conn.close()
    log_action(user_id, 'ADD_FAVORITE', f'Лот #{lot_id}')

def remove_favorite(user_id, lot_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('DELETE FROM favorites WHERE user_id = ? AND lot_id = ?', (user_id, lot_id))
    conn.commit()
    conn.close()
    log_action(user_id, 'REMOVE_FAVORITE', f'Лот #{lot_id}')

def is_favorite(user_id, lot_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT 1 FROM favorites WHERE user_id = ? AND lot_id = ?', (user_id, lot_id))
    row = cur.fetchone()
    conn.close()
    return row is not None

def get_user_favorites(user_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT f.lot_id, f.price_at_add, f.created_at, l.price, l.description
        FROM favorites f
        JOIN resale_lots l ON f.lot_id = l.id
        WHERE f.user_id = ?
        ORDER BY f.created_at DESC
    ''', (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


# ---------- Торг (price offers) ----------
def add_price_offer(lot_id, buyer_id, price):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO price_offers (lot_id, buyer_id, price) VALUES (?, ?, ?)
    ''', (lot_id, buyer_id, price))
    offer_id = cur.lastrowid
    conn.commit()
    conn.close()
    log_action(buyer_id, 'PRICE_OFFER', f'Лот #{lot_id}, цена {price}')
    increment_lot_offers_count(lot_id)
    return offer_id

def get_price_offers_for_lot(lot_id, status='pending'):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT id, buyer_id, price, created_at FROM price_offers
        WHERE lot_id = ? AND status = ?
        ORDER BY price DESC
    ''', (lot_id, status))
    rows = cur.fetchall()
    conn.close()
    return rows

def update_price_offer_status(offer_id, status):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('UPDATE price_offers SET status = ? WHERE id = ?', (status, offer_id))
    conn.commit()
    conn.close()


# ---------- Жалобы ----------
def add_complaint(complainant_id, lot_id, reason):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO complaints (complainant_id, lot_id, reason) VALUES (?, ?, ?)
    ''', (complainant_id, lot_id, reason))
    complaint_id = cur.lastrowid
    conn.commit()
    conn.close()
    log_action(complainant_id, 'COMPLAINT', f'Лот #{lot_id}')
    return complaint_id

def get_pending_complaints():
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT c.id, c.lot_id, c.reason, c.created_at, u.username, u.full_name
        FROM complaints c
        JOIN users u ON c.complainant_id = u.user_id
        WHERE c.status = 'pending'
        ORDER BY c.created_at
    ''')
    rows = cur.fetchall()
    conn.close()
    return rows

def resolve_complaint(complaint_id, action='reviewed'):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('UPDATE complaints SET status = ? WHERE id = ?', (action, complaint_id))
    conn.commit()
    conn.close()
    log_action(0, 'RESOLVE_COMPLAINT', f'Жалоба #{complaint_id}')


# ---------- Поддержка ----------
def add_support_ticket(user_id, message):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO support_tickets (user_id, message) VALUES (?, ?)
    ''', (user_id, message))
    ticket_id = cur.lastrowid
    conn.commit()
    conn.close()
    log_action(user_id, 'SUPPORT_TICKET', f'Тикет #{ticket_id}')
    return ticket_id


# ---------- Платежи ----------
def set_user_payment_id(user_id, payment_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('UPDATE users SET yookassa_payment_id = ? WHERE user_id = ?', (payment_id, user_id))
    conn.commit()
    conn.close()

def get_user_payment_id(user_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT yookassa_payment_id FROM users WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


# ---------- Популярные данные ----------
def populate_popular_data():
    # Здесь можно добавить популярные бренды и модели
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()

    # Для категории "Смартфоны" (id=2)
    cur.execute("INSERT OR IGNORE INTO brands (category_id, name) VALUES (2, 'Apple'), (2, 'Samsung'), (2, 'Xiaomi'), (2, 'Google')")
    # Для Apple
    apple_id = cur.execute("SELECT id FROM brands WHERE name='Apple' AND category_id=2").fetchone()
    if apple_id:
        apple_id = apple_id[0]
        cur.execute("INSERT OR IGNORE INTO models (brand_id, name) VALUES (?, 'iPhone 14'), (?, 'iPhone 15')", (apple_id, apple_id))
        iphone14_id = cur.execute("SELECT id FROM models WHERE name='iPhone 14' AND brand_id=?", (apple_id,)).fetchone()
        if iphone14_id:
            iphone14_id = iphone14_id[0]
            cur.execute("INSERT OR IGNORE INTO specs (model_id, spec_type, spec_value) VALUES (?, 'color', 'Черный'), (?, 'color', 'Белый'), (?, 'storage', '128GB'), (?, 'storage', '256GB')", 
                        (iphone14_id, iphone14_id, iphone14_id, iphone14_id))
        iphone15_id = cur.execute("SELECT id FROM models WHERE name='iPhone 15' AND brand_id=?", (apple_id,)).fetchone()
        if iphone15_id:
            iphone15_id = iphone15_id[0]
            cur.execute("INSERT OR IGNORE INTO specs (model_id, spec_type, spec_value) VALUES (?, 'color', 'Черный'), (?, 'color', 'Синий'), (?, 'storage', '128GB'), (?, 'storage', '256GB')",
                        (iphone15_id, iphone15_id, iphone15_id, iphone15_id))

    # Samsung
    samsung_id = cur.execute("SELECT id FROM brands WHERE name='Samsung' AND category_id=2").fetchone()
    if samsung_id:
        samsung_id = samsung_id[0]
        cur.execute("INSERT OR IGNORE INTO models (brand_id, name) VALUES (?, 'Galaxy S23'), (?, 'Galaxy S24')", (samsung_id, samsung_id))
        s23_id = cur.execute("SELECT id FROM models WHERE name='Galaxy S23' AND brand_id=?", (samsung_id,)).fetchone()
        if s23_id:
            s23_id = s23_id[0]
            cur.execute("INSERT OR IGNORE INTO specs (model_id, spec_type, spec_value) VALUES (?, 'color', 'Черный'), (?, 'color', 'Зеленый'), (?, 'storage', '128GB'), (?, 'storage', '256GB')",
                        (s23_id, s23_id, s23_id, s23_id))
        s24_id = cur.execute("SELECT id FROM models WHERE name='Galaxy S24' AND brand_id=?", (samsung_id,)).fetchone()
        if s24_id:
            s24_id = s24_id[0]
            cur.execute("INSERT OR IGNORE INTO specs (model_id, spec_type, spec_value) VALUES (?, 'color', 'Черный'), (?, 'color', 'Фиолетовый'), (?, 'storage', '128GB'), (?, 'storage', '256GB')",
                        (s24_id, s24_id, s24_id, s24_id))

    conn.commit()
    conn.close()