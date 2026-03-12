import sqlite3
import threading
import time
from contextlib import closing
from typing import Optional, Dict, Any, List

DB_PATH = "app.db"
_BG_THREAD = None
_BG_STOP = threading.Event()


# --- Database helpers -------------------------------------------------------
def _get_conn():
    return sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)


def _row_to_dict(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


# --- Initialization --------------------------------------------------------
def init_db():
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            balance INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS lots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            seller_id INTEGER NOT NULL,
            start_price INTEGER NOT NULL,
            current_price INTEGER NOT NULL,
            active INTEGER DEFAULT 1,
            created_at INTEGER NOT NULL,
            FOREIGN KEY(seller_id) REFERENCES users(id)
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_id INTEGER NOT NULL,
            buyer_id INTEGER NOT NULL,
            price INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY(lot_id) REFERENCES lots(id),
            FOREIGN KEY(buyer_id) REFERENCES users(id)
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            lot_id INTEGER NOT NULL,
            added_at INTEGER NOT NULL,
            UNIQUE(user_id, lot_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(lot_id) REFERENCES lots(id)
        )""")
        conn.commit()


# --- Background tasks ------------------------------------------------------
def _bg_task_cleanup():
    # Example background task: remove offers older than 30 days (2592000 seconds)
    while not _BG_STOP.wait(600):  # runs every 10 minutes
        cutoff = int(time.time()) - 2592000
        try:
            with closing(_get_conn()) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM offers WHERE created_at < ?", (cutoff,))
                deleted = cur.rowcount
                conn.commit()
                # optional: print cleanup info
                if deleted:
                    print(f"[bg] cleaned {deleted} old offers")
        except Exception as e:
            print("[bg] cleanup error:", e)


def start_background_tasks():
    global _BG_THREAD
    if _BG_THREAD and _BG_THREAD.is_alive():
        return
    _BG_STOP.clear()
    _BG_THREAD = threading.Thread(target=_bg_task_cleanup, daemon=True)
    _BG_THREAD.start()


def stop_background_tasks():
    _BG_STOP.set()
    if _BG_THREAD:
        _BG_THREAD.join(timeout=5)


# --- Utility functions -----------------------------------------------------
def now() -> int:
    return int(time.time())


# --- Users -----------------------------------------------------------------
def create_user(username: str, balance: int = 0) -> Dict[str, Any]:
    ts = now()
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO users (username, balance, created_at) VALUES (?, ?, ?)",
                    (username, balance, ts))
        conn.commit()
        user_id = cur.lastrowid
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return _row_to_dict(cur, cur.fetchone())


def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def adjust_user_balance(user_id: int, delta: int) -> bool:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (delta, user_id))
        conn.commit()
        return cur.rowcount > 0


# --- Lots ------------------------------------------------------------------
def create_lot(title: str, seller_id: int, start_price: int) -> Dict[str, Any]:
    ts = now()
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("""INSERT INTO lots (title, seller_id, start_price, current_price, active, created_at)
                       VALUES (?, ?, ?, ?, 1, ?)""",
                    (title, seller_id, start_price, start_price, ts))
        conn.commit()
        lid = cur.lastrowid
        cur.execute("SELECT * FROM lots WHERE id = ?", (lid,))
        return _row_to_dict(cur, cur.fetchone())


def get_lot(lot_id: int) -> Optional[Dict[str, Any]]:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM lots WHERE id = ?", (lot_id,))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def set_lot_current_price(lot_id: int, new_price: int) -> bool:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE lots SET current_price = ? WHERE id = ?", (new_price, lot_id))
        conn.commit()
        return cur.rowcount > 0


# --- Favorites -------------------------------------------------------------
def add_favorite(user_id: int, lot_id: int) -> bool:
    ts = now()
    try:
        with closing(_get_conn()) as conn:
            cur = conn.cursor()
            cur.execute("INSERT OR IGNORE INTO favorites (user_id, lot_id, added_at) VALUES (?, ?, ?)",
                        (user_id, lot_id, ts))
            conn.commit()
            return cur.rowcount > 0
    except Exception:
        return False


def remove_favorite(user_id: int, lot_id: int) -> bool:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM favorites WHERE user_id = ? AND lot_id = ?", (user_id, lot_id))
        conn.commit()
        return cur.rowcount > 0


# --- Offers / Bids ---------------------------------------------------------
def list_offers_for_lot(lot_id: int) -> List[Dict[str, Any]]:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM offers WHERE lot_id = ? ORDER BY price DESC, created_at ASC", (lot_id,))
        rows = cur.fetchall()
        return [_row_to_dict(cur, r) for r in rows]


def make_price_offer(buyer_id: int, lot_id: int, price: int) -> Dict[str, Any]:
    """
    Попытка сделать ставку (заявку) от buyer_id на lot_id по цене price.
    Возвращает dict с ключом success: bool и дополнительными полями:
     - on_success: offer (offer data)
     - on_failure: reason (строка)
    Правила:
     - lot должен быть active
     - price должен быть > current_price и >= start_price
     - у покупателя должно быть достаточно баланса
    Atomic: проверка и запись в одной транзакции.
    """
    if price <= 0:
        return {"success": False, "reason": "invalid_price"}

    ts = now()

    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        try:
            # begin immediate transaction to avoid race
            cur.execute("BEGIN IMMEDIATE")
            # fetch lot and buyer
            cur.execute("SELECT * FROM lots WHERE id = ? FOR UPDATE", (lot_id,))
        except sqlite3.OperationalError:
            # sqlite may not support FOR UPDATE; ignore
            pass

        # re-query lot normally (sqlite ignore FOR UPDATE)
        cur.execute("SELECT * FROM lots WHERE id = ?", (lot_id,))
        lot_row = cur.fetchone()
        if not lot_row:
            conn.rollback()
            return {"success": False, "reason": "lot_not_found"}
        lot = _row_to_dict(cur, lot_row)
        if not lot.get("active", 0):
            conn.rollback()
            return {"success": False, "reason": "lot_inactive"}

        cur.execute("SELECT * FROM users WHERE id = ?", (buyer_id,))
        buyer_row = cur.fetchone()
        if not buyer_row:
            conn.rollback()
            return {"success": False, "reason": "buyer_not_found"}
        buyer = _row_to_dict(cur, buyer_row)

        current_price = int(lot["current_price"])
        start_price = int(lot["start_price"])

        if price <= current_price or price < start_price:
            conn.rollback()
            return {"success": False, "reason": "price_too_low", "current_price": current_price}

        # check buyer balance
        if int(buyer["balance"]) < price:
            conn.rollback()
            return {"success": False, "reason": "insufficient_funds", "balance": buyer["balance"]}

        # Everything ok: create offer, update lot current_price and reserve buyer funds (decrement)
        try:
            cur.execute("INSERT INTO offers (lot_id, buyer_id, price, created_at) VALUES (?, ?, ?, ?)",
                        (lot_id, buyer_id, price, ts))
            offer_id = cur.lastrowid
            cur.execute("UPDATE lots SET current_price = ? WHERE id = ?", (price, lot_id))
            # Here decision: immediately deduct buyer's balance (reserve). Alternative: hold only on winning.
            cur.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (price, buyer_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            return {"success": False, "reason": "db_error", "error": str(e)}

        # Return created offer
        cur.execute("SELECT * FROM offers WHERE id = ?", (offer_id,))
        offer = _row_to_dict(cur, cur.fetchone())
        return {"success": True, "offer": offer}


# --- Simple tests (run when module executed directly) ----------------------
if __name__ == "__main__":
    init_db()
    start_background_tasks()
    print("DB initialized and background tasks started")

    # Create test data if none
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            u1 = create_user("alice", balance=1000)
            u2 = create_user("bob", balance=500)
            l1 = create_lot("Nice Watch", seller_id=u1["id"], start_price=100)
            print("Created test users and lot:", u1, u2, l1)

    # Try making an offer
    result = make_price_offer(buyer_id=2, lot_id=1, price=150)
    print("Offer result:", result)

    # Keep main thread alive briefly to allow background to run
    time.sleep(1)
    stop_background_tasks()