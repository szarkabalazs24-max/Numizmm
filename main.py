import discord
from discord.ext import commands
from discord import app_commands
import os, json, datetime, asyncio, re, random

# ================== ALAP ==================

TOKEN = os.getenv("DISCORD_TOKEN")

WARN_FILE = "warns.json"
LOG_FILE = "log.json"
WELCOME_FILE = "welcome.json"
LEAVE_FILE = "leave.json"
AUTO_ROLE_FILE = "autorole.json"

FORBIDDEN_WORDS = ["fasz","geci","buzi","bazdmeg","kurva"]
LINK_REGEX = r"http[s]?://"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================== SEGÉD ==================

def load_json(file, default):
    if not os.path.exists(file):
        return default
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def embed_base(title, desc, color):
    e = discord.Embed(
        title=title,
        description=desc,
        color=color,
        timestamp=datetime.datetime.utcnow()
    )
    e.set_footer(text="✨ Numiz’s MM Basement szervere ✨")
    return e

def mod_check(i: discord.Interaction):
    p = i.user.guild_permissions
    return p.manage_messages or p.administrator

# ================== READY ==================

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("✅ Bot online")

# ================== AUTOMOD ==================

spam_cache = {}

@bot.event
async def on_message(msg):
    if msg.author.bot:
        return

    now = datetime.datetime.utcnow()
    text = msg.content.lower()
    uid = str(msg.author.id)

    # LINK
    if re.search(LINK_REGEX, text):
        await msg.delete()
        await msg.author.timeout(datetime.timedelta(minutes=10))
        await msg.channel.send(embed=embed_base(
            "🔗 Tiltott link",
            f"{msg.author.mention}\n🔇 10 perc némítás",
            discord.Color.red()
        ))
        return

    # SPAM
    spam_cache.setdefault(uid, [])
    spam_cache[uid] = [t for t in spam_cache[uid] if (now - t).seconds < 5]
    spam_cache[uid].append(now)

    if len(spam_cache[uid]) >= 5:
        await msg.delete()
        await msg.author.timeout(datetime.timedelta(minutes=5))
        await msg.channel.send(embed=embed_base(
            "🔁 Spam",
            f"{msg.author.mention}\n🔇 5 perc némítás",
            discord.Color.orange()
        ))
        spam_cache[uid].clear()
        return

    # KÁROMKODÁS
    if any(w in text for w in FORBIDDEN_WORDS):
        await msg.delete()
        data = load_json(WARN_FILE, {})
        data.setdefault(uid, []).append("Káromkodás")
        save_json(WARN_FILE, data)

        mute = len(data[uid]) * 2
        await msg.author.timeout(datetime.timedelta(minutes=mute))

        await msg.channel.send(embed=embed_base(
            "🤬 Káromkodás",
            f"{msg.author.mention}\n⚠️ Figyelmeztetések: **{len(data[uid])}**\n🔇 {mute} perc",
            discord.Color.dark_red()
        ))
        return

    await bot.process_commands(msg)

# ================== BELÉPÉS / KILÉPÉS ==================

@bot.event
async def on_member_join(m):
    role_data = load_json(AUTO_ROLE_FILE, {})
    role = m.guild.get_role(role_data.get("role_id", 0))
    if role:
        await m.add_roles(role)

    ch = m.guild.get_channel(load_json(WELCOME_FILE, {}).get("channel_id", 0))
    if ch:
        await ch.send(f"👋 {m.mention} üdv! Te vagy a **{m.guild.member_count}. tag**")

@bot.event
async def on_member_remove(m):
    ch = m.guild.get_channel(load_json(LEAVE_FILE, {}).get("channel_id", 0))
    if ch:
        await ch.send(f"🚪 **{m.name}** kilépett a szerverről.")

# ================== FIGYELMEZTETÉS ==================

@bot.tree.command(name="figyelmeztetes")
@app_commands.check(mod_check)
async def figy(interaction, tag: discord.Member):
    data = load_json(WARN_FILE, {})
    uid = str(tag.id)
    data.setdefault(uid, []).append("Manuális figyelmeztetés")
    save_json(WARN_FILE, data)

    await interaction.response.send_message(embed=embed_base(
        "⚠️ Figyelmeztetés",
        f"{tag.mention}\nÖsszes: **{len(data[uid])}**",
        discord.Color.orange()
    ))

@bot.tree.command(name="figyelmeztetes_info")
async def figyinfo(interaction, tag: discord.Member):
    data = load_json(WARN_FILE, {})
    warns = data.get(str(tag.id), [])

    if not warns:
        return await interaction.response.send_message(
            embed=embed_base("📌 Figyelmeztetések", "Nincs figyelmeztetés.", discord.Color.green()),
            ephemeral=True
        )

    lista = "\n".join([f"{i+1}. {w}" for i, w in enumerate(warns)])

    await interaction.response.send_message(embed=embed_base(
        "ℹ️ Figyelmeztetések",
        f"👤 {tag.mention}\n⚠️ Összes: **{len(warns)}**\n\n{lista}",
        discord.Color.blurple()
    ))

@bot.tree.command(name="figyelmeztetes_torles")
@app_commands.check(mod_check)
async def figytorles(interaction, tag: discord.Member, db: int = 1):
    data = load_json(WARN_FILE, {})
    uid = str(tag.id)
    warns = data.get(uid, [])

    if not warns:
        return await interaction.response.send_message("❌ Nincs mit törölni", ephemeral=True)

    torolt = min(db, len(warns))
    for _ in range(torolt):
        warns.pop(0)

    if warns:
        data[uid] = warns
    else:
        data.pop(uid)

    save_json(WARN_FILE, data)

    await interaction.response.send_message(embed=embed_base(
        "🧹 Figyelmeztetés törölve",
        f"👤 {tag.mention}\n🗑️ Törölve: **{torolt}**\n📊 Maradt: **{len(warns)}**",
        discord.Color.green()
    ))

# ================== NÉMÍTÁS ==================

@bot.tree.command(name="nemitas")
@app_commands.check(mod_check)
async def nemitas(interaction, tag: discord.Member, perc: int):
    await tag.timeout(datetime.timedelta(minutes=perc))
    await interaction.response.send_message(embed=embed_base(
        "🔇 Némítás",
        f"{tag.mention}\n⏱ {perc} perc",
        discord.Color.red()
    ))

@bot.tree.command(name="nemitas_feloldas")
@app_commands.check(mod_check)
async def unmute(interaction, tag: discord.Member):
    await tag.timeout(None)
    await interaction.response.send_message(embed=embed_base(
        "🔊 Némítás feloldva",
        f"{tag.mention}",
        discord.Color.green()
    ))

# ================== KITILTÁS ==================

@bot.tree.command(name="kitiltas")
@app_commands.check(mod_check)
async def ban(interaction, tag: discord.Member):
    await tag.ban()
    await interaction.response.send_message(f"🚫 {tag} kitiltva")

@bot.tree.command(name="id_kitiltas")
@app_commands.check(mod_check)
async def idban(interaction, userid: str):
    user = await bot.fetch_user(int(userid))
    await interaction.guild.ban(user)
    await interaction.response.send_message("🚫 ID kitiltva")

# ================== INDÍTÁS ==================

bot.run(TOKEN)
