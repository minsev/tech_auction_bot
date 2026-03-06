import sqlite3

conn = sqlite3.connect('tech_auction.db')
cur = conn.cursor()

print("=== КАТЕГОРИИ ===")
cur.execute("SELECT id, name FROM categories")
for row in cur.fetchall():
    print(f"ID: {row[0]}, Название: {row[1]}")

print("\n=== БРЕНДЫ ===")
cur.execute("SELECT b.id, b.name, c.name FROM brands b JOIN categories c ON b.category_id = c.id")
for row in cur.fetchall():
    print(f"ID: {row[0]}, Бренд: {row[1]}, Категория: {row[2]}")

print("\n=== МОДЕЛИ ===")
cur.execute("SELECT m.id, m.name, b.name FROM models m JOIN brands b ON m.brand_id = b.id LIMIT 10")
for row in cur.fetchall():
    print(f"ID: {row[0]}, Модель: {row[1]}, Бренд: {row[2]}")

conn.close()