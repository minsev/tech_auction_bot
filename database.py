import sqlite3
import datetime
import base64

def init_db():
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            phone TEXT,
            full_name TEXT,
            referrer_id INTEGER DEFAULT NULL,
            balance INTEGER DEFAULT 0,
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
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS specs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            spec_type TEXT,
            spec_value TEXT,
            FOREIGN KEY(model_id) REFERENCES models(id)
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS buyout_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category_id INTEGER,
            brand_id INTEGER,
            model_id INTEGER,
            specs TEXT,
            description TEXT,
            condition TEXT,
            photo_file_id TEXT,
            desired_price INTEGER,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed', 'cancelled')),
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
            FOREIGN KEY(request_id) REFERENCES buyout_requests(id),
            FOREIGN KEY(reseller_id) REFERENCES users(user_id)
        )
    ''')
    
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
            photo_file_id TEXT,
            price INTEGER,
            status TEXT DEFAULT 'moderation' CHECK(status IN ('moderation', 'active', 'reserved', 'sold', 'rejected')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            buyer_id INTEGER DEFAULT NULL,
            sold_at TIMESTAMP DEFAULT NULL,
            FOREIGN KEY(reseller_id) REFERENCES users(user_id),
            FOREIGN KEY(buyer_id) REFERENCES users(user_id)
        )
    ''')
    
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
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category_id INTEGER DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, category_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )
    ''')
    
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
    
    conn.commit()
    conn.close()
    
    add_default_categories()
    populate_popular_data()

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

def add_user(user_id, username, phone, full_name, referrer_id=None):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT OR REPLACE INTO users (user_id, username, phone, full_name, referrer_id, balance)
        VALUES (?, ?, ?, ?, ?, 0)
    ''', (user_id, username, phone, full_name, referrer_id))
    conn.commit()
    conn.close()

def add_role(user_id, role):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, ?)', (user_id, role))
    conn.commit()
    conn.close()

def remove_role(user_id, role):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('DELETE FROM user_roles WHERE user_id = ? AND role = ?', (user_id, role))
    conn.commit()
    conn.close()

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

def add_reseller_request(user_id, username, full_name, phone):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT OR REPLACE INTO reseller_requests (user_id, username, full_name, phone)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, full_name, phone))
    conn.commit()
    conn.close()

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

def create_buyout_request(user_id, category_id, brand_id, model_id, specs, description, condition, photo_file_id, desired_price):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO buyout_requests 
        (user_id, category_id, brand_id, model_id, specs, description, condition, photo_file_id, desired_price, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
    ''', (user_id, category_id, brand_id, model_id, specs, description, condition, photo_file_id, desired_price))
    request_id = cur.lastrowid
    conn.commit()
    conn.close()
    return request_id

def get_user_buyout_requests(user_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT id, category_id, brand_id, model_id, specs, description, condition, photo_file_id, desired_price, status, created_at
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
        SELECT id, user_id, category_id, brand_id, model_id, specs, description, condition, photo_file_id, desired_price, created_at
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
        SELECT id, user_id, category_id, brand_id, model_id, specs, description, condition, photo_file_id, desired_price, status, created_at, winner_id
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

def cancel_buyout_request(req_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('UPDATE buyout_requests SET status = "cancelled" WHERE id = ?', (req_id,))
    conn.commit()
    conn.close()

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
        INSERT INTO offers (request_id, reseller_id, price)
        VALUES (?, ?, ?)
    ''', (request_id, reseller_id, price))
    conn.commit()
    conn.close()
    return True

def create_resale_lot(reseller_id, category_id, brand_id, model_id, specs, description, condition, photo_file_id, price):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO resale_lots 
        (reseller_id, category_id, brand_id, model_id, specs, description, condition, photo_file_id, price, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'moderation')
    ''', (reseller_id, category_id, brand_id, model_id, specs, description, condition, photo_file_id, price))
    lot_id = cur.lastrowid
    conn.commit()
    conn.close()
    return lot_id

def get_moderation_resale_lots():
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT id, reseller_id, category_id, brand_id, model_id, specs, description, condition, photo_file_id, price, created_at
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
    return affected > 0

def get_active_resale_lots():
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT id, reseller_id, category_id, brand_id, model_id, specs, description, condition, photo_file_id, price, created_at, status
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
        SELECT id, reseller_id, category_id, brand_id, model_id, specs, description, condition, photo_file_id, price, status, created_at, buyer_id, sold_at
        FROM resale_lots WHERE id = ?
    ''', (lot_id,))
    row = cur.fetchone()
    conn.close()
    return row

def reserve_lot(lot_id, buyer_id):
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
    return affected > 0

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

def subscribe_user(user_id, category_id=None):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT OR IGNORE INTO subscriptions (user_id, category_id) VALUES (?, ?)
        ''', (user_id, category_id))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

def unsubscribe_user(user_id, category_id=None):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    if category_id is None:
        cur.execute('DELETE FROM subscriptions WHERE user_id = ?', (user_id,))
    else:
        cur.execute('DELETE FROM subscriptions WHERE user_id = ? AND category_id = ?', (user_id, category_id))
    conn.commit()
    conn.close()

def get_subscribers(category_id=None):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    if category_id is None:
        cur.execute('SELECT user_id FROM subscriptions WHERE category_id IS NULL')
    else:
        cur.execute('''
            SELECT user_id FROM subscriptions 
            WHERE category_id IS NULL OR category_id = ?
        ''', (category_id,))
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_user_subscriptions(user_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT category_id FROM subscriptions WHERE user_id = ?', (user_id,))
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]

def add_referral(referrer_id, referred_id):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)
    ''', (referrer_id, referred_id))
    conn.commit()
    conn.close()

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

def populate_popular_data():
    """Добавляет популярные модели iPhone, Samsung и AirPods"""
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    
    cur.execute("SELECT id FROM categories WHERE name='Смартфоны'")
    smartphones_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM categories WHERE name='Аудио/Видео'")
    audio_id = cur.fetchone()[0]
    
    # Apple
    cur.execute("SELECT id FROM brands WHERE category_id=? AND name=?", (smartphones_id, "Apple"))
    apple_row = cur.fetchone()
    if apple_row:
        apple_id = apple_row[0]
    else:
        cur.execute("INSERT INTO brands (category_id, name) VALUES (?, ?)", (smartphones_id, "Apple"))
        apple_id = cur.lastrowid
        print("Создан бренд Apple")
    
    iphones = [
        ("iPhone 6", ["16GB", "32GB", "64GB"], ["Space Gray", "Silver", "Gold"]),
        ("iPhone 6s", ["16GB", "32GB", "64GB", "128GB"], ["Space Gray", "Silver", "Gold", "Rose Gold"]),
        ("iPhone 7", ["32GB", "128GB", "256GB"], ["Black", "Jet Black", "Silver", "Gold", "Rose Gold"]),
        ("iPhone 8", ["64GB", "256GB"], ["Space Gray", "Silver", "Gold"]),
        ("iPhone X", ["64GB", "256GB"], ["Space Gray", "Silver"]),
        ("iPhone XR", ["64GB", "128GB", "256GB"], ["Black", "White", "Blue", "Yellow", "Coral", "Red"]),
        ("iPhone XS", ["64GB", "256GB", "512GB"], ["Space Gray", "Silver", "Gold"]),
        ("iPhone XS Max", ["64GB", "256GB", "512GB"], ["Space Gray", "Silver", "Gold"]),
        ("iPhone 11", ["64GB", "128GB", "256GB"], ["Black", "White", "Green", "Yellow", "Purple", "Red"]),
        ("iPhone 11 Pro", ["64GB", "256GB", "512GB"], ["Space Gray", "Silver", "Gold", "Midnight Green"]),
        ("iPhone 11 Pro Max", ["64GB", "256GB", "512GB"], ["Space Gray", "Silver", "Gold", "Midnight Green"]),
        ("iPhone SE (2020)", ["64GB", "128GB", "256GB"], ["Black", "White", "Red"]),
        ("iPhone 12", ["64GB", "128GB", "256GB"], ["Black", "White", "Blue", "Green", "Red"]),
        ("iPhone 12 mini", ["64GB", "128GB", "256GB"], ["Black", "White", "Blue", "Green", "Red"]),
        ("iPhone 12 Pro", ["128GB", "256GB", "512GB"], ["Graphite", "Silver", "Gold", "Pacific Blue"]),
        ("iPhone 12 Pro Max", ["128GB", "256GB", "512GB"], ["Graphite", "Silver", "Gold", "Pacific Blue"]),
        ("iPhone 13", ["128GB", "256GB", "512GB"], ["Pink", "Blue", "Midnight", "Starlight", "Red"]),
        ("iPhone 13 mini", ["128GB", "256GB", "512GB"], ["Pink", "Blue", "Midnight", "Starlight", "Red"]),
        ("iPhone 13 Pro", ["128GB", "256GB", "512GB", "1TB"], ["Graphite", "Gold", "Silver", "Sierra Blue"]),
        ("iPhone 13 Pro Max", ["128GB", "256GB", "512GB", "1TB"], ["Graphite", "Gold", "Silver", "Sierra Blue"]),
        ("iPhone SE (2022)", ["64GB", "128GB", "256GB"], ["Midnight", "Starlight", "Red"]),
        ("iPhone 14", ["128GB", "256GB", "512GB"], ["Midnight", "Purple", "Starlight", "Blue", "Red"]),
        ("iPhone 14 Plus", ["128GB", "256GB", "512GB"], ["Midnight", "Purple", "Starlight", "Blue", "Red"]),
        ("iPhone 14 Pro", ["128GB", "256GB", "512GB", "1TB"], ["Space Black", "Silver", "Gold", "Deep Purple"]),
        ("iPhone 14 Pro Max", ["128GB", "256GB", "512GB", "1TB"], ["Space Black", "Silver", "Gold", "Deep Purple"]),
        ("iPhone 15", ["128GB", "256GB", "512GB"], ["Black", "Blue", "Green", "Yellow", "Pink"]),
        ("iPhone 15 Plus", ["128GB", "256GB", "512GB"], ["Black", "Blue", "Green", "Yellow", "Pink"]),
        ("iPhone 15 Pro", ["128GB", "256GB", "512GB", "1TB"], ["Black Titanium", "White Titanium", "Blue Titanium", "Natural Titanium"]),
        ("iPhone 15 Pro Max", ["256GB", "512GB", "1TB"], ["Black Titanium", "White Titanium", "Blue Titanium", "Natural Titanium"]),
        ("iPhone 16", ["128GB", "256GB", "512GB"], ["Black", "White", "Pink", "Teal", "Ultramarine"]),
        ("iPhone 16 Plus", ["128GB", "256GB", "512GB"], ["Black", "White", "Pink", "Teal", "Ultramarine"]),
        ("iPhone 16 Pro", ["128GB", "256GB", "512GB", "1TB"], ["Black Titanium", "White Titanium", "Natural Titanium", "Desert Titanium"]),
        ("iPhone 16 Pro Max", ["256GB", "512GB", "1TB"], ["Black Titanium", "White Titanium", "Natural Titanium", "Desert Titanium"]),
    ]
    
    for model_name, memories, colors in iphones:
        cur.execute("SELECT id FROM models WHERE brand_id=? AND name=?", (apple_id, model_name))
        model_row = cur.fetchone()
        if model_row:
            model_id = model_row[0]
        else:
            cur.execute("INSERT INTO models (brand_id, name) VALUES (?, ?)", (apple_id, model_name))
            model_id = cur.lastrowid
        for mem in memories:
            cur.execute("INSERT OR IGNORE INTO specs (model_id, spec_type, spec_value) VALUES (?, 'memory', ?)", (model_id, mem))
        for col in colors:
            cur.execute("INSERT OR IGNORE INTO specs (model_id, spec_type, spec_value) VALUES (?, 'color', ?)", (model_id, col))
    
    # Samsung
    cur.execute("SELECT id FROM brands WHERE category_id=? AND name=?", (smartphones_id, "Samsung"))
    samsung_row = cur.fetchone()
    if samsung_row:
        samsung_id = samsung_row[0]
    else:
        cur.execute("INSERT INTO brands (category_id, name) VALUES (?, ?)", (smartphones_id, "Samsung"))
        samsung_id = cur.lastrowid
        print("Создан бренд Samsung")
    
    samsung_models = [
        ("Galaxy S21", ["128GB", "256GB"], ["Phantom Gray", "Phantom White", "Phantom Violet", "Phantom Pink"]),
        ("Galaxy S21+", ["128GB", "256GB"], ["Phantom Black", "Phantom Silver", "Phantom Violet"]),
        ("Galaxy S21 Ultra", ["128GB", "256GB", "512GB"], ["Phantom Black", "Phantom Silver", "Phantom Titanium", "Phantom Navy"]),
        ("Galaxy S22", ["128GB", "256GB"], ["Phantom Black", "Phantom White", "Green", "Pink Gold"]),
        ("Galaxy S22+", ["128GB", "256GB"], ["Phantom Black", "Phantom White", "Green", "Pink Gold"]),
        ("Galaxy S22 Ultra", ["128GB", "256GB", "512GB", "1TB"], ["Phantom Black", "Phantom White", "Green", "Burgundy"]),
        ("Galaxy S23", ["128GB", "256GB", "512GB"], ["Phantom Black", "Cream", "Green", "Lavender"]),
        ("Galaxy S23+", ["256GB", "512GB"], ["Phantom Black", "Cream", "Green", "Lavender"]),
        ("Galaxy S23 Ultra", ["256GB", "512GB", "1TB"], ["Phantom Black", "Cream", "Green", "Lavender"]),
        ("Galaxy S24", ["128GB", "256GB", "512GB"], ["Amber Yellow", "Cobalt Violet", "Marble Gray", "Onyx Black"]),
        ("Galaxy S24+", ["256GB", "512GB"], ["Amber Yellow", "Cobalt Violet", "Marble Gray", "Onyx Black"]),
        ("Galaxy S24 Ultra", ["256GB", "512GB", "1TB"], ["Titanium Black", "Titanium Gray", "Titanium Violet", "Titanium Yellow"]),
        ("Galaxy Z Flip4", ["128GB", "256GB", "512GB"], ["Bora Purple", "Graphite", "Pink Gold", "Blue"]),
        ("Galaxy Z Flip5", ["256GB", "512GB"], ["Graphite", "Lavender", "Mint", "Cream"]),
        ("Galaxy Z Flip6", ["256GB", "512GB"], ["Blue", "Silver Shadow", "Yellow", "Mint"]),
        ("Galaxy Z Fold4", ["256GB", "512GB", "1TB"], ["Graygreen", "Phantom Black", "Beige", "Burgundy"]),
        ("Galaxy Z Fold5", ["256GB", "512GB", "1TB"], ["Icy Blue", "Phantom Black", "Cream"]),
        ("Galaxy Z Fold6", ["256GB", "512GB", "1TB"], ["Navy", "Silver Shadow", "Pink"]),
        ("Galaxy Note20", ["256GB"], ["Mystic Bronze", "Mystic Green", "Mystic Gray"]),
        ("Galaxy Note20 Ultra", ["256GB", "512GB"], ["Mystic Bronze", "Mystic Black", "Mystic White"]),
    ]
    
    for model_name, memories, colors in samsung_models:
        cur.execute("SELECT id FROM models WHERE brand_id=? AND name=?", (samsung_id, model_name))
        model_row = cur.fetchone()
        if model_row:
            model_id = model_row[0]
        else:
            cur.execute("INSERT INTO models (brand_id, name) VALUES (?, ?)", (samsung_id, model_name))
            model_id = cur.lastrowid
        for mem in memories:
            cur.execute("INSERT OR IGNORE INTO specs (model_id, spec_type, spec_value) VALUES (?, 'memory', ?)", (model_id, mem))
        for col in colors:
            cur.execute("INSERT OR IGNORE INTO specs (model_id, spec_type, spec_value) VALUES (?, 'color', ?)", (model_id, col))
    
    # AirPods
    cur.execute("SELECT id FROM brands WHERE category_id=? AND name=?", (audio_id, "Apple AirPods"))
    airpods_row = cur.fetchone()
    if airpods_row:
        airpods_brand_id = airpods_row[0]
    else:
        cur.execute("INSERT INTO brands (category_id, name) VALUES (?, ?)", (audio_id, "Apple AirPods"))
        airpods_brand_id = cur.lastrowid
        print("Создан бренд Apple AirPods")
    
    airpods_models = [
        ("AirPods 2", ["С зарядным футляром", "С беспроводной зарядкой"], ["White"]),
        ("AirPods 3", ["С MagSafe"], ["White"]),
        ("AirPods Pro", ["1-го поколения"], ["White"]),
        ("AirPods Pro 2", ["2-го поколения", "2-го поколения с USB-C"], ["White"]),
        ("AirPods Max", ["С Lightning", "С USB-C"], ["Space Gray", "Silver", "Green", "Sky Blue", "Pink"]),
    ]
    
    for model_name, versions, colors in airpods_models:
        cur.execute("SELECT id FROM models WHERE brand_id=? AND name=?", (airpods_brand_id, model_name))
        model_row = cur.fetchone()
        if model_row:
            model_id = model_row[0]
        else:
            cur.execute("INSERT INTO models (brand_id, name) VALUES (?, ?)", (airpods_brand_id, model_name))
            model_id = cur.lastrowid
        for ver in versions:
            cur.execute("INSERT OR IGNORE INTO specs (model_id, spec_type, spec_value) VALUES (?, 'version', ?)", (model_id, ver))
        for col in colors:
            cur.execute("INSERT OR IGNORE INTO specs (model_id, spec_type, spec_value) VALUES (?, 'color', ?)", (model_id, col))
    
    conn.commit()
    conn.close()
    print("✅ Популярные данные добавлены в БД")