import sqlite3

# Вставьте свой Telegram ID (число) вместо 123456789
YOUR_ID = 8151084911

conn = sqlite3.connect('tech_auction.db')
cur = conn.cursor()
cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (8151084911,))
conn.commit()
conn.close()
print("✅ Админ добавлен!")