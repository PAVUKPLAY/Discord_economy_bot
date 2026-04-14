import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput, Select
import random
import os
import json
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

DAILY_REWARD = 100
WORK_MIN = 50
WORK_MAX = 150
COIN_NAME = "🪙 монет"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

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
                await interaction.response.send_message("❌ Неверный формат получателя. Укажите ID или упоминание.", ephemeral=True)
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
            await interaction.response.send_message("❌ Нельзя передавать монеты самому себе.", ephemeral=True)
            return
        sender_bal = get_balance(self.sender_id)
        if sender_bal < amount:
            await interaction.response.send_message(f"❌ Недостаточно средств! У вас {sender_bal} {COIN_NAME}.", ephemeral=True)
            return
        update_balance(self.sender_id, -amount)
        update_balance(receiver_id, amount)
        embed = discord.Embed(title="✅ Перевод выполнен", description=f"Вы передали **{amount}** {COIN_NAME} пользователю <@{receiver_id}>", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

class BuyRoleModal(Modal):
    def __init__(self, user_id):
        super().__init__(title="Покупка роли", timeout=120)
        self.user_id = user_id
        self.role_id_input = TextInput(label="ID роли", placeholder="Цифровой ID роли", required=True)
        self.add_item(self.role_id_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            role_id = int(self.role_id_input.value)
        except ValueError:
            await interaction.response.send_message("❌ ID роли должно быть числом.", ephemeral=True)
            return
        item = get_shop_item(role_id)
        if not item:
            await interaction.response.send_message("❌ Товар не найден в магазине.", ephemeral=True)
            return
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("❌ Роль не существует на этом сервере.", ephemeral=True)
            return
        price = item[1]
        bal = get_balance(self.user_id)
        if bal < price:
            await interaction.response.send_message(f"❌ Недостаточно монет! Нужно {price}, у вас {bal}.", ephemeral=True)
            return
        if role in interaction.user.roles:
            await interaction.response.send_message("❌ У вас уже есть эта роль.", ephemeral=True)
            return
        update_balance(self.user_id, -price)
        await interaction.user.add_roles(role)
        embed = discord.Embed(title="✅ Покупка", description=f"Вы купили роль {role.mention} за {price} {COIN_NAME}!", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AddShopItemModal(Modal):
    def __init__(self):
        super().__init__(title="Добавить товар в магазин (монеты)", timeout=120)
        self.role_id_input = TextInput(label="ID роли", placeholder="Цифровой ID", required=True)
        self.price_input = TextInput(label="Цена", placeholder="Число", required=True)
        self.add_item(self.role_id_input)
        self.add_item(self.price_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Только администраторы могут добавлять товары.", ephemeral=True)
            return
        try:
            role_id = int(self.role_id_input.value)
            price = int(self.price_input.value)
        except ValueError:
            await interaction.response.send_message("❌ ID роли и цена должны быть числами.", ephemeral=True)
            return
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("❌ Роль не найдена.", ephemeral=True)
            return
        add_shop_item(role_id, role.name, price)
        embed = discord.Embed(title="✅ Готово", description=f"Роль {role.mention} добавлена в магазин за {price} {COIN_NAME}.", color=discord.Color.green())
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

# ---------- МОДАЛЬНЫЕ ОКНА ДЛЯ ПИРОЖКОВ ----------
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
        self.required = required_ingredients  # dict
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

class BuyRoleWithPirozhkiModal(Modal):
    def __init__(self, user_id, role_id, role_name, pirozhok_type, quantity):
        super().__init__(title=f"Покупка роли {role_name}", timeout=120)
        self.user_id = user_id
        self.role_id = role_id
        self.role_name = role_name
        self.pirozhok_type = pirozhok_type
        self.quantity = quantity
        self.confirm_input = TextInput(label="Подтверждение", placeholder="Введите 'ДА' для покупки", required=True)
        self.add_item(self.confirm_input)

    async def on_submit(self, interaction: discord.Interaction):
        if self.confirm_input.value.strip().upper() != "ДА":
            await interaction.response.send_message("❌ Покупка отменена.", ephemeral=True)
            return
        have = get_pirozhki_quantity(self.user_id, self.pirozhok_type)
        if have < self.quantity:
            await interaction.response.send_message(f"❌ У вас недостаточно пирожков '{self.pirozhok_type}'. Нужно {self.quantity}, у вас {have}.", ephemeral=True)
            return
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message("❌ Роль не найдена на сервере.", ephemeral=True)
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
        if remove_inventory(self.user_id, "pirozhok", recipe_id, self.quantity):
            await interaction.user.add_roles(role)
            embed = discord.Embed(title="✅ Покупка", description=f"Вы купили роль {role.mention} за {self.quantity} пирожков '{self.pirozhok_type}'.", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("❌ Ошибка при списании пирожков. Попробуйте снова.", ephemeral=True)

# ---------- ВСПОМОГАТЕЛЬНЫЕ VIEW ДЛЯ ВЫБОРА ----------
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

class PirozhkiShopView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.add_item(PirozhkiShopSelect(user_id))

class PirozhkiShopSelect(Select):
    def __init__(self, user_id):
        self.user_id = user_id
        items = get_shop_pirozhki_items()
        options = []
        for role_id, role_name, pirozhok_type, qty in items:
            options.append(discord.SelectOption(label=role_name, description=f"{qty} пирожков '{pirozhok_type}'", value=str(role_id)))
        super().__init__(placeholder="Выберите роль для покупки", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это меню не для вас.", ephemeral=True)
            return
        role_id = int(self.values[0])
        item = get_shop_pirozhki_item(role_id)
        if not item:
            await interaction.response.send_message("❌ Товар не найден.", ephemeral=True)
            return
        role_name, pirozhok_type, qty = item
        modal = BuyRoleWithPirozhkiModal(interaction.user.id, role_id, role_name, pirozhok_type, qty)
        await interaction.response.send_modal(modal)

# ---------- ГЛАВНОЕ МЕНЮ С КНОПКАМИ ----------
class EconomyView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💰 Баланс", style=discord.ButtonStyle.blurple, row=0)
    async def balance_button(self, interaction: discord.Interaction, button: Button):
        bal = get_balance(interaction.user.id)
        embed = discord.Embed(title="💰 Ваш баланс", description=f"**{bal}** {COIN_NAME}", color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎁 Ежедневный", style=discord.ButtonStyle.green, row=0)
    async def daily_button(self, interaction: discord.Interaction, button: Button):
        if not can_daily(interaction.user.id):
            embed = discord.Embed(title="❌ Ошибка", description="Вы уже получали бонус сегодня!", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        update_balance(interaction.user.id, DAILY_REWARD)
        set_daily(interaction.user.id)
        embed = discord.Embed(title="🎁 Ежедневный бонус", description=f"Вы получили {DAILY_REWARD} {COIN_NAME}!", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="💼 Работа", style=discord.ButtonStyle.blurple, row=0)
    async def work_button(self, interaction: discord.Interaction, button: Button):
        earnings = random.randint(WORK_MIN, WORK_MAX)
        update_balance(interaction.user.id, earnings)
        embed = discord.Embed(title="💼 Работа", description=f"Вы заработали **{earnings}** {COIN_NAME}!", color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

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

    @discord.ui.button(label="🛒 Магазин (монеты)", style=discord.ButtonStyle.blurple, row=1)
    async def shop_button(self, interaction: discord.Interaction, button: Button):
        items = get_shop_items()
        if not items:
            embed = discord.Embed(title="🛒 Магазин", description="Магазин пуст.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(title="🛒 Магазин ролей (за монеты)", color=discord.Color.green())
        for role_id, name, price in items:
            role = interaction.guild.get_role(role_id)
            display_name = role.mention if role else name
            embed.add_field(name=display_name, value=f"{price} {COIN_NAME}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔨 Купить роль (монеты)", style=discord.ButtonStyle.green, row=1)
    async def buy_button(self, interaction: discord.Interaction, button: Button):
        modal = BuyRoleModal(interaction.user.id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🛒 Ингредиенты", style=discord.ButtonStyle.blurple, row=2)
    async def buy_ingredient_button(self, interaction: discord.Interaction, button: Button):
        view = IngredientSelectView(interaction.user.id)
        embed = discord.Embed(title="🛒 Магазин ингредиентов", description="Выберите ингредиент из списка", color=discord.Color.blue())
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
        embed = discord.Embed(title="💰 Продажа пирожков", description="Выберите тип пирожка", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="🛒 Магазин (пирожки)", style=discord.ButtonStyle.blurple, row=3)
    async def pirozhki_shop_button(self, interaction: discord.Interaction, button: Button):
        items = get_shop_pirozhki_items()
        if not items:
            embed = discord.Embed(title="🛒 Магазин ролей за пирожки", description="Магазин пуст. Администратор может добавить товары командой `!добавить_товар_пирожки`.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(title="🛒 Магазин ролей (за пирожки)", color=discord.Color.purple())
        for role_id, role_name, pirozhok_type, qty in items:
            role = interaction.guild.get_role(role_id)
            display_name = role.mention if role else role_name
            embed.add_field(name=display_name, value=f"{qty} пирожков '{pirozhok_type}'", inline=False)
        view = PirozhkiShopView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="➕ Добавить товар (админ)", style=discord.ButtonStyle.red, row=3)
    async def add_shop_button(self, interaction: discord.Interaction, button: Button):
        modal = AddShopItemModal()
        await interaction.response.send_modal(modal)

# ---------- ТЕКСТОВАЯ КОМАНДА ДЛЯ АДМИНИСТРАТОРА (ДОБАВЛЕНИЕ ТОВАРА ЗА ПИРОЖКИ) ----------
@bot.command(name="добавить_товар_пирожки")
@commands.has_permissions(administrator=True)
async def add_pirozhki_shop_item(ctx, role_id: int, pirozhok_type: str, quantity: int):
    """Добавить роль в магазин за пирожки. Пример: !добавить_товар_пирожки 123456789 'пирожок с картошкой' 5"""
    role = ctx.guild.get_role(role_id)
    if not role:
        await ctx.send("❌ Роль не найдена.")
        return
    recipe = get_recipe_by_name(pirozhok_type)
    if not recipe:
        await ctx.send(f"❌ Рецепт '{pirozhok_type}' не найден. Доступные: пирожок с картошкой, пирожок с мясом, пирожок с луком и яйцом")
        return
    add_shop_pirozhki_item(role_id, role.name, pirozhok_type, quantity)
    await ctx.send(f"✅ Роль {role.mention} добавлена в магазин за {quantity} пирожков '{pirozhok_type}'.")

# ---------- СОБЫТИЯ БОТА ----------
@bot.event
async def on_ready():
    print(f"✅ Бот {bot.user} запущен!")
    init_db()
    channel = bot.get_channel(ALLOWED_CHANNEL_ID)
    if not channel:
        print(f"❌ Канал с ID {ALLOWED_CHANNEL_ID} не найден!")
        return
    async for message in channel.history(limit=50):
        if message.author == bot.user and message.embeds and message.components:
            await message.edit(view=EconomyView())
            print("Главное сообщение обновлено.")
            break
    else:
        embed = discord.Embed(
            title="💎 Экономический бот",
            description=(
                "Нажимайте на кнопки ниже, чтобы взаимодействовать.\n\n"
                f"**{COIN_NAME}** — основная валюта.\n"
                "• `Ежедневный` — 100 монет раз в сутки\n"
                "• `Работа` — от 50 до 150 монет\n"
                "• `Орёл/Решка` — удвоение ставки\n"
                "• `Передать` — перевод монет\n\n"
                "**🥧 Выпечка пирожков:**\n"
                "• Купите ингредиенты, испеките пирожки по рецептам.\n"
                "• Пирожки можно продать за монеты или обменять на роли в специальном магазине.\n\n"
                "**Администратор** может добавлять товары в оба магазина (монеты — кнопкой, пирожки — командой `!добавить_товар_пирожки`)."
            ),
            color=discord.Color.gold()
        )
        await channel.send(embed=embed, view=EconomyView())
        print("Главное сообщение отправлено.")
    print(f"Бот активен в канале {channel.name}")

# ---------- ЗАПУСК ----------
if __name__ == "__main__":
    bot.run(TOKEN)