import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import random
import os
from dotenv import load_dotenv
from database import *

# Загружаем переменные из .env (если файл существует)
load_dotenv()

# --- Конфигурация из переменных окружения ---
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise ValueError("Не задана переменная окружения DISCORD_TOKEN")

ALLOWED_CHANNEL_ID = os.getenv('ALLOWED_CHANNEL_ID')
if not ALLOWED_CHANNEL_ID:
    raise ValueError("Не задана переменная окружения ALLOWED_CHANNEL_ID")
ALLOWED_CHANNEL_ID = int(ALLOWED_CHANNEL_ID)

# Настройки экономики
DAILY_REWARD = 100
WORK_MIN = 50
WORK_MAX = 150
COIN_NAME = "🪙 монет"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)  # префикс не используется, но нужен

# ---------- Модальные окна ----------
class TransferModal(Modal):
    def __init__(self, sender_id):
        super().__init__(title="Передача монет", timeout=120)
        self.sender_id = sender_id
        self.receiver_input = TextInput(
            label="ID или @ упоминание получателя",
            placeholder="Например: @User или 123456789",
            required=True
        )
        self.amount_input = TextInput(
            label="Сумма",
            placeholder="Число",
            required=True
        )
        self.add_item(self.receiver_input)
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Парсим получателя
        receiver_text = self.receiver_input.value.strip()
        if receiver_text.startswith('<@') and receiver_text.endswith('>'):
            receiver_id = int(receiver_text.strip('<@!>'))
        else:
            try:
                receiver_id = int(receiver_text)
            except ValueError:
                await interaction.response.send_message("❌ Неверный формат получателя. Укажите ID или упоминание.", ephemeral=True)
                return
        # Проверяем сумму
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
        embed = discord.Embed(
            title="✅ Перевод выполнен",
            description=f"Вы передали **{amount}** {COIN_NAME} пользователю <@{receiver_id}>",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class BuyRoleModal(Modal):
    def __init__(self, user_id):
        super().__init__(title="Покупка роли", timeout=120)
        self.user_id = user_id
        self.role_id_input = TextInput(
            label="ID роли",
            placeholder="Цифровой ID роли",
            required=True
        )
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
        embed = discord.Embed(
            title="✅ Покупка",
            description=f"Вы купили роль {role.mention} за {price} {COIN_NAME}!",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AddShopItemModal(Modal):
    def __init__(self):
        super().__init__(title="Добавить товар в магазин", timeout=120)
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
        embed = discord.Embed(
            title="✅ Готово",
            description=f"Роль {role.mention} добавлена в магазин за {price} {COIN_NAME}.",
            color=discord.Color.green()
        )
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
        embed = discord.Embed(
            title="🎲 Орёл или решка?",
            description=f"Ставка: **{bet}** {COIN_NAME}\nВыберите сторону:",
            color=discord.Color.gold()
        )
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

# ---------- Главное меню с кнопками ----------
class EconomyView(View):
    def __init__(self):
        super().__init__(timeout=None)  # бесконечное время

    @discord.ui.button(label="💰 Баланс", style=discord.ButtonStyle.blurple)
    async def balance_button(self, interaction: discord.Interaction, button: Button):
        bal = get_balance(interaction.user.id)
        embed = discord.Embed(title="💰 Ваш баланс", description=f"**{bal}** {COIN_NAME}", color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎁 Ежедневный", style=discord.ButtonStyle.green)
    async def daily_button(self, interaction: discord.Interaction, button: Button):
        if not can_daily(interaction.user.id):
            embed = discord.Embed(title="❌ Ошибка", description="Вы уже получали бонус сегодня!", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        update_balance(interaction.user.id, DAILY_REWARD)
        set_daily(interaction.user.id)
        embed = discord.Embed(title="🎁 Ежедневный бонус", description=f"Вы получили {DAILY_REWARD} {COIN_NAME}!", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="💼 Работа", style=discord.ButtonStyle.blurple)
    async def work_button(self, interaction: discord.Interaction, button: Button):
        earnings = random.randint(WORK_MIN, WORK_MAX)
        update_balance(interaction.user.id, earnings)
        embed = discord.Embed(title="💼 Работа", description=f"Вы заработали **{earnings}** {COIN_NAME}!", color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="💸 Передать", style=discord.ButtonStyle.green)
    async def transfer_button(self, interaction: discord.Interaction, button: Button):
        modal = TransferModal(interaction.user.id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🎲 Орёл/Решка", style=discord.ButtonStyle.primary)
    async def flip_button(self, interaction: discord.Interaction, button: Button):
        modal = FlipModal(interaction.user.id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🏆 Топ", style=discord.ButtonStyle.blurple)
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

    @discord.ui.button(label="🛒 Магазин", style=discord.ButtonStyle.blurple)
    async def shop_button(self, interaction: discord.Interaction, button: Button):
        items = get_shop_items()
        if not items:
            embed = discord.Embed(title="🛒 Магазин", description="Магазин пуст.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(title="🛒 Магазин ролей", color=discord.Color.green())
        for role_id, name, price in items:
            role = interaction.guild.get_role(role_id)
            display_name = role.mention if role else name
            embed.add_field(name=display_name, value=f"{price} {COIN_NAME}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔨 Купить роль", style=discord.ButtonStyle.green)
    async def buy_button(self, interaction: discord.Interaction, button: Button):
        modal = BuyRoleModal(interaction.user.id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="➕ Добавить товар (админ)", style=discord.ButtonStyle.red)
    async def add_shop_button(self, interaction: discord.Interaction, button: Button):
        modal = AddShopItemModal()
        await interaction.response.send_modal(modal)

# ---------- События бота ----------
@bot.event
async def on_ready():
    print(f"✅ Бот {bot.user} запущен!")
    init_db()
    channel = bot.get_channel(ALLOWED_CHANNEL_ID)
    if not channel:
        print(f"❌ Канал с ID {ALLOWED_CHANNEL_ID} не найден!")
        return
    # Ищем существующее сообщение бота с кнопками
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
                f"**{COIN_NAME}** — валюта сервера.\n"
                "• `Ежедневный` — 100 монет раз в сутки\n"
                "• `Работа` — от 50 до 150 монет\n"
                "• `Орёл/Решка` — удвоение ставки\n"
                "• `Передать` — перевод монет\n"
                "• `Магазин` — покупка ролей\n\n"
                "**Администратор** может добавлять товары через кнопку."
            ),
            color=discord.Color.gold()
        )
        await channel.send(embed=embed, view=EconomyView())
        print("Главное сообщение отправлено.")
    print(f"Бот активен в канале {channel.name}")

# ---------- Запуск ----------
if __name__ == "__main__":
    bot.run(TOKEN)