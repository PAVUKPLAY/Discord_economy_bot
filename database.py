import sqlite3
import json
from datetime import datetime, timedelta

DB_PATH = "economy.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  balance INTEGER DEFAULT 0,
                  xp INTEGER DEFAULT 0,
                  last_daily TEXT)''')
    # Таблица магазина ролей
    c.execute('''CREATE TABLE IF NOT EXISTS shop_roles
                 (role_id INTEGER PRIMARY KEY,
                  role_name TEXT,
                  price_coins INTEGER,
                  price_pirozhki_type TEXT,
                  price_pirozhki_qty INTEGER,
                  condition TEXT)''')
    # Ингредиенты
    c.execute('''CREATE TABLE IF NOT EXISTS ingredients
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE,
                  price INTEGER)''')
    # Рецепты пирожков
    c.execute('''CREATE TABLE IF NOT EXISTS recipes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE,
                  ingredients TEXT,
                  sell_price INTEGER)''')
    # Инвентарь
    c.execute('''CREATE TABLE IF NOT EXISTS user_inventory
                 (user_id INTEGER,
                  item_type TEXT,
                  item_id INTEGER,
                  quantity INTEGER,
                  PRIMARY KEY (user_id, item_type, item_id))''')
    # Логи работы (кулдаун)
    c.execute('''CREATE TABLE IF NOT EXISTS work_uses
                 (user_id INTEGER,
                  timestamp REAL,
                  PRIMARY KEY (user_id, timestamp))''')
    # Настройки
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY,
                  value TEXT)''')
    # Логи админов
    c.execute('''CREATE TABLE IF NOT EXISTS admin_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  admin_id INTEGER,
                  admin_name TEXT,
                  action TEXT,
                  target_id INTEGER,
                  target_name TEXT,
                  details TEXT,
                  timestamp TEXT)''')
    # Промокоды
    c.execute('''CREATE TABLE IF NOT EXISTS promocodes
                 (code TEXT PRIMARY KEY,
                  reward_type TEXT,
                  reward_amount INTEGER,
                  reward_item TEXT,
                  uses_limit INTEGER,
                  created_by INTEGER,
                  created_at TEXT,
                  uses_left INTEGER)''')
    # Использования промокодов
    c.execute('''CREATE TABLE IF NOT EXISTS promocode_uses
                 (code TEXT,
                  user_id INTEGER,
                  used_at TEXT,
                  PRIMARY KEY (code, user_id))''')
    conn.commit()

    # Заполнение начальными данными
    c.execute("SELECT COUNT(*) FROM ingredients")
    if c.fetchone()[0] == 0:
        ingredients = [
            ("картошка", 10), ("мясо", 30), ("лук", 5),
            ("яйца", 8), ("мука", 15), ("масло", 12)
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
    c.execute("SELECT COUNT(*) FROM settings")
    if c.fetchone()[0] == 0:
        settings = [
            ('work_min', '50'),
            ('work_max', '150'),
            ('daily_reward', '100'),
            ('xp_per_work', '10'),
            ('xp_per_gamble', '5'),
            ('level_base_xp', '100')
        ]
        c.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", settings)
    conn.commit()
    conn.close()

# ---------- БАЛАНС МОНЕТ ----------
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

def set_balance(user_id, amount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO users (user_id, balance) VALUES (?, ?) "
              "ON CONFLICT(user_id) DO UPDATE SET balance = ?",
              (user_id, amount, amount))
    conn.commit()
    conn.close()

# ---------- ОПЫТ И УРОВНИ ----------
def get_xp(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT xp FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    xp = row[0] if row else 0
    base = int(get_setting('level_base_xp', 100))
    # Уровень: floor(sqrt(xp / base)) + 1
    level = max(1, int((xp / base) ** 0.5) + 1)
    return xp, level

def set_xp(user_id, new_xp):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO users (user_id, xp) VALUES (?, ?) "
              "ON CONFLICT(user_id) DO UPDATE SET xp = ?",
              (user_id, new_xp, new_xp))
    conn.commit()
    conn.close()

def add_xp(user_id, amount):
    current, _ = get_xp(user_id)
    set_xp(user_id, current + amount)

def get_level_xp(level):
    base = int(get_setting('level_base_xp', 100))
    return base * (level ** 2)

def get_xp_per_work():
    return int(get_setting('xp_per_work', 10))

def set_xp_per_work(value):
    set_setting('xp_per_work', value)

def get_xp_per_gamble():
    return int(get_setting('xp_per_gamble', 5))

def set_xp_per_gamble(value):
    set_setting('xp_per_gamble', value)

# ---------- ЕЖЕДНЕВНЫЙ БОНУС ----------
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

def get_daily_cooldown_seconds(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT last_daily FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row is None or row[0] is None:
        return 0
    last = datetime.fromisoformat(row[0])
    next_available = last + timedelta(days=1)
    remaining = (next_available - datetime.now()).total_seconds()
    return max(0, int(remaining))

def get_daily_reward():
    return int(get_setting('daily_reward', 100))

def set_daily_reward(value):
    set_setting('daily_reward', value)

# ---------- РАБОТА (КУЛДАУН) ----------
def can_work(user_id):
    now = datetime.now().timestamp()
    ten_min_ago = now - 600
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM work_uses WHERE user_id = ? AND timestamp > ?", (user_id, ten_min_ago))
    count = c.fetchone()[0]
    conn.close()
    return count < 20

def add_work_use(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().timestamp()
    c.execute("INSERT INTO work_uses (user_id, timestamp) VALUES (?, ?)", (user_id, now))
    conn.commit()
    conn.close()

def get_work_cooldown_remaining(user_id):
    now = datetime.now().timestamp()
    ten_min_ago = now - 600
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM work_uses WHERE user_id = ? AND timestamp > ?", (user_id, ten_min_ago))
    count = c.fetchone()[0]
    conn.close()
    if count < 20:
        return 0
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT MIN(timestamp) FROM work_uses WHERE user_id = ? AND timestamp > ?", (user_id, ten_min_ago))
    oldest = c.fetchone()[0]
    conn.close()
    if oldest:
        next_free = oldest + 600
        remaining = next_free - now
        return max(0, int(remaining))
    return 0

def get_work_min():
    return int(get_setting('work_min', 50))

def get_work_max():
    return int(get_setting('work_max', 150))

def set_work_min(value):
    set_setting('work_min', value)

def set_work_max(value):
    set_setting('work_max', value)

# ---------- НАСТРОЙКИ ----------
def get_setting(key, default=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    return default

def set_setting(key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

# ---------- ТОП ПО МОНЕТАМ ----------
def get_top_balances(limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

# ---------- ЛОГИ АДМИНОВ ----------
def log_admin_action(admin_id, admin_name, action, target_id=None, target_name=None, details=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("INSERT INTO admin_logs (admin_id, admin_name, action, target_id, target_name, details, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (admin_id, admin_name, action, target_id, target_name, details, now))
    conn.commit()
    conn.close()

# ---------- МАГАЗИН РОЛЕЙ ----------
def add_shop_role(role_id, role_name, price_coins=None, price_pirozhki_type=None, price_pirozhki_qty=None, condition='or'):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO shop_roles (role_id, role_name, price_coins, price_pirozhki_type, price_pirozhki_qty, condition) VALUES (?, ?, ?, ?, ?, ?)",
              (role_id, role_name, price_coins, price_pirozhki_type, price_pirozhki_qty, condition))
    conn.commit()
    conn.close()

def get_shop_roles():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role_id, role_name, price_coins, price_pirozhki_type, price_pirozhki_qty, condition FROM shop_roles")
    rows = c.fetchall()
    conn.close()
    return rows

def get_shop_role(role_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role_name, price_coins, price_pirozhki_type, price_pirozhki_qty, condition FROM shop_roles WHERE role_id = ?", (role_id,))
    row = c.fetchone()
    conn.close()
    return row

def delete_shop_role(role_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM shop_roles WHERE role_id = ?", (role_id,))
    conn.commit()
    conn.close()

# ---------- ИНГРЕДИЕНТЫ, РЕЦЕПТЫ, ИНВЕНТАРЬ ----------
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

def add_pirozhki(user_id, recipe_name, quantity):
    recipe = get_recipe_by_name(recipe_name)
    if not recipe:
        return False
    add_inventory(user_id, "pirozhok", recipe[0], quantity)
    return True

def remove_pirozhki(user_id, recipe_name, quantity):
    recipe = get_recipe_by_name(recipe_name)
    if not recipe:
        return False
    return remove_inventory(user_id, "pirozhok", recipe[0], quantity)

# ---------- ПРОМОКОДЫ ----------
def create_promocode_full(code, reward_type, reward_amount, reward_item, uses_limit, created_by):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT code FROM promocodes WHERE code = ?", (code,))
    if c.fetchone():
        conn.close()
        return False
    now = datetime.now().isoformat()
    uses_left = uses_limit if uses_limit is not None else -1
    c.execute("INSERT INTO promocodes (code, reward_type, reward_amount, reward_item, uses_limit, created_by, created_at, uses_left) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (code, reward_type, reward_amount, reward_item, uses_limit, created_by, now, uses_left))
    conn.commit()
    conn.close()
    return True

def use_promocode_full(user_id, code):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT reward_type, reward_amount, reward_item, uses_left FROM promocodes WHERE code = ?", (code,))
    row = c.fetchone()
    if not row:
        conn.close()
        return "not_found"
    reward_type, reward_amount, reward_item, uses_left = row
    if uses_left == 0:
        conn.close()
        return "expired"
    c.execute("SELECT 1 FROM promocode_uses WHERE code = ? AND user_id = ?", (code, user_id))
    if c.fetchone():
        conn.close()
        return "already_used"
    if reward_type == "coins":
        update_balance(user_id, reward_amount)
    elif reward_type == "pirozhki":
        add_pirozhki(user_id, reward_item, reward_amount)
    elif reward_type == "xp":
        add_xp(user_id, reward_amount)
    now = datetime.now().isoformat()
    c.execute("INSERT INTO promocode_uses (code, user_id, used_at) VALUES (?, ?, ?)", (code, user_id, now))
    if uses_left != -1:
        c.execute("UPDATE promocodes SET uses_left = uses_left - 1 WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    return (True, reward_type, reward_amount, reward_item)
