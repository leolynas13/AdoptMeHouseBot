import discord
from discord.ext import commands

TOKEN = "MTUyNjI3NDE5MzM4NDI3NTk4OA.GBFMGD.z9A6R9xthjJoaR9nOHkX9ryy4FnQ-5ZWiTAIHU"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

houses = []


@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online!")


@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")


@bot.command()
async def house(ctx, *, description):
    house_offer = {
        "user": ctx.author.mention,
        "description": description
    }

    houses.append(house_offer)

    embed = discord.Embed(
        title="🏠 New House Trade Offer",
        color=0x00ff00
    )

    embed.add_field(
        name="👤 Owner",
        value=ctx.author.mention,
        inline=False
    )

    embed.add_field(
        name="📝 House Description",
        value=description,
        inline=False
    )

    await ctx.send(embed=embed)


@bot.command()
async def houses(ctx):
    if len(houses) == 0:
        await ctx.send("❌ No houses available right now.")
        return

    embed = discord.Embed(
        title="🏠 Available Houses",
        color=0x3498db
    )

    for i, house in enumerate(houses, start=1):
        embed.add_field(
            name=f"House #{i} - {house['user']}",
            value=house["description"],
            inline=False
        )

    await ctx.send(embed=embed)


bot.run(TOKEN)