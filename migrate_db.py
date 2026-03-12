import sqlite3

conn = sqlite3.connect('tech_auction.db')
cur = conn.cursor()

# Проверяем, есть ли столбец expires_at
cur.execute("PRAGMA table_info(buyout_requests)")
columns = [col[1] for col in cur.fetchall()]
if 'expires_at' in columns:
    print("Обнаружен столбец expires_at. Удаляем...")
    # Создаем новую таблицу без expires_at
    cur.execute('''
        CREATE TABLE buyout_requests_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category_id INTEGER,
            brand_id INTEGER,
            model_id INTEGER,
            specs TEXT,
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
    # Копируем данные (исключая expires_at)
    cur.execute('''
        INSERT INTO buyout_requests_new (
            id, user_id, category_id, brand_id, model_id, specs, description, condition,
            photo_file_ids, video_file_id, desired_price,
            battery_cycles, max_capacity, display_replaced, defects, accessories,
            status, created_at, winner_id
        )
        SELECT
            id, user_id, category_id, brand_id, model_id, specs, description, condition,
            photo_file_ids, video_file_id, desired_price,
            battery_cycles, max_capacity, display_replaced, defects, accessories,
            status, created_at, winner_id
        FROM buyout_requests
    ''')
    # Удаляем старую таблицу
    cur.execute("DROP TABLE buyout_requests")
    # Переименовываем новую
    cur.execute("ALTER TABLE buyout_requests_new RENAME TO buyout_requests")
    conn.commit()
    print("✅ Миграция выполнена. Столбец expires_at удален.")
else:
    print("Столбец expires_at не найден. Миграция не требуется.")

conn.close()