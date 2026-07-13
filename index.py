import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import asyncio


# Token récupéré depuis Render / Secrets
TOKEN = os.getenv("TOKEN")


# -------- BOT --------

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# -------- DATABASE --------

FILE = "houses.json"


def load_houses():

    if not os.path.exists(FILE):
        with open(FILE, "w") as f:
            json.dump({}, f)

    with open(FILE, "r") as f:
        return json.load(f)



def save_houses():

    with open(FILE, "w") as f:
        json.dump(
            houses,
            f,
            indent=4
        )


houses = load_houses()



# -------- BUTTON --------

class ContactButton(discord.ui.View):

    def __init__(self, owner_id):

        super().__init__(
            timeout=None
        )

        self.owner_id = owner_id


    @discord.ui.button(
        label="📩 Contact Owner",
        style=discord.ButtonStyle.green
    )
    async def contact(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        owner = interaction.guild.get_member(
            int(self.owner_id)
        )


        if owner is None:

            await interaction.response.send_message(
                "❌ Owner not found",
                ephemeral=True
            )

            return


        try:

            await owner.send(
                "🏠 Someone is interested in your house!\n"
                f"Player: {interaction.user}"
            )


            await interaction.response.send_message(
                "✅ Message sent to owner!",
                ephemeral=True
            )


        except:

            await interaction.response.send_message(
                "❌ Owner DM disabled",
                ephemeral=True
            )



# -------- EVENTS --------


@bot.event
async def on_ready():

    try:

        synced = await bot.tree.sync()

        print(
            f"✅ Synced {len(synced)} commands"
        )

    except Exception as e:

        print(
            "Sync error:",
            e
        )


    print(
        f"🟢 {bot.user} is online"
    )



@bot.event
async def on_disconnect():

    print(
        "⚠️ Discord disconnected"
    )



# -------- COMMANDS --------


@bot.tree.command(
    name="addhouse",
    description="Add your Adopt Me house"
)
async def addhouse(
    interaction: discord.Interaction,
    price: int,
    category: str,
    description: str
):

    houses[str(interaction.user.id)] = {

        "owner": interaction.user.name,
        "owner_id": interaction.user.id,
        "price": price,
        "category": category,
        "description": description

    }


    save_houses()


    await interaction.response.send_message(
        "✅ House added!",
        ephemeral=True
    )# -------- HOUSES --------

@bot.tree.command(
    name="houses",
    description="Show all houses"
)
async def houses_command(
    interaction: discord.Interaction
):

    if not houses:

        await interaction.response.send_message(
            "❌ No houses available"
        )
        return


    await interaction.response.send_message(
        f"🏠 {len(houses)} house(s) found!"
    )


    for house in houses.values():

        embed = discord.Embed(
            title=f"🏠 {house['owner']}'s House",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="💰 Price",
            value=str(house["price"])
        )

        embed.add_field(
            name="🏷 Category",
            value=house["category"]
        )

        embed.add_field(
            name="📝 Description",
            value=house["description"],
            inline=False
        )


        await interaction.followup.send(
            embed=embed,
            view=ContactButton(
                house["owner_id"]
            )
        )



# -------- SEARCH --------

@bot.tree.command(
    name="search",
    description="Search a house"
)
async def search(
    interaction: discord.Interaction,
    keyword: str
):

    results = []


    for house in houses.values():

        text = (
            house["category"]
            + " "
            + house["description"]
        )


        if keyword.lower() in text.lower():

            results.append(house)



    if not results:

        await interaction.response.send_message(
            "❌ No house found"
        )
        return



    await interaction.response.send_message(
        f"🔎 {len(results)} result(s)"
    )


    for house in results:

        embed = discord.Embed(
            title=f"🏠 {house['owner']}'s House",
            color=discord.Color.orange()
        )


        embed.add_field(
            name="💰 Price",
            value=str(house["price"])
        )

        embed.add_field(
            name="📝 Description",
            value=house["description"]
        )


        await interaction.followup.send(
            embed=embed,
            view=ContactButton(
                house["owner_id"]
            )
        )



# -------- REMOVE --------

@bot.tree.command(
    name="removehouse",
    description="Remove your house"
)
async def removehouse(
    interaction: discord.Interaction
):

    user = str(interaction.user.id)


    if user not in houses:

        await interaction.response.send_message(
            "❌ You don't have a house",
            ephemeral=True
        )

        return


    del houses[user]

    save_houses()


    await interaction.response.send_message(
        "✅ House removed",
        ephemeral=True
    )



# -------- PING --------

@bot.tree.command(
    name="ping",
    description="Check bot latency"
)
async def ping(
    interaction: discord.Interaction
):

    await interaction.response.send_message(
        f"🏓 {round(bot.latency * 1000)}ms"
    )



# -------- START --------

async def main():

    while True:

        try:

            await bot.start(TOKEN)


        except Exception as e:

            print(
                "❌ Bot error:",
                e
            )

            print(
                "🔄 Restarting in 10 seconds..."
            )


            await asyncio.sleep(10)



asyncio.run(main())
