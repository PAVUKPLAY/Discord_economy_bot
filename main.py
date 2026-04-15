import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput, Select
import random
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from database import *

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise ValueError("Не задан DISCORD_TOKEN")

ALLOWED_CHANNEL_ID = os.getenv('ALLOWED_CHANNEL_ID')
if not ALLOWED_CHANNEL_ID:
    raise ValueError("Не задан ALLOWED_CHANNEL_ID")
ALLOWED_CHANNEL_ID = int(ALLOWED_CHANNEL_ID)

ADMIN_CHANNEL_ID = os.getenv('ADMIN_CHANNEL_ID')
if ADMIN_CHANNEL_ID:
    ADMIN_CHANNEL_ID = int(ADMIN_CHANNEL_ID)

LOG_CHANNEL_ID = os.getenv('LOG_CHANNEL_ID')
if LOG_CHANNEL_ID:
    LOG_CHANNEL_ID = int(LOG_CHANNEL_ID)

COIN_NAME = "🪙 монет"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- Функция отправки логов в канал ----------
async def send_log(admin_name, action, target_name=None, details=None):
    if LOG_CHANNEL_ID:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if channel:
            embed = discord.Embed(title="📋 Лог админ-действия", color=discord.Color.orange())
            embed.add_field(name="Администратор", value=admin_name, inline=True)
            embed.add_field(name="Действие", value=action, inline=True)
            if target_name:
                embed.add_field(name="Цель", value=target_name, inline=True)
            if details:
                embed.add_field(name="Детали", value=details, inline=False)
            embed.timestamp = datetime.now()
            await channel.send(embed=embed)

# ---------- ГЕНЕРАЦИЯ МАТЕМАТИЧЕСКОЙ ЗАДАЧИ ----------
def generate_math_problem():
    operators = ['+', '-', '*']
    op = random.choice(operators)
    if op == '+':
        a = random.randint(1, 10)
        b = random.randint(1, 10)
        answer = a + b
        question = f"{a} + {b}"
    elif op == '-':
        a = random.randint(1, 10)
        b = random.randint(1, a)
        answer = a - b
        question = f"{a} - {b}"
    else:
        a = random.randint(1, 5)
        b = random.randint(1, 5)
        answer = a * b
        question = f"{a} * {b}"
    options = [answer]
    while len(options) < 3:
        fake = answer + random.randint(-3, 3)
        if fake != answer and fake not in options and fake >= 0:
            options.append(fake)
    random.shuffle(options)
    return question, answer, options

# ---------- КЛАСС ДЛЯ РАБОТЫ (МАТЕМАТИЧЕСКАЯ ЗАДАЧА) ----------
class MathProblemView(View):
    def __init__(self, user_id, question, answer, options, reward):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.answer = answer
        self.reward = reward
        self.answered = False
        for opt in options:
            btn = Button(label=str(opt), style=discord.ButtonStyle.primary)
            btn.callback = self.make_callback(opt)
            self.add_item(btn)

    def make_callback(self, option):
        async def callback(interaction: discord.Interaction):
            if self.answered:
                await interaction.response.send_message("❌ Вы уже ответили на этот вопрос.", ephemeral=True)
                return
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ Это задание не для вас.", ephemeral=True)
                return
            self.answered = True
            if option == self.answer:
                update_balance(self.user_id, self.reward)
                embed = discord.Embed(title="✅ Правильно!", description=f"Вы получили {self.reward} {COIN_NAME}!", color=discord.Color.green())
                await interaction.response.edit_message(embed=embed, view=None)
            else:
                embed = discord.Embed(title="❌ Неправильно!", description=f"Правильный ответ: {self.answer}. Вы не получили монет.", color=discord.Color.red())
                await interaction.response.edit_message(embed=embed, view=None)
            self.stop()
        return callback

# ---------- МОДАЛЬНЫЕ ОКНА (базовые) ----------
class TransferModal(Modal):
    def __init__(self, sender_id):
        super().__init__(title="Передача монет", timeout=120)
        self.sender_id = sender_id
        self.receiver_input = TextInput(label="ID или @ упоминание получателя", placeholder="Например: @User или 123456789", required=True)
        self.amount_input = TextInput(label="Сумма", placeholder="Число", required=True)
        self.add_item(self.receiver_input)
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        receiver_text = self.receiver_input.value.strip()
        if receiver_text.startswith('<@') and receiver_text.endswith('>'):
            receiver_id = int(receiver_text.strip('<@!>'))
        else:
            try:
                receiver_id = int(receiver_text)
            except ValueError:
                await interaction.response.send_message("❌ Неверный формат получателя.", ephemeral=True)
                return
        try:
            amount = int(self.amount_input.value)
        except ValueError:
            await interaction.response.send_message("❌ Сумма должна быть числом.", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("❌ Сумма должна быть положительной.", ephemeral=True)
            return
        if receiver_id == self.sender_id:
            await interaction.response.send_message("❌ Нельзя передавать самому себе.", ephemeral=True)
            return
        sender_bal = get_balance(self.sender_id)
        if sender_bal < amount:
            await interaction.response.send_message(f"❌ Недостаточно средств! У вас {sender_bal} {COIN_NAME}.", ephemeral=True)
            return
        update_balance(self.sender_id, -amount)
        update_balance(receiver_id, amount)
        embed = discord.Embed(title="✅ Перевод выполнен", description=f"Вы передали **{amount}** {COIN_NAME} пользователю <@{receiver_id}>", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

class FlipModal(Modal):
    def __init__(self, user_id):
        super().__init__(title="Орёл или решка", timeout=120)
        self.user_id = user_id
        self.bet_input = TextInput(label="Ставка", placeholder="Количество монет", required=True)
        self.add_item(self.bet_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet = int(self.bet_input.value)
        except ValueError:
            await interaction.response.send_message("❌ Ставка должна быть числом.", ephemeral=True)
            return
        if bet <= 0:
            await interaction.response.send_message("❌ Ставка должна быть положительной.", ephemeral=True)
            return
        bal = get_balance(self.user_id)
        if bal < bet:
            await interaction.response.send_message(f"❌ Недостаточно монет! Ваш баланс: {bal} {COIN_NAME}.", ephemeral=True)
            return
        view = FlipChoiceView(self.user_id, bet)
        embed = discord.Embed(title="🎲 Орёл или решка?", description=f"Ставка: **{bet}** {COIN_NAME}\nВыберите сторону:", color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class FlipChoiceView(View):
    def __init__(self, user_id, bet):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.bet = bet

    @discord.ui.button(label="🦅 Орёл", style=discord.ButtonStyle.primary)
    async def eagle(self, interaction: discord.Interaction, button: Button):
        await self.process(interaction, "орёл")

    @discord.ui.button(label="🪙 Решка", style=discord.ButtonStyle.primary)
    async def tails(self, interaction: discord.Interaction, button: Button):
        await self.process(interaction, "решка")

    async def process(self, interaction: discord.Interaction, choice):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Эта кнопка не для вас!", ephemeral=True)
            return
        result = random.choice(["орёл", "решка"])
        win = (choice == result)
        embed = discord.Embed(title="🎲 Результат", color=discord.Color.gold())
        embed.add_field(name="Ваш выбор", value=choice)
        embed.add_field(name="Результат", value=result)
        if win:
            update_balance(self.user_id, self.bet)
            new_bal = get_balance(self.user_id)
            embed.add_field(name="💰 Вы выиграли!", value=f"+{self.bet} {COIN_NAME}")
            embed.set_footer(text=f"Новый баланс: {new_bal} {COIN_NAME}")
            embed.color = discord.Color.green()
        else:
            update_balance(self.user_id, -self.bet)
            new_bal = get_balance(self.user_id)
            embed.add_field(name="😢 Вы проиграли!", value=f"-{self.bet} {COIN_NAME}")
            embed.set_footer(text=f"Новый баланс: {new_bal} {COIN_NAME}")
            embed.color = discord.Color.red()
        await interaction.response.edit_message(embed=embed, view=None)

# ---------- МОДАЛЬНЫЕ ОКНА ДЛЯ ИНГРЕДИЕНТОВ И ПИРОЖКОВ ----------
class BuyIngredientModal(Modal):
    def __init__(self, user_id, ingredient_id, ingredient_name, price):
        super().__init__(title=f"Покупка {ingredient_name}", timeout=120)
        self.user_id = user_id
        self.ingredient_id = ingredient_id
        self.ingredient_name = ingredient_name
        self.price = price
        self.quantity_input = TextInput(label="Количество", placeholder="Сколько штук купить?", required=True)
        self.add_item(self.quantity_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.quantity_input.value)
            if qty <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Введите положительное число.", ephemeral=True)
            return
        total_cost = qty * self.price
        balance = get_balance(self.user_id)
        if balance < total_cost:
            await interaction.response.send_message(f"❌ Недостаточно монет! Нужно {total_cost}, у вас {balance}.", ephemeral=True)
            return
        update_balance(self.user_id, -total_cost)
        add_inventory(self.user_id, "ingredient", self.ingredient_id, qty)
        embed = discord.Embed(title="✅ Покупка", description=f"Вы купили {qty} x **{self.ingredient_name}** за {total_cost} {COIN_NAME}.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

class MakePirozhokModal(Modal):
    def __init__(self, user_id, recipe_id, recipe_name, required_ingredients):
        super().__init__(title=f"Выпечка: {recipe_name}", timeout=120)
        self.user_id = user_id
        self.recipe_id = recipe_id
        self.recipe_name = recipe_name
        self.required = required_ingredients
        self.quantity_input = TextInput(label="Количество пирожков", placeholder="Сколько испечь?", required=True)
        self.add_item(self.quantity_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.quantity_input.value)
            if qty <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Введите положительное число.", ephemeral=True)
            return
        missing = []
        for ing_name, need in self.required.items():
            have = get_ingredient_quantity(self.user_id, ing_name)
            if have < need * qty:
                missing.append(f"{ing_name} (нужно {need*qty}, есть {have})")
        if missing:
            await interaction.response.send_message(f"❌ Не хватает ингредиентов:\n" + "\n".join(missing), ephemeral=True)
            return
        for ing_name, need in self.required.items():
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id FROM ingredients WHERE name = ?", (ing_name,))
            row = c.fetchone()
            conn.close()
            if row:
                ing_id = row[0]
                remove_inventory(self.user_id, "ingredient", ing_id, need * qty)
        add_inventory(self.user_id, "pirozhok", self.recipe_id, qty)
        embed = discord.Embed(title="🍞 Выпечка", description=f"Вы испекли **{qty}** шт. **{self.recipe_name}**!", color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, ephemeral=True)

class SellPirozhokModal(Modal):
    def __init__(self, user_id, recipe_id, recipe_name, sell_price):
        super().__init__(title=f"Продажа {recipe_name}", timeout=120)
        self.user_id = user_id
        self.recipe_id = recipe_id
        self.recipe_name = recipe_name
        self.sell_price = sell_price
        self.quantity_input = TextInput(label="Количество", placeholder="Сколько продать?", required=True)
        self.add_item(self.quantity_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.quantity_input.value)
            if qty <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Введите положительное число.", ephemeral=True)
            return
        have = get_pirozhki_quantity(self.user_id, self.recipe_name)
        if have < qty:
            await interaction.response.send_message(f"❌ У вас только {have} пирожков {self.recipe_name}.", ephemeral=True)
            return
        remove_inventory(self.user_id, "pirozhok", self.recipe_id, qty)
        total = qty * self.sell_price
        update_balance(self.user_id, total)
        embed = discord.Embed(title="💰 Продажа", description=f"Вы продали {qty} шт. **{self.recipe_name}** за {total} {COIN_NAME}.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------- МОДАЛЬНЫЕ ОКНА ДЛЯ МАГАЗИНА РОЛЕЙ (АДМИН) ----------
class AddShopRoleModal(Modal):
    def __init__(self):
        super().__init__(title="Добавить роль в магазин", timeout=120)
        self.role_id_input = TextInput(label="ID роли", placeholder="Цифровой ID роли", required=True)
        self.price_coins_input = TextInput(label="Цена в монетах (0 если не надо)", placeholder="Число", required=True, default="0")
        self.pirozhok_type_input = TextInput(label="Тип пирожка (оставьте пустым если не надо)", placeholder="пирожок с картошкой / мясом / луком и яйцом", required=False)
        self.pirozhok_qty_input = TextInput(label="Количество пирожков (0 если не надо)", placeholder="Число", required=True, default="0")
        self.condition_input = TextInput(label="Условие (or/and)", placeholder="or - можно купить за монеты ИЛИ пирожки; and - нужны и монеты, и пирожки", required=True, default="or")
        self.add_item(self.role_id_input)
        self.add_item(self.price_coins_input)
        self.add_item(self.pirozhok_type_input)
        self.add_item(self.pirozhok_qty_input)
        self.add_item(self.condition_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Только администраторы могут добавлять товары.", ephemeral=True)
            return
        try:
            role_id = int(self.role_id_input.value)
            price_coins = int(self.price_coins_input.value)
            pirozhok_qty = int(self.pirozhok_qty_input.value)
        except ValueError:
            await interaction.response.send_message("❌ ID роли и цены должны быть числами.", ephemeral=True)
            return
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("❌ Роль не найдена.", ephemeral=True)
            return
        pirozhok_type = self.pirozhok_type_input.value.strip()
        if pirozhok_type == "":
            pirozhok_type = None
        if pirozhok_type and pirozhok_qty <= 0:
            await interaction.response.send_message("❌ Если указан тип пирожка, количество должно быть положительным.", ephemeral=True)
            return
        if price_coins <= 0 and (not pirozhok_type or pirozhok_qty <= 0):
            await interaction.response.send_message("❌ Укажите хотя бы один способ оплаты (монеты или пирожки).", ephemeral=True)
            return
        condition = self.condition_input.value.strip().lower()
        if condition not in ('or', 'and'):
            await interaction.response.send_message("❌ Условие должно быть 'or' или 'and'.", ephemeral=True)
            return
        add_shop_role(role_id, role.name, price_coins if price_coins > 0 else None, pirozhok_type, pirozhok_qty if pirozhok_qty > 0 else None, condition)
        embed = discord.Embed(title="✅ Готово", color=discord.Color.green())
        desc = f"Роль {role.mention} добавлена в магазин."
        if price_coins > 0:
            desc += f"\n💰 Цена: {price_coins} {COIN_NAME}"
        if pirozhok_type and pirozhok_qty > 0:
            desc += f"\n🥧 Цена: {pirozhok_qty} шт. '{pirozhok_type}'"
        desc += f"\n📌 Условие: {'ИЛИ' if condition == 'or' else 'И'}"
        embed.description = desc
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log_admin_action(interaction.user.id, interaction.user.name, "add_shop_role", target_id=role_id, target_name=role.name, details=f"coins={price_coins}, pirozhki={pirozhok_type}:{pirozhok_qty}, condition={condition}")
        await send_log(interaction.user.name, "добавил роль в магазин", role.name, f"цена: {desc}")

class BuyRoleChoiceView(View):
    def __init__(self, user_id, role_id, role_name, price_coins, pirozhok_type, pirozhok_qty):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.role_id = role_id
        self.role_name = role_name
        self.price_coins = price_coins
        self.pirozhok_type = pirozhok_type
        self.pirozhok_qty = pirozhok_qty

        if price_coins and price_coins > 0:
            btn_coins = Button(label=f"💰 За {price_coins} {COIN_NAME}", style=discord.ButtonStyle.green)
            btn_coins.callback = self.buy_coins
            self.add_item(btn_coins)

        if pirozhok_type and pirozhok_qty and pirozhok_qty > 0:
            btn_pirozhki = Button(label=f"🥧 За {pirozhok_qty} пирожков '{pirozhok_type}'", style=discord.ButtonStyle.blurple)
            btn_pirozhki.callback = self.buy_pirozhki
            self.add_item(btn_pirozhki)

    async def buy_coins(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это окно не для вас.", ephemeral=True)
            return
        bal = get_balance(self.user_id)
        if bal < self.price_coins:
            await interaction.response.send_message(f"❌ Недостаточно монет! Нужно {self.price_coins}, у вас {bal}.", ephemeral=True)
            return
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message("❌ Роль больше не существует.", ephemeral=True)
            return
        if role in interaction.user.roles:
            await interaction.response.send_message("❌ У вас уже есть эта роль.", ephemeral=True)
            return
        update_balance(self.user_id, -self.price_coins)
        await interaction.user.add_roles(role)
        embed = discord.Embed(title="✅ Покупка", description=f"Вы купили роль {role.mention} за {self.price_coins} {COIN_NAME}!", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    async def buy_pirozhki(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это окно не для вас.", ephemeral=True)
            return
        have = get_pirozhki_quantity(self.user_id, self.pirozhok_type)
        if have < self.pirozhok_qty:
            await interaction.response.send_message(f"❌ Недостаточно пирожков '{self.pirozhok_type}'! Нужно {self.pirozhok_qty}, у вас {have}.", ephemeral=True)
            return
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message("❌ Роль больше не существует.", ephemeral=True)
            return
        if role in interaction.user.roles:
            await interaction.response.send_message("❌ У вас уже есть эта роль.", ephemeral=True)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id FROM recipes WHERE name = ?", (self.pirozhok_type,))
        row = c.fetchone()
        conn.close()
        if not row:
            await interaction.response.send_message("❌ Ошибка: тип пирожка не найден.", ephemeral=True)
            return
        recipe_id = row[0]
        if remove_inventory(self.user_id, "pirozhok", recipe_id, self.pirozhok_qty):
            await interaction.user.add_roles(role)
            embed = discord.Embed(title="✅ Покупка", description=f"Вы купили роль {role.mention} за {self.pirozhok_qty} пирожков '{self.pirozhok_type}'!", color=discord.Color.green())
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await interaction.response.send_message("❌ Ошибка при списании пирожков.", ephemeral=True)
        self.stop()

# ---------- АДМИНСКАЯ ПАНЕЛЬ ----------
class AdminPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💰 Выдать монеты", style=discord.ButtonStyle.green, row=0)
    async def give_coins(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        modal = AdminGiveCoinsModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="💰 Забрать монеты", style=discord.ButtonStyle.red, row=0)
    async def take_coins(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        modal = AdminTakeCoinsModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🥧 Выдать пирожки", style=discord.ButtonStyle.green, row=1)
    async def give_pirozhki(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        modal = AdminGivePirozhkiModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🥧 Забрать пирожки", style=discord.ButtonStyle.red, row=1)
    async def take_pirozhki(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        modal = AdminTakePirozhkiModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="⚙️ Настройка зарплаты", style=discord.ButtonStyle.blurple, row=2)
    async def salary_settings(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        modal = AdminSalaryModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🎁 Ежедневная награда", style=discord.ButtonStyle.blurple, row=2)
    async def daily_reward_settings(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        modal = AdminDailyRewardModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🛒 Добавить роль", style=discord.ButtonStyle.primary, row=3)
    async def add_shop_role(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        modal = AddShopRoleModal()
        await interaction.response.send_modal(modal)

# Модальные окна для админ-панели
class AdminGiveCoinsModal(Modal):
    def __init__(self):
        super().__init__(title="Выдать монеты")
        self.user_input = TextInput(label="ID пользователя", placeholder="Цифровой ID", required=True)
        self.amount_input = TextInput(label="Сумма", placeholder="Число", required=True)
        self.add_item(self.user_input)
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.user_input.value)
            amount = int(self.amount_input.value)
        except ValueError:
            await interaction.response.send_message("❌ ID и сумма должны быть числами.", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("❌ Сумма должна быть положительной.", ephemeral=True)
            return
        update_balance(user_id, amount)
        log_admin_action(interaction.user.id, interaction.user.name, "give_coins", target_id=user_id, details=str(amount))
        await send_log(interaction.user.name, "выдал монеты", f"<@{user_id}>", f"{amount} {COIN_NAME}")
        await interaction.response.send_message(f"✅ Выдано {amount} {COIN_NAME} пользователю <@{user_id}>.", ephemeral=True)

class AdminTakeCoinsModal(Modal):
    def __init__(self):
        super().__init__(title="Забрать монеты")
        self.user_input = TextInput(label="ID пользователя", placeholder="Цифровой ID", required=True)
        self.amount_input = TextInput(label="Сумма", placeholder="Число", required=True)
        self.add_item(self.user_input)
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.user_input.value)
            amount = int(self.amount_input.value)
        except ValueError:
            await interaction.response.send_message("❌ ID и сумма должны быть числами.", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("❌ Сумма должна быть положительной.", ephemeral=True)
            return
        current = get_balance(user_id)
        if current < amount:
            await interaction.response.send_message(f"❌ У пользователя только {current} {COIN_NAME}.", ephemeral=True)
            return
        update_balance(user_id, -amount)
        log_admin_action(interaction.user.id, interaction.user.name, "take_coins", target_id=user_id, details=str(amount))
        await send_log(interaction.user.name, "забрал монеты", f"<@{user_id}>", f"{amount} {COIN_NAME}")
        await interaction.response.send_message(f"✅ Забрано {amount} {COIN_NAME} у пользователя <@{user_id}>.", ephemeral=True)

class AdminGivePirozhkiModal(Modal):
    def __init__(self):
        super().__init__(title="Выдать пирожки")
        self.user_input = TextInput(label="ID пользователя", placeholder="Цифровой ID", required=True)
        self.type_input = TextInput(label="Тип пирожка", placeholder="пирожок с картошкой / мясом / луком и яйцом", required=True)
        self.quantity_input = TextInput(label="Количество", placeholder="Число", required=True)
        self.add_item(self.user_input)
        self.add_item(self.type_input)
        self.add_item(self.quantity_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.user_input.value)
            quantity = int(self.quantity_input.value)
        except ValueError:
            await interaction.response.send_message("❌ ID и количество должны быть числами.", ephemeral=True)
            return
        pirozhok_type = self.type_input.value.strip().lower()
        recipe = get_recipe_by_name(pirozhok_type)
        if not recipe:
            await interaction.response.send_message("❌ Неверный тип пирожка. Доступные: пирожок с картошкой, пирожок с мясом, пирожок с луком и яйцом", ephemeral=True)
            return
        if quantity <= 0:
            await interaction.response.send_message("❌ Количество должно быть положительным.", ephemeral=True)
            return
        add_pirozhki(user_id, pirozhok_type, quantity)
        log_admin_action(interaction.user.id, interaction.user.name, "give_pirozhki", target_id=user_id, details=f"{pirozhok_type} x{quantity}")
        await send_log(interaction.user.name, "выдал пирожки", f"<@{user_id}>", f"{quantity} шт. '{pirozhok_type}'")
        await interaction.response.send_message(f"✅ Выдано {quantity} пирожков '{pirozhok_type}' пользователю <@{user_id}>.", ephemeral=True)

class AdminTakePirozhkiModal(Modal):
    def __init__(self):
        super().__init__(title="Забрать пирожки")
        self.user_input = TextInput(label="ID пользователя", placeholder="Цифровой ID", required=True)
        self.type_input = TextInput(label="Тип пирожка", placeholder="пирожок с картошкой / мясом / луком и яйцом", required=True)
        self.quantity_input = TextInput(label="Количество", placeholder="Число", required=True)
        self.add_item(self.user_input)
        self.add_item(self.type_input)
        self.add_item(self.quantity_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.user_input.value)
            quantity = int(self.quantity_input.value)
        except ValueError:
            await interaction.response.send_message("❌ ID и количество должны быть числами.", ephemeral=True)
            return
        pirozhok_type = self.type_input.value.strip().lower()
        recipe = get_recipe_by_name(pirozhok_type)
        if not recipe:
            await interaction.response.send_message("❌ Неверный тип пирожка.", ephemeral=True)
            return
        if quantity <= 0:
            await interaction.response.send_message("❌ Количество должно быть положительным.", ephemeral=True)
            return
        current = get_pirozhki_quantity(user_id, pirozhok_type)
        if current < quantity:
            await interaction.response.send_message(f"❌ У пользователя только {current} пирожков '{pirozhok_type}'.", ephemeral=True)
            return
        if remove_pirozhki(user_id, pirozhok_type, quantity):
            log_admin_action(interaction.user.id, interaction.user.name, "take_pirozhki", target_id=user_id, details=f"{pirozhok_type} x{quantity}")
            await send_log(interaction.user.name, "забрал пирожки", f"<@{user_id}>", f"{quantity} шт. '{pirozhok_type}'")
            await interaction.response.send_message(f"✅ Забрано {quantity} пирожков '{pirozhok_type}' у пользователя <@{user_id}>.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Ошибка при списании.", ephemeral=True)

class AdminSalaryModal(Modal):
    def __init__(self):
        super().__init__(title="Настройка зарплаты")
        self.min_input = TextInput(label="Мин. зарплата", placeholder=f"Текущая: {get_work_min()}", required=True)
        self.max_input = TextInput(label="Макс. зарплата", placeholder=f"Текущая: {get_work_max()}", required=True)
        self.add_item(self.min_input)
        self.add_item(self.max_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_min = int(self.min_input.value)
            new_max = int(self.max_input.value)
        except ValueError:
            await interaction.response.send_message("❌ Введите числа.", ephemeral=True)
            return
        if new_min <= 0 or new_max <= 0 or new_min > new_max:
            await interaction.response.send_message("❌ Неверные значения: мин > 0, макс > 0, мин <= макс.", ephemeral=True)
            return
        set_work_min(new_min)
        set_work_max(new_max)
        log_admin_action(interaction.user.id, interaction.user.name, "set_work_salary", details=f"min={new_min}, max={new_max}")
        await send_log(interaction.user.name, "изменил зарплату за работу", None, f"от {new_min} до {new_max}")
        await interaction.response.send_message(f"✅ Зарплата установлена: от {new_min} до {new_max} {COIN_NAME}.", ephemeral=True)
        channel = bot.get_channel(ALLOWED_CHANNEL_ID)
        if channel:
            await EconomyView.update_main_embed(channel)

class AdminDailyRewardModal(Modal):
    def __init__(self):
        super().__init__(title="Изменить ежедневную награду")
        self.reward_input = TextInput(label="Новая сумма", placeholder=f"Текущая: {get_daily_reward()}", required=True)
        self.add_item(self.reward_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_reward = int(self.reward_input.value)
            if new_reward <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Введите положительное число.", ephemeral=True)
            return
        set_daily_reward(new_reward)
        log_admin_action(interaction.user.id, interaction.user.name, "set_daily_reward", details=str(new_reward))
        await send_log(interaction.user.name, "изменил ежедневную награду", None, f"{new_reward} {COIN_NAME}")
        await interaction.response.send_message(f"✅ Ежедневная награда изменена на {new_reward} {COIN_NAME}.", ephemeral=True)
        channel = bot.get_channel(ALLOWED_CHANNEL_ID)
        if channel:
            await EconomyView.update_main_embed(channel)

# ---------- ВСПОМОГАТЕЛЬНЫЕ VIEW ДЛЯ ВЫБОРА (пользовательские) ----------
class IngredientSelectView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.add_item(IngredientSelect(user_id))

class IngredientSelect(Select):
    def __init__(self, user_id):
        self.user_id = user_id
        ingredients = get_all_ingredients()
        options = []
        for ing_id, name, price in ingredients:
            options.append(discord.SelectOption(label=name, description=f"{price} монет/шт", value=str(ing_id)))
        super().__init__(placeholder="Выберите ингредиент для покупки", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это меню не для вас.", ephemeral=True)
            return
        ing_id = int(self.values[0])
        ingredients = get_all_ingredients()
        ing = next((i for i in ingredients if i[0] == ing_id), None)
        if not ing:
            await interaction.response.send_message("❌ Ингредиент не найден.", ephemeral=True)
            return
        modal = BuyIngredientModal(interaction.user.id, ing_id, ing[1], ing[2])
        await interaction.response.send_modal(modal)

class RecipeSelectView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.add_item(RecipeSelect(user_id))

class RecipeSelect(Select):
    def __init__(self, user_id):
        self.user_id = user_id
        recipes = get_all_recipes()
        options = []
        for rec_id, name, ing_json, sell_price in recipes:
            options.append(discord.SelectOption(label=name, description=f"Продажа: {sell_price} монет", value=str(rec_id)))
        super().__init__(placeholder="Выберите рецепт", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это меню не для вас.", ephemeral=True)
            return
        rec_id = int(self.values[0])
        recipes = get_all_recipes()
        rec = next((r for r in recipes if r[0] == rec_id), None)
        if not rec:
            await interaction.response.send_message("❌ Рецепт не найден.", ephemeral=True)
            return
        required = json.loads(rec[2])
        modal = MakePirozhokModal(interaction.user.id, rec_id, rec[1], required)
        await interaction.response.send_modal(modal)

class SellPirozhokSelectView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.add_item(SellPirozhokSelect(user_id))

class SellPirozhokSelect(Select):
    def __init__(self, user_id):
        self.user_id = user_id
        recipes = get_all_recipes()
        options = []
        for rec_id, name, ing_json, sell_price in recipes:
            options.append(discord.SelectOption(label=name, description=f"Цена: {sell_price} монет", value=f"{rec_id}|{sell_price}"))
        super().__init__(placeholder="Какой пирожок продать?", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это меню не для вас.", ephemeral=True)
            return
        parts = self.values[0].split('|')
        rec_id = int(parts[0])
        sell_price = int(parts[1])
        recipes = get_all_recipes()
        rec = next((r for r in recipes if r[0] == rec_id), None)
        if not rec:
            await interaction.response.send_message("❌ Рецепт не найден.", ephemeral=True)
            return
        modal = SellPirozhokModal(interaction.user.id, rec_id, rec[1], sell_price)
        await interaction.response.send_modal(modal)

class ShopSelectView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.add_item(ShopSelect(user_id))

class ShopSelect(Select):
    def __init__(self, user_id):
        self.user_id = user_id
        roles = get_shop_roles()
        options = []
        for role_id, role_name, price_coins, pirozhok_type, pirozhok_qty, condition in roles:
            label = role_name[:100]
            description = []
            if price_coins and price_coins > 0:
                description.append(f"{price_coins} монет")
            if pirozhok_type and pirozhok_qty and pirozhok_qty > 0:
                description.append(f"{pirozhok_qty} пирожков")
            if condition == 'and':
                desc = " и ".join(description) if description else "нет цены"
            else:
                desc = " или ".join(description) if description else "нет цены"
            options.append(discord.SelectOption(label=label, description=desc[:100], value=str(role_id)))
        super().__init__(placeholder="Выберите роль для покупки", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это меню не для вас.", ephemeral=True)
            return
        role_id = int(self.values[0])
        role_data = get_shop_role(role_id)
        if not role_data:
            await interaction.response.send_message("❌ Роль не найдена в магазине.", ephemeral=True)
            return
        role_name, price_coins, pirozhok_type, pirozhok_qty, condition = role_data
        has_coins = price_coins and price_coins > 0
        has_pirozhki = pirozhok_type and pirozhok_qty and pirozhok_qty > 0
        if has_coins and has_pirozhki and condition == 'and':
            bal = get_balance(interaction.user.id)
            have_p = get_pirozhki_quantity(interaction.user.id, pirozhok_type)
            if bal < price_coins or have_p < pirozhok_qty:
                await interaction.response.send_message(f"❌ Недостаточно! Нужно {price_coins} {COIN_NAME} и {pirozhok_qty} пирожков '{pirozhok_type}'.", ephemeral=True)
                return
            role = interaction.guild.get_role(role_id)
            if not role:
                await interaction.response.send_message("❌ Роль больше не существует.", ephemeral=True)
                return
            if role in interaction.user.roles:
                await interaction.response.send_message("❌ У вас уже есть эта роль.", ephemeral=True)
                return
            update_balance(interaction.user.id, -price_coins)
            recipe = get_recipe_by_name(pirozhok_type)
            if recipe:
                remove_inventory(interaction.user.id, "pirozhok", recipe[0], pirozhok_qty)
            await interaction.user.add_roles(role)
            embed = discord.Embed(title="✅ Покупка", description=f"Вы купили роль {role.mention} за {price_coins} {COIN_NAME} и {pirozhok_qty} пирожков '{pirozhok_type}'!", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        elif has_coins and has_pirozhki and condition == 'or':
            view = BuyRoleChoiceView(interaction.user.id, role_id, role_name, price_coins, pirozhok_type, pirozhok_qty)
            embed = discord.Embed(title=f"Покупка роли {role_name}", description="Выберите способ оплаты:", color=discord.Color.orange())
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        elif has_coins and not has_pirozhki:
            bal = get_balance(interaction.user.id)
            if bal < price_coins:
                await interaction.response.send_message(f"❌ Недостаточно монет! Нужно {price_coins}, у вас {bal}.", ephemeral=True)
                return
            role = interaction.guild.get_role(role_id)
            if not role:
                await interaction.response.send_message("❌ Роль больше не существует.", ephemeral=True)
                return
            if role in interaction.user.roles:
                await interaction.response.send_message("❌ У вас уже есть эта роль.", ephemeral=True)
                return
            update_balance(interaction.user.id, -price_coins)
            await interaction.user.add_roles(role)
            embed = discord.Embed(title="✅ Покупка", description=f"Вы купили роль {role.mention} за {price_coins} {COIN_NAME}!", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        elif has_pirozhki and not has_coins:
            have = get_pirozhki_quantity(interaction.user.id, pirozhok_type)
            if have < pirozhok_qty:
                await interaction.response.send_message(f"❌ Недостаточно пирожков '{pirozhok_type}'! Нужно {pirozhok_qty}, у вас {have}.", ephemeral=True)
                return
            role = interaction.guild.get_role(role_id)
            if not role:
                await interaction.response.send_message("❌ Роль больше не существует.", ephemeral=True)
                return
            if role in interaction.user.roles:
                await interaction.response.send_message("❌ У вас уже есть эта роль.", ephemeral=True)
                return
            recipe = get_recipe_by_name(pirozhok_type)
            if recipe:
                remove_inventory(interaction.user.id, "pirozhok", recipe[0], pirozhok_qty)
            await interaction.user.add_roles(role)
            embed = discord.Embed(title="✅ Покупка", description=f"Вы купили роль {role.mention} за {pirozhok_qty} пирожков '{pirozhok_type}'!", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("❌ Эта роль не имеет цены.", ephemeral=True)

# ---------- ГЛАВНОЕ МЕНЮ (ПОЛЬЗОВАТЕЛЬСКОЕ) ----------
class EconomyView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @staticmethod
    async def update_main_embed(channel):
        work_min = get_work_min()
        work_max = get_work_max()
        daily_reward = get_daily_reward()
        embed = discord.Embed(
            title="💎 Экономический бот",
            description=(
                f"**{COIN_NAME}** — основная валюта.\n\n"
                f"🎁 **Ежедневный бонус:** {daily_reward} {COIN_NAME}\n"
                f"💼 **Работа:** {work_min} - {work_max} {COIN_NAME} (решите пример)\n"
                "• 20 попыток в 10 минут\n\n"
                "🎲 **Орёл/Решка:** удвоение ставки\n"
                "💸 **Передать монеты**\n\n"
                "**🥧 Выпечка пирожков:**\n"
                "• Купите ингредиенты, испеките пирожки.\n"
                "• Продайте или обменяйте на роли."
            ),
            color=discord.Color.gold()
        )
        async for message in channel.history(limit=50):
            if message.author == bot.user and message.embeds:
                await message.edit(embed=embed, view=EconomyView())
                return
        await channel.send(embed=embed, view=EconomyView())

    @discord.ui.button(label="💰 Баланс", style=discord.ButtonStyle.blurple, row=0)
    async def balance_button(self, interaction: discord.Interaction, button: Button):
        bal = get_balance(interaction.user.id)
        embed = discord.Embed(title="💰 Ваш баланс", description=f"**{bal}** {COIN_NAME}", color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎁 Ежедневный", style=discord.ButtonStyle.green, row=0)
    async def daily_button(self, interaction: discord.Interaction, button: Button):
        remaining = get_daily_cooldown_seconds(interaction.user.id)
        if remaining > 0:
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            seconds = remaining % 60
            await interaction.response.send_message(f"❌ Вы уже получали бонус сегодня. Следующая награда через {hours}ч {minutes}м {seconds}с.", ephemeral=True)
            return
        reward = get_daily_reward()
        update_balance(interaction.user.id, reward)
        set_daily(interaction.user.id)
        embed = discord.Embed(title="🎁 Ежедневный бонус", description=f"Вы получили {reward} {COIN_NAME}!", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="💼 Работа", style=discord.ButtonStyle.blurple, row=0)
    async def work_button(self, interaction: discord.Interaction, button: Button):
        if not can_work(interaction.user.id):
            remaining = get_work_cooldown_remaining(interaction.user.id)
            minutes = remaining // 60
            seconds = remaining % 60
            await interaction.response.send_message(f"❌ Вы использовали все 20 попыток работы за последние 10 минут. Следующая попытка через {minutes}м {seconds}с.", ephemeral=True)
            return
        reward = random.randint(get_work_min(), get_work_max())
        question, answer, options = generate_math_problem()
        embed = discord.Embed(title="🧮 Математическая задача", description=f"Решите пример:\n**{question}**", color=discord.Color.blue())
        view = MathProblemView(interaction.user.id, question, answer, options, reward)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        add_work_use(interaction.user.id)

    @discord.ui.button(label="💸 Передать", style=discord.ButtonStyle.green, row=0)
    async def transfer_button(self, interaction: discord.Interaction, button: Button):
        modal = TransferModal(interaction.user.id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🎲 Орёл/Решка", style=discord.ButtonStyle.primary, row=1)
    async def flip_button(self, interaction: discord.Interaction, button: Button):
        modal = FlipModal(interaction.user.id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🏆 Топ", style=discord.ButtonStyle.blurple, row=1)
    async def top_button(self, interaction: discord.Interaction, button: Button):
        rows = get_top_balances(10)
        if not rows:
            embed = discord.Embed(title="🏆 Топ", description="Нет данных.", color=discord.Color.blue())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(title="🏆 Таблица лидеров", color=discord.Color.blue())
        desc = ""
        for idx, (user_id, bal) in enumerate(rows, start=1):
            user = bot.get_user(user_id)
            name = user.name if user else f"<@{user_id}>"
            desc += f"{idx}. **{name}** — {bal} {COIN_NAME}\n"
        embed.description = desc
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🛒 Магазин", style=discord.ButtonStyle.blurple, row=1)
    async def shop_button(self, interaction: discord.Interaction, button: Button):
        roles = get_shop_roles()
        if not roles:
            embed = discord.Embed(title="🛒 Магазин", description="Магазин пуст.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(title="🛒 Магазин ролей", color=discord.Color.green())
        for role_id, role_name, price_coins, pirozhok_type, pirozhok_qty, condition in roles:
            role = interaction.guild.get_role(role_id)
            display_name = role.name if role else role_name
            text = []
            if price_coins and price_coins > 0:
                text.append(f"{price_coins} {COIN_NAME}")
            if pirozhok_type and pirozhok_qty and pirozhok_qty > 0:
                text.append(f"{pirozhok_qty} пирожков '{pirozhok_type}'")
            if condition == 'and':
                value = " и ".join(text)
            else:
                value = " или ".join(text)
            embed.add_field(name=display_name, value=value, inline=False)
        view = ShopSelectView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="🛒 Ингредиенты", style=discord.ButtonStyle.blurple, row=2)
    async def buy_ingredient_button(self, interaction: discord.Interaction, button: Button):
        view = IngredientSelectView(interaction.user.id)
        embed = discord.Embed(title="🛒 Магазин ингредиентов", description="Выберите ингредиент", color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="🍞 Выпечка", style=discord.ButtonStyle.primary, row=2)
    async def bake_button(self, interaction: discord.Interaction, button: Button):
        view = RecipeSelectView(interaction.user.id)
        embed = discord.Embed(title="🍞 Выпечка пирожков", description="Выберите рецепт", color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="🥧 Мои пирожки", style=discord.ButtonStyle.blurple, row=2)
    async def my_pirozhki_button(self, interaction: discord.Interaction, button: Button):
        inv = get_all_pirozhki(interaction.user.id)
        if not inv:
            embed = discord.Embed(title="🥧 Ваши пирожки", description="У вас нет пирожков.", color=discord.Color.blue())
        else:
            desc = "\n".join([f"**{name}**: {qty} шт." for name, qty in inv.items()])
            embed = discord.Embed(title="🥧 Ваши пирожки", description=desc, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="💰 Продать пирожки", style=discord.ButtonStyle.green, row=2)
    async def sell_pirozhki_button(self, interaction: discord.Interaction, button: Button):
        view = SellPirozhokSelectView(interaction.user.id)
        embed = discord.Embed(title="💰 Продажа пирожков", description="Выберите тип", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ---------- СОБЫТИЯ БОТА ----------
@bot.event
async def on_ready():
    print(f"✅ Бот {bot.user} запущен!")
    init_db()
    # Основной канал
    channel = bot.get_channel(ALLOWED_CHANNEL_ID)
    if channel:
        await EconomyView.update_main_embed(channel)
        print("Главное сообщение обновлено.")
    else:
        print(f"❌ Канал {ALLOWED_CHANNEL_ID} не найден!")

    # Админ-канал
    if ADMIN_CHANNEL_ID:
        admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
        if admin_channel:
            async for message in admin_channel.history(limit=50):
                if message.author == bot.user and message.embeds and "Админ-панель" in (message.embeds[0].title if message.embeds else ""):
                    await message.edit(view=AdminPanelView())
                    print("Админ-панель обновлена.")
                    break
            else:
                embed = discord.Embed(title="🛠️ Админ-панель", description="Управление экономикой сервера", color=discord.Color.red())
                await admin_channel.send(embed=embed, view=AdminPanelView())
                print("Админ-панель отправлена.")
        else:
            print(f"❌ Админ-канал {ADMIN_CHANNEL_ID} не найден!")

    # Канал логов
    if LOG_CHANNEL_ID:
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            print(f"Логи будут отправляться в канал {log_channel.name}")
        else:
            print(f"❌ Канал логов {LOG_CHANNEL_ID} не найден!")

# ---------- ЗАПУСК ----------
if __name__ == "__main__":
    bot.run(TOKEN)
