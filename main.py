import discord
from discord.ext import commands
from discord.ui import Button, View
import random
import os
from database import *

# --- Конфигурация ---
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise ValueError("Не задана переменная окружения DISCORD_TOKEN")

# ID разрешённого канала (можно задать числом или через переменную окружения)
ALLOWED_CHANNEL_ID = os.getenv('ALLOWED_CHANNEL_ID')
if ALLOWED_CHANNEL_ID:
    ALLOWED_CHANNEL_ID = int(ALLOWED_CHANNEL_ID)
else:
    ALLOWED_CHANNEL_ID = None  # если не задан, бот работает во всех каналах

PREFIX = "!"
DAILY_REWARD = 100
WORK_MIN = 50
WORK_MAX = 150
COIN_NAME = "🪙 монет"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ---------- Глобальная проверка канала ----------
def is_allowed_channel(ctx):
    if ALLOWED_CHANNEL_ID is None:
        return True
    return ctx.channel.id == ALLOWED_CHANNEL_ID

# Проверка перед каждой командой
@bot.before_invoke
async def before_invoke(ctx):
    if not is_allowed_channel(ctx):
        embed = discord.Embed(
            title="⛔ Недоступно",
            description=f"Этот бот работает только в канале <#{ALLOWED_CHANNEL_ID}>.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=5)
        raise commands.CommandError("Команда заблокирована: не тот канал")

# ---------- Вспомогательные классы кнопок (без изменений) ----------
class DailyView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="Забрать", style=discord.ButtonStyle.green)
    async def daily_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Эта кнопка не для вас!", ephemeral=True)
            return
        if not can_daily(self.user_id):
            await interaction.response.send_message("❌ Вы уже получали ежедневный бонус сегодня!", ephemeral=True)
            return
        update_balance(self.user_id, DAILY_REWARD)
        set_daily(self.user_id)
        embed = discord.Embed(
            title="🎁 Ежедневный бонус",
            description=f"Вы получили **{DAILY_REWARD}** {COIN_NAME}!",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

class WorkView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="💼 Поработать", style=discord.ButtonStyle.blurple)
    async def work_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Эта кнопка не для вас!", ephemeral=True)
            return
        earnings = random.randint(WORK_MIN, WORK_MAX)
        update_balance(self.user_id, earnings)
        embed = discord.Embed(
            title="💼 Работа",
            description=f"Вы поработали и заработали **{earnings}** {COIN_NAME}!",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

class FlipView(View):
    def __init__(self, user_id, bet):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.bet = bet

    @discord.ui.button(label="🦅 Орёл", style=discord.ButtonStyle.primary)
    async def eagle_button(self, interaction: discord.Interaction, button: Button):
        await self.process_flip(interaction, "орёл")

    @discord.ui.button(label="🪙 Решка", style=discord.ButtonStyle.primary)
    async def tails_button(self, interaction: discord.Interaction, button: Button):
        await self.process_flip(interaction, "решка")

    async def process_flip(self, interaction: discord.Interaction, choice):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Эта кнопка не для вас!", ephemeral=True)
            return
        result = random.choice(["орёл", "решка"])
        win = (choice == result)
        embed = discord.Embed(title="🎲 Подбрасываем монетку...", color=discord.Color.gold())
        embed.add_field(name="Ваш выбор", value=choice, inline=True)
        embed.add_field(name="Результат", value=result, inline=True)
        if win:
            update_balance(self.user_id, self.bet)
            new_balance = get_balance(self.user_id)
            embed.add_field(name="💰 Вы выиграли!", value=f"+{self.bet} {COIN_NAME}", inline=False)
            embed.set_footer(text=f"Новый баланс: {new_balance} {COIN_NAME}")
            color = discord.Color.green()
        else:
            update_balance(self.user_id, -self.bet)
            new_balance = get_balance(self.user_id)
            embed.add_field(name="😢 Вы проиграли!", value=f"-{self.bet} {COIN_NAME}", inline=False)
            embed.set_footer(text=f"Новый баланс: {new_balance} {COIN_NAME}")
            color = discord.Color.red()
        embed.color = color
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

class ConfirmTransferView(View):
    def __init__(self, sender_id, receiver_id, amount):
        super().__init__(timeout=60)
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.amount = amount

    @discord.ui.button(label="✅ Да, передать", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.sender_id:
            await interaction.response.send_message("❌ Это не ваша транзакция!", ephemeral=True)
            return
        if get_balance(self.sender_id) < self.amount:
            await interaction.response.edit_message(content="❌ Недостаточно средств! Транзакция отменена.", embed=None, view=None)
            self.stop()
            return
        update_balance(self.sender_id, -self.amount)
        update_balance(self.receiver_id, self.amount)
        embed = discord.Embed(
            title="✅ Перевод выполнен",
            description=f"Вы передали **{self.amount}** {COIN_NAME} пользователю <@{self.receiver_id}>",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="❌ Отмена", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.sender_id:
            await interaction.response.send_message("❌ Это не ваша транзакция!", ephemeral=True)
            return
        embed = discord.Embed(
            title="❌ Перевод отменён",
            description="Вы отменили передачу монет.",
            color=discord.Color.dark_red()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

# ---------- Команды (без изменений, но с русскими именами) ----------
@bot.command(name="баланс", aliases=["balance"])
async def balance_cmd(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author
    bal = get_balance(member.id)
    embed = discord.Embed(
        title="💰 Баланс",
        description=f"Баланс {member.mention}: **{bal}** {COIN_NAME}",
        color=discord.Color.blurple()
    )
    await ctx.send(embed=embed)

@bot.command(name="ежедневный", aliases=["daily"])
async def daily_cmd(ctx):
    if not can_daily(ctx.author.id):
        embed = discord.Embed(
            title="❌ Ошибка",
            description="Вы уже получали ежедневный бонус сегодня!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    embed = discord.Embed(
        title="🎁 Ежедневный бонус",
        description=f"Нажмите на кнопку ниже, чтобы получить **{DAILY_REWARD}** {COIN_NAME}.",
        color=discord.Color.gold()
    )
    view = DailyView(ctx.author.id)
    await ctx.send(embed=embed, view=view)

@bot.command(name="работать", aliases=["work"])
async def work_cmd(ctx):
    embed = discord.Embed(
        title="💼 Работа",
        description=f"Нажмите кнопку, чтобы поработать и получить от {WORK_MIN} до {WORK_MAX} {COIN_NAME}.",
        color=discord.Color.blue()
    )
    view = WorkView(ctx.author.id)
    await ctx.send(embed=embed, view=view)

@bot.command(name="передать", aliases=["give"])
async def give_cmd(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        embed = discord.Embed(title="❌ Ошибка", description="Сумма должна быть положительной!", color=discord.Color.red())
        await ctx.send(embed=embed)
        return
    if member == ctx.author:
        embed = discord.Embed(title="❌ Ошибка", description="Нельзя передавать монеты самому себе!", color=discord.Color.red())
        await ctx.send(embed=embed)
        return
    sender_bal = get_balance(ctx.author.id)
    if sender_bal < amount:
        embed = discord.Embed(title="❌ Ошибка", description=f"Недостаточно средств! У вас {sender_bal} {COIN_NAME}.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return
    embed = discord.Embed(
        title="💰 Подтверждение перевода",
        description=f"Вы собираетесь передать **{amount}** {COIN_NAME} пользователю {member.mention}.\nНажмите **✅ Да, передать** для подтверждения.",
        color=discord.Color.orange()
    )
    view = ConfirmTransferView(ctx.author.id, member.id, amount)
    await ctx.send(embed=embed, view=view)

@bot.command(name="монетка", aliases=["flip"])
async def flip_cmd(ctx, bet: int):
    if bet <= 0:
        embed = discord.Embed(title="❌ Ошибка", description="Ставка должна быть положительной!", color=discord.Color.red())
        await ctx.send(embed=embed)
        return
    bal = get_balance(ctx.author.id)
    if bal < bet:
        embed = discord.Embed(title="❌ Ошибка", description=f"Недостаточно монет! Ваш баланс: {bal} {COIN_NAME}.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return
    embed = discord.Embed(
        title="🎲 Орёл или решка?",
        description=f"Ставка: **{bet}** {COIN_NAME}\nВыберите сторону, нажав на кнопку.",
        color=discord.Color.gold()
    )
    view = FlipView(ctx.author.id, bet)
    await ctx.send(embed=embed, view=view)

@bot.command(name="топ", aliases=["top"])
async def top_cmd(ctx, limit: int = 10):
    if limit > 25:
        limit = 25
    rows = get_top_balances(limit)
    if not rows:
        embed = discord.Embed(title="🏆 Таблица лидеров", description="Нет данных.", color=discord.Color.blue())
        await ctx.send(embed=embed)
        return
    embed = discord.Embed(title="🏆 Таблица лидеров", color=discord.Color.blue())
    desc = ""
    for idx, (user_id, bal) in enumerate(rows, start=1):
        user = bot.get_user(user_id)
        name = user.name if user else f"<@{user_id}>"
        desc += f"{idx}. **{name}** — {bal} {COIN_NAME}\n"
    embed.description = desc
    await ctx.send(embed=embed)

@bot.command(name="магазин", aliases=["shop"])
async def shop_cmd(ctx):
    items = get_shop_items()
    if not items:
        embed = discord.Embed(title="🛒 Магазин", description="Магазин пуст. Администратор может добавить товары командой `!добавить_товар`.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return
    embed = discord.Embed(title="🛒 Магазин ролей", color=discord.Color.green())
    for role_id, name, price in items:
        role = ctx.guild.get_role(role_id)
        display_name = role.mention if role else name
        embed.add_field(name=display_name, value=f"{price} {COIN_NAME}", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="добавить_товар", aliases=["add_shop_item"])
@commands.has_permissions(administrator=True)
async def add_shop_item_cmd(ctx, role_id: int, price: int):
    role = ctx.guild.get_role(role_id)
    if not role:
        embed = discord.Embed(title="❌ Ошибка", description="Роль с таким ID не найдена на этом сервере.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return
    add_shop_item(role_id, role.name, price)
    embed = discord.Embed(title="✅ Готово", description=f"Роль {role.mention} добавлена в магазин за {price} {COIN_NAME}.", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="купить", aliases=["buy"])
async def buy_cmd(ctx, role_id: int):
    item = get_shop_item(role_id)
    if not item:
        embed = discord.Embed(title="❌ Ошибка", description="Товар не найден.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return
    role = ctx.guild.get_role(role_id)
    if not role:
        embed = discord.Embed(title="❌ Ошибка", description="Роль не существует на этом сервере.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return
    price = item[1]
    bal = get_balance(ctx.author.id)
    if bal < price:
        embed = discord.Embed(title="❌ Ошибка", description=f"Недостаточно монет! Нужно {price}, у вас {bal}.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return
    if role in ctx.author.roles:
        embed = discord.Embed(title="❌ Ошибка", description="У вас уже есть эта роль.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return
    update_balance(ctx.author.id, -price)
    await ctx.author.add_roles(role)
    embed = discord.Embed(title="✅ Покупка", description=f"Вы купили роль {role.mention} за {price} {COIN_NAME}!", color=discord.Color.green())
    await ctx.send(embed=embed)

# ---------- Обработчик ошибок ----------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandError) and str(error) == "Команда заблокирована: не тот канал":
        # сообщение уже отправлено в before_invoke, ничего не делаем
        return
    if isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(title="❌ Ошибка", description=f"Не хватает аргумента. Используйте `{ctx.prefix}help {ctx.command.name}`", color=discord.Color.red())
        await ctx.send(embed=embed)
    elif isinstance(error, commands.BadArgument):
        embed = discord.Embed(title="❌ Ошибка", description="Неверный аргумент (например, пользователь не найден).", color=discord.Color.red())
        await ctx.send(embed=embed)
    elif isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(title="❌ Ошибка", description="У вас недостаточно прав для выполнения этой команды.", color=discord.Color.red())
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title="❌ Ошибка", description=f"Произошла ошибка: {error}", color=discord.Color.red())
        await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f"✅ Бот {bot.user} запущен!")
    init_db()
    if ALLOWED_CHANNEL_ID:
        print(f"Бот работает только в канале {ALLOWED_CHANNEL_ID}")
    else:
        print("Бот работает во всех каналах")

if __name__ == "__main__":
    bot.run(TOKEN)
