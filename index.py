import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import sqlite3
from dotenv import load_dotenv

# --- PATH CONFIGURATION ---
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, 'token.env')
db_path = os.path.join(script_dir, 'database.db')

if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)

TOKEN = os.getenv("DISCORD_TOKEN")

print(f"👉 Token successfully detected? {TOKEN is not None}")

# --- DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Houses for sale table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS houses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER,
            owner_name TEXT,
            price INTEGER,
            type TEXT,
            images TEXT,
            favorites TEXT,
            status TEXT
        )
    ''')
    # Commissions / Demands table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS demands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            title TEXT,
            description TEXT,
            reward TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()


# --- BOT CONFIGURATION ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        print("Local initialization complete. Connecting...")
        try:
            synced = await self.tree.sync()
            print(f"✅ {len(synced)} slash commands successfully synced!")
        except Exception as e:
            print(f"❌ Error syncing commands: {e}")

    async def on_ready(self):
        print(f"✅ Successfully connected as: {self.user} (ID: {self.user.id})")

bot = MyBot()


# --- DATABASE QUERIES ---
def db_add_house(owner_id, owner_name, price, house_type, images):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    images_str = ",".join(images)
    cursor.execute("INSERT INTO houses (owner_id, owner_name, price, type, images, favorites, status) VALUES (?, ?, ?, ?, ?, '', 'Available')", (owner_id, owner_name, price, house_type, images_str))
    conn.commit()
    conn.close()

def db_get_available_houses():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, owner_id, owner_name, price, type, images, favorites, status FROM houses WHERE status = 'Available'")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "owner_id": r[1], "owner_name": r[2], "price": r[3], "type": r[4], "images": r[5].split(",") if r[5] else [], "favorites": [int(x) for x in r[6].split(",")] if r[6] else [], "status": r[7]} for r in rows]

def db_update_favorites(house_id, favorites_list):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE houses SET favorites = ? WHERE id = ?", (",".join([str(x) for x in favorites_list]), house_id))
    conn.commit()
    conn.close()

def db_remove_house(house_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM houses WHERE id = ?", (house_id,))
    changes = cursor.rowcount
    conn.commit()
    conn.close()
    return changes > 0

def db_add_demand(user_id, user_name, title, description, reward):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO demands (user_id, user_name, title, description, reward, status) VALUES (?, ?, ?, ?, ?, 'Open')", (user_id, user_name, title, description, reward))
    conn.commit()
    conn.close()

def db_get_open_demands():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, user_name, title, description, reward, status FROM demands WHERE status = 'Open'")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "user_id": r[1], "user_name": r[2], "title": r[3], "description": r[4], "reward": r[5], "status": r[6]} for r in rows]

def db_remove_demand(demand_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM demands WHERE id = ?", (demand_id,))
    changes = cursor.rowcount
    conn.commit()
    conn.close()
    return changes > 0


# ==========================================
# PART A: COMMISSIONS INTERFACES
# ==========================================

class CommissionModal(discord.ui.Modal, title="💬 Create a Commission"):
    demand_title = discord.ui.TextInput(label="Demand Title", placeholder="E.g., Looking for a builder for a Unicorn house", min_length=5, max_length=100)
    description = discord.ui.TextInput(label="Build Details / Style requested", style=discord.TextStyle.paragraph, placeholder="E.g., Modern style, 3 bedrooms, fully furnished...", max_length=500)
    reward = discord.ui.TextInput(label="Reward / Offer", placeholder="E.g., 8,000 Bucks / Neon Dragon", max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        db_add_demand(interaction.user.id, interaction.user.name, self.demand_title.value, self.description.value, self.reward.value)
        await interaction.response.send_message("✅ Your commission request has been successfully published!", ephemeral=True)


class CommissionMenuView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=180)
        self.user_id = user_id

    @discord.ui.button(label="💬 Commissions", style=discord.ButtonStyle.success, row=0)
    async def create_commission(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CommissionModal())

    @discord.ui.button(label="📜 List of Commissions", style=discord.ButtonStyle.primary, row=0)
    async def list_commissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DemandBookView(interaction.user.id)
        embed = view.generate_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="⬅️ Back to Main Menu", style=discord.ButtonStyle.secondary, row=1)
    async def back_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MainMenuView(interaction.user.id)
        await interaction.response.edit_message(embed=view.generate_embed(), view=view)


class DemandBookView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.demands_list = db_get_open_demands()
        self.index = 0

    def generate_embed(self):
        if not self.demands_list:
            return discord.Embed(title="📜 Commissions List", description="No commission requests are currently available.", color=discord.Color.orange())
        
        demand = self.demands_list[self.index]
        user = bot.get_user(demand["user_id"])
        user_mention = user.mention if user else demand["user_name"]

        embed = discord.Embed(title=f"📜 Commissions List — {self.index + 1}/{len(self.demands_list)}", color=discord.Color.gold())
        embed.add_field(name="Client", value=user_mention, inline=False)
        embed.add_field(name="Request", value=demand["title"], inline=False)
        embed.add_field(name="Description / Requirements", value=demand["description"], inline=False)
        embed.add_field(name="💰 Reward / Payment", value=demand["reward"], inline=False)
        embed.set_footer(text=f"ID: #{demand['id']}")
        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.primary)
    async def prev_demand(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1) % len(self.demands_list) if self.demands_list else 0
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary)
    async def next_demand(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % len(self.demands_list) if self.demands_list else 0
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)

    @discord.ui.button(label="✉️ Speak about Commission", style=discord.ButtonStyle.danger)
    async def speak_commission(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.demands_list: return
        demand = self.demands_list[self.index]
        builder, guild = interaction.user, interaction.guild
        
        if builder.id == demand["user_id"]:
            await interaction.response.send_message("❌ You cannot apply for your own commission!", ephemeral=True)
            return

        poster = guild.get_member(demand["user_id"])
        if not poster:
            await interaction.response.send_message("❌ The author of this request is no longer in the server.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            builder: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        if poster:
            overwrites[poster] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel = await guild.create_text_channel(name=f"commission-{builder.name}-and-{demand['user_name']}", overwrites=overwrites)
        await interaction.response.send_message(f"✅ Private room opened to negotiate: {channel.mention}!", ephemeral=True)

        welcome = discord.Embed(title="🛠️ New Commission Discussion", description=f"Private discussion regarding: **{demand['title']}**.", color=discord.Color.green())
        welcome.add_field(name="Client", value=poster.mention, inline=True)
        welcome.add_field(name="Builder", value=builder.mention, inline=True)
        welcome.add_field(name="Description Reminder", value=demand["description"], inline=False)
        welcome.add_field(name="Promised Reward", value=demand["reward"], inline=False)
        await channel.send(content=f"{builder.mention} & {poster.mention}", embed=welcome)

    @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.secondary, row=1)
    async def back_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CommissionMenuView(self.user_id)
        await interaction.response.edit_message(embed=discord.Embed(title="🛠️ Commissions Hub", description="Select an option below:", color=discord.Color.teal()), view=view)


# ==========================================
# PART B: HOUSE CATALOGUE
# ==========================================

class HouseBookView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.houses_list = db_get_available_houses()
        self.house_index, self.photo_index = 0, 0

    def generate_embed(self):
        if not self.houses_list:
            return discord.Embed(title="🏠 House Catalog", description="No houses are currently listed for sale.", color=discord.Color.red())
        house = self.houses_list[self.house_index]
        owner = bot.get_user(house["owner_id"])
        embed = discord.Embed(title=f"📖 House Catalog — {self.house_index + 1}/{len(self.houses_list)}", color=discord.Color.blurple())
        embed.add_field(name="Seller", value=owner.mention if owner else house["owner_name"], inline=True)
        embed.add_field(name="House Type", value=house["type"], inline=True)
        embed.add_field(name="Price Tag", value=f"{house['price']} 💵 Bucks", inline=True)
        embed.add_field(name="⭐ Favorites", value=f"{len(house['favorites'])} user(s)", inline=True)
        embed.set_footer(text=f"ID: #{house['id']}")
        if house["images"]: embed.set_image(url=house["images"][self.photo_index])
        return embed

    @discord.ui.button(label="🏠 ◀", style=discord.ButtonStyle.primary)
    async def prev_h(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.house_index = (self.house_index - 1) % len(self.houses_list) if self.houses_list else 0
        self.photo_index = 0
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)

    @discord.ui.button(label="📸 ◀", style=discord.ButtonStyle.secondary)
    async def prev_p(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.houses_list and self.houses_list[self.house_index]["images"]:
            self.photo_index = (self.photo_index - 1) % len(self.houses_list[self.house_index]["images"])
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)

    @discord.ui.button(label="▶ 📸", style=discord.ButtonStyle.secondary)
    async def next_p(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.houses_list and self.houses_list[self.house_index]["images"]:
            self.photo_index = (self.photo_index + 1) % len(self.houses_list[self.house_index]["images"])
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)

    @discord.ui.button(label="▶ 🏠", style=discord.ButtonStyle.primary)
    async def next_h(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.house_index = (self.house_index + 1) % len(self.houses_list) if self.houses_list else 0
        self.photo_index = 0
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)

    @discord.ui.button(label="❤️ Favorite", style=discord.ButtonStyle.success)
    async def favorite(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.houses_list: return
        house = self.houses_list[self.house_index]
        if interaction.user.id in house["favorites"]: house["favorites"].remove(interaction.user.id)
        else: house["favorites"].append(interaction.user.id)
        db_update_favorites(house["id"], house["favorites"])
        await interaction.response.send_message("Favorites updated!", ephemeral=True)
        await interaction.message.edit(embed=self.generate_embed(), view=self)

    @discord.ui.button(label="🤝 Propose a Trade", style=discord.ButtonStyle.danger, row=1)
    async def buy_house(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.houses_list: return
        house = self.houses_list[self.house_index]
        buyer, guild = interaction.user, interaction.guild
        seller = guild.get_member(house["owner_id"])
        if buyer.id == house["owner_id"]: 
            await interaction.response.send_message("You cannot buy your own house!", ephemeral=True)
            return
            
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            buyer: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        if seller:
            overwrites[seller] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel = await guild.create_text_channel(name=f"buy-{buyer.name}-from-{house['owner_name']}", overwrites=overwrites)
        await interaction.response.send_message(f"✅ Purchase channel created: {channel.mention}", ephemeral=True)
        await channel.send(f"{buyer.mention} & {seller.mention if seller else house['owner_name']}, welcome! Negotiation room for **{house['type']}**.")

    @discord.ui.button(label="⬅️ Back to Main Menu", style=discord.ButtonStyle.secondary, row=1)
    async def back_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MainMenuView(self.user_id)
        await interaction.response.edit_message(embed=view.generate_embed(), view=view)


# ==========================================
# PART C: GLOBAL HUB MENU
# ==========================================

class MainMenuView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=180)
        self.user_id = user_id

    def generate_embed(self):
        embed = discord.Embed(title="🏡 Crystal House Trade — Main Menu", description="Welcome to the ultimate house trading and building platform! Select the section you would like to explore today:", color=discord.Color.purple())
        embed.add_field(name="🛒 House Catalog", value="Discover amazing houses built by our community. Find your dream home and open a trade request instantly to pay in Bucks or Pets!", inline=False)
        embed.add_field(name="🛠️ Commissions Hub", value="Looking for a talented builder to create a custom house for you? Or are you a builder looking for paid jobs? This is your place!", inline=False)
        embed.set_footer(text="⚠️ For safety reasons, always complete transactions inside the official game.")
        return embed

    @discord.ui.button(label="🛒 House Catalog", style=discord.ButtonStyle.primary, emoji="🛒")
    async def open_catalog(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = HouseBookView(interaction.user.id)
        await interaction.response.edit_message(embed=view.generate_embed(), view=view)

    @discord.ui.button(label="🛠️ Commissions Hub", style=discord.ButtonStyle.success, emoji="🛠️")
    async def open_commissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CommissionMenuView(interaction.user.id)
        embed = discord.Embed(title="🛠️ Commissions Hub", description="Select an option below:", color=discord.Color.teal())
        await interaction.response.edit_message(embed=embed, view=view)


# --- SLASH COMMANDS ---
@bot.tree.command(name="menu", description="Open the central configuration and announcements panel")
async def menu(interaction: discord.Interaction):
    view = MainMenuView(interaction.user.id)
    await interaction.response.send_message(embed=view.generate_embed(), view=view)


@bot.tree.command(name="addhouse", description="Add a house for sale to the catalog")
async def addhouse_cmd(interaction: discord.Interaction, price: int, house_type: str):
    await interaction.response.send_message(f"🏠 **{interaction.user.display_name}**, upload up to **5 photos** of your house now!\n⚠️ You have **15 seconds** to upload.", ephemeral=True)
    images = []
    def check(m): return m.author.id == interaction.user.id and len(m.attachments) > 0
    try:
        while len(images) < 5:
            msg = await bot.wait_for('message', check=check, timeout=15.0)
            for attachment in msg.attachments:
                if len(images) < 5: images.append(attachment.url)
            await interaction.followup.send(f"📸 Image(s) received ({len(images)}/5)", ephemeral=True)
            if len(images) >= 5: break
    except asyncio.TimeoutError:
        if len(images) == 0:
            await interaction.followup.send("⏱️ Time's up! No photos received.", ephemeral=True)
            return
    db_add_house(interaction.user.id, interaction.user.name, price, house_type, images)
    await interaction.followup.send("✅ Successfully added to the catalog!", ephemeral=True)


@bot.tree.command(name="removehouse", description="Remove one of your listed houses from sale using its ID")
async def removehouse(interaction: discord.Interaction, house_id: int):
    all_houses = db_get_available_houses()
    target = next((h for h in all_houses if h["id"] == house_id), None)
    if not target or target["owner_id"] != interaction.user.id:
        await interaction.response.send_message("❌ House not found or you do not own it.", ephemeral=True)
        return
    db_remove_house(house_id)
    await interaction.response.send_message(f"🗑️ Successfully removed house `#{house_id}` from the catalog!", ephemeral=True)


@bot.tree.command(name="removedemand", description="Remove one of your commissions requests using its ID")
async def removedemand(interaction: discord.Interaction, demand_id: int):
    all_demands = db_get_open_demands()
    target = next((d for d in all_demands if d["id"] == demand_id), None)
    if target is None or target["user_id"] != interaction.user.id:
        await interaction.response.send_message("❌ Commission request not found or you are not the author.", ephemeral=True)
        return
    if db_remove_demand(demand_id):
        await interaction.response.send_message(f"🗑️ Your commission request `#{demand_id}` has been successfully removed!", ephemeral=True)


# --- BOT RUN ---
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Unable to launch bot: Token not found.")