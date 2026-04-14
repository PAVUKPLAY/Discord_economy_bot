import discord
from discord.ext import commands
import random
import os
from database import *

# --- Конфигурация из переменных окружения ---
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise ValueError("Не задана переменная окружения DISCORD_TOKEN")

PREFIX = "!"
DAILY_REWARD = 100
WORK_MIN = 50
WORK_MAX = 150
COIN_NAME = "🪙 монет"

# --- Настройки intents ---
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# --- Событие запуска ---
@bot.event
async def on_ready():
    print(f"✅ Бот {bot.user} запущен!")
    init_db()
    # Добавим пример товара в магазин (замените ROLE_ID на реальный ID роли на вашем сервере)
    # Можно также добавить через команду администратора, но для демо - раскомментируйте и укажите ID
    # add_shop_item(123456789012345678, "VIP", 5000)
    print("База данных инициализирована.")

# --- Команды ---
@bot.command()
async def balance(ctx, member: discord.Member = None):
    """Показать баланс"""
    if member is None:
        member = ctx.author
    bal = get_balance(member.id)
    await ctx.send(f"💰 Баланс {member.mention}: {bal} {COIN_NAME}")

@bot.command()
async def daily(ctx):
    """Ежедневный бонус"""
    user_id = ctx.author.id
    if not can_daily(user_id):
        await ctx.send(f"❌ {ctx.author.mention}, вы уже получали ежедневный бонус сегодня!")
        return
    update_balance(user_id, DAILY_REWARD)
    set_daily(user_id)
    await ctx.send(f"🎁 {ctx.author.mention}, вы получили {DAILY_REWARD} {COIN_NAME}!")

@bot.command()
async def work(ctx):
    """Случайный заработок"""
    earnings = random.randint(WORK_MIN, WORK_MAX)
    update_balance(ctx.author.id, earnings)
    await ctx.send(f"💼 {ctx.author.mention}, вы поработали и заработали {earnings} {COIN_NAME}!")

@bot.command()
async def give(ctx, member: discord.Member, amount: int):
    """Передать монеты"""
    if amount <= 0:
        await ctx.send("Сумма должна быть положительной!")
        return
    if member == ctx.author:
        await ctx.send("Нельзя передавать монеты самому себе!")
        return
    sender_bal = get_balance(ctx.author.id)
    if sender_bal < amount:
        await ctx.send(f"❌ Недостаточно средств! У вас {sender_bal} {COIN_NAME}.")
        return
    update_balance(ctx.author.id, -amount)
    update_balance(member.id, amount)
    await ctx.send(f"✅ {ctx.author.mention} передал {amount} {COIN_NAME} пользователю {member.mention}!")

@bot.command()
async def flip(ctx, bet: int):
    """Орёл или решка"""
    if bet <= 0:
        await ctx.send("Ставка должна быть положительной!")
        return
    bal = get_balance(ctx.author.id)
    if bal < bet:
        await ctx.send(f"Недостаточно монет! Ваш баланс: {bal}")
        return
    result = random.choice(["орёл", "решка"])
    embed = discord.Embed(title="🎲 Подбрасываем монетку...", color=discord.Color.gold())
    embed.add_field(name="Результат", value=f"Выпал **{result}**!", inline=False)
    if result == "орёл":
        update_balance(ctx.author.id, bet)   # выигрыш = ставка (чистая прибыль)
        embed.add_field(name="💰 Вы выиграли!", value=f"+{bet} {COIN_NAME}", inline=False)
    else:
        update_balance(ctx.author.id, -bet)
        embed.add_field(name="😢 Вы проиграли!", value=f"-{bet} {COIN_NAME}", inline=False)
    embed.set_footer(text=f"Ваш новый баланс: {get_balance(ctx.author.id)} {COIN_NAME}")
    await ctx.send(embed=embed)

@bot.command()
async def top(ctx, limit: int = 10):
    """Топ богачей"""
    if limit > 25:
        limit = 25
    rows = get_top_balances(limit)
    if not rows:
        await ctx.send("Нет данных.")
        return
    embed = discord.Embed(title="🏆 Таблица лидеров", color=discord.Color.blue())
    desc = ""
    for idx, (user_id, bal) in enumerate(rows, start=1):
        user = bot.get_user(user_id)
        name = user.name if user else f"<@{user_id}>"
        desc += f"{idx}. **{name}** — {bal} {COIN_NAME}\n"
    embed.description = desc
    await ctx.send(embed=embed)

@bot.command()
async def shop(ctx):
    """Показать магазин"""
    conn = sqlite3.connect("economy.db")
    c = conn.cursor()
    c.execute("SELECT role_id, role_name, price FROM shop")
    items = c.fetchall()
    conn.close()
    if not items:
        await ctx.send("Магазин пуст. Администратор может добавить товары через команду `add_shop_item`.")
        return
    embed = discord.Embed(title="🛒 Магазин ролей", color=discord.Color.green())
    for role_id, name, price in items:
        role = ctx.guild.get_role(role_id)
        display_name = role.mention if role else name
        embed.add_field(name=display_name, value=f"{price} {COIN_NAME}", inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def add_shop_item(ctx, role_id: int, price: int):
    """(Админ) Добавить роль в магазин"""
    role = ctx.guild.get_role(role_id)
    if not role:
        await ctx.send("Роль с таким ID не найдена на этом сервере.")
        return
    add_shop_item(role_id, role.name, price)
    await ctx.send(f"✅ Роль {role.mention} добавлена в магазин за {price} {COIN_NAME}.")

@bot.command()
async def buy(ctx, role_id: int):
    """Купить роль по ID"""
    conn = sqlite3.connect("economy.db")
    c = conn.cursor()
    c.execute("SELECT role_name, price FROM shop WHERE role_id = ?", (role_id,))
    item = c.fetchone()
    conn.close()
    if not item:
        await ctx.send("Товар не найден.")
        return
    role = ctx.guild.get_role(role_id)
    if not role:
        await ctx.send("Роль не существует на этом сервере.")
        return
    price = item[1]
    bal = get_balance(ctx.author.id)
    if bal < price:
        await ctx.send(f"Недостаточно монет! Нужно {price}, у вас {bal}.")
        return
    if role in ctx.author.roles:
        await ctx.send("У вас уже есть эта роль.")
        return
    update_balance(ctx.author.id, -price)
    await ctx.author.add_roles(role)
    await ctx.send(f"✅ Вы купили роль {role.mention} за {price} {COIN_NAME}!")

# --- Обработчик ошибок ---
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Не хватает аргумента. Используйте `{ctx.prefix}help {ctx.command.name}`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Неверный аргумент (например, пользователь не найден).")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("У вас недостаточно прав для выполнения этой команды.")
    else:
        await ctx.send(f"Произошла ошибка: {error}")

# --- Запуск ---
if __name__ == "__main__":
    bot.run(TOKEN)