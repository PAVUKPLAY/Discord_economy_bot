import sqlite3
import json
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
    c.execute('''CREATE TABLE IF NOT EXISTS shop_pirozhki
                 (role_id INTEGER PRIMARY KEY,
                  role_name TEXT,
                  pirozhok_type TEXT,
                  quantity INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ingredients
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE,
                  price INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS recipes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE,
                  ingredients TEXT,
                  sell_price INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_inventory
                 (user_id INTEGER,
                  item_type TEXT,
                  item_id INTEGER,
                  quantity INTEGER,
                  PRIMARY KEY (user_id, item_type, item_id))''')
    conn.commit()

    # Заполнение начальными данными
    c.execute("SELECT COUNT(*) FROM ingredients")
    if c.fetchone()[0] == 0:
        ingredients = [
            ("картошка", 10),
            ("мясо", 30),
            ("лук", 5),
            ("яйца", 8),
            ("мука", 15),
            ("масло", 12)
        ]
        c.executemany("INSERT INTO ingredients (name, price) VALUES (?, ?)", ingredients)
    c.execute("SELECT COUNT(*) FROM recipes")
    if c.fetchone()[0] == 0:
        recipes = [
            ("пирожок с картошкой", json.dumps({"картошка": 2, "мука": 1, "масло": 1}), 50),
            ("пирожок с мясом", json.dumps({"мясо": 1, "мука": 1, "масло": 1, "лук": 1}), 80),
            ("пирожок с луком и яйцом", json.dumps({"лук": 2, "яйца": 2, "мука": 1, "масло": 1}), 60)
        ]
        c.executemany("INSERT INTO recipes (name, ingredients, sell_price) VALUES (?, ?, ?)", recipes)
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_balance(user_id, amount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO users (user_id, balance) VALUES (?, ?) "
              "ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?",
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

def get_shop_items():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role_id, role_name, price FROM shop")
    items = c.fetchall()
    conn.close()
    return items

def get_shop_item(role_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role_name, price FROM shop WHERE role_id = ?", (role_id,))
    item = c.fetchone()
    conn.close()
    return item

def add_shop_pirozhki_item(role_id, role_name, pirozhok_type, quantity):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO shop_pirozhki (role_id, role_name, pirozhok_type, quantity) VALUES (?, ?, ?, ?)",
              (role_id, role_name, pirozhok_type, quantity))
    conn.commit()
    conn.close()

def get_shop_pirozhki_items():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role_id, role_name, pirozhok_type, quantity FROM shop_pirozhki")
    items = c.fetchall()
    conn.close()
    return items

def get_shop_pirozhki_item(role_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role_name, pirozhok_type, quantity FROM shop_pirozhki WHERE role_id = ?", (role_id,))
    item = c.fetchone()
    conn.close()
    return item

def get_all_ingredients():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, price FROM ingredients ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return rows

def get_ingredient_price(ingredient_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT price FROM ingredients WHERE name = ?", (ingredient_name,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def get_all_recipes():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, ingredients, sell_price FROM recipes")
    rows = c.fetchall()
    conn.close()
    return rows

def get_recipe_by_name(name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, ingredients, sell_price FROM recipes WHERE name = ?", (name,))
    row = c.fetchone()
    conn.close()
    return row

def add_inventory(user_id, item_type, item_id, quantity):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO user_inventory (user_id, item_type, item_id, quantity) VALUES (?, ?, ?, ?) "
              "ON CONFLICT(user_id, item_type, item_id) DO UPDATE SET quantity = quantity + ?",
              (user_id, item_type, item_id, quantity, quantity))
    conn.commit()
    conn.close()

def remove_inventory(user_id, item_type, item_id, quantity):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT quantity FROM user_inventory WHERE user_id = ? AND item_type = ? AND item_id = ?",
              (user_id, item_type, item_id))
    row = c.fetchone()
    if not row or row[0] < quantity:
        conn.close()
        return False
    new_qty = row[0] - quantity
    if new_qty == 0:
        c.execute("DELETE FROM user_inventory WHERE user_id = ? AND item_type = ? AND item_id = ?",
                  (user_id, item_type, item_id))
    else:
        c.execute("UPDATE user_inventory SET quantity = ? WHERE user_id = ? AND item_type = ? AND item_id = ?",
                  (new_qty, user_id, item_type, item_id))
    conn.commit()
    conn.close()
    return True

def get_inventory(user_id, item_type=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if item_type:
        c.execute("SELECT item_id, quantity FROM user_inventory WHERE user_id = ? AND item_type = ?", (user_id, item_type))
    else:
        c.execute("SELECT item_type, item_id, quantity FROM user_inventory WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_ingredient_quantity(user_id, ingredient_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM ingredients WHERE name = ?", (ingredient_name,))
    row = c.fetchone()
    if not row:
        conn.close()
        return 0
    ing_id = row[0]
    c.execute("SELECT quantity FROM user_inventory WHERE user_id = ? AND item_type = 'ingredient' AND item_id = ?",
              (user_id, ing_id))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def get_pirozhki_quantity(user_id, recipe_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM recipes WHERE name = ?", (recipe_name,))
    row = c.fetchone()
    if not row:
        conn.close()
        return 0
    recipe_id = row[0]
    c.execute("SELECT quantity FROM user_inventory WHERE user_id = ? AND item_type = 'pirozhok' AND item_id = ?",
              (user_id, recipe_id))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def get_all_pirozhki(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT r.name, inv.quantity FROM user_inventory inv
                 JOIN recipes r ON inv.item_id = r.id
                 WHERE inv.user_id = ? AND inv.item_type = 'pirozhok' ''', (user_id,))
    rows = c.fetchall()
    conn.close()
    return {name: qty for name, qty in rows}
