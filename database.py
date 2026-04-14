import sqlite3
from datetime import datetime, timedelta

DB_PATH = "economy.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  balance INTEGER DEFAULT 0,
                  last_daily TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS shop
                 (role_id INTEGER PRIMARY KEY,
                  role_name TEXT,
                  price INTEGER)''')
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row is None:
        return 0
    return row[0]

def update_balance(user_id, amount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO users (user_id, balance) VALUES (?, ?) "
              "ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?",
              (user_id, amount, amount))
    conn.commit()
    conn.close()

def set_balance(user_id, amount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO users (user_id, balance) VALUES (?, ?) "
              "ON CONFLICT(user_id) DO UPDATE SET balance = ?",
              (user_id, amount, amount))
    conn.commit()
    conn.close()

def can_daily(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT last_daily FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row is None or row[0] is None:
        return True
    last = datetime.fromisoformat(row[0])
    return datetime.now() - last >= timedelta(days=1)

def set_daily(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("INSERT INTO users (user_id, last_daily) VALUES (?, ?) "
              "ON CONFLICT(user_id) DO UPDATE SET last_daily = ?",
              (user_id, now, now))
    conn.commit()
    conn.close()

def get_top_balances(limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def add_shop_item(role_id, role_name, price):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO shop (role_id, role_name, price) VALUES (?, ?, ?)",
              (role_id, role_name, price))
    conn.commit()
    conn.close()