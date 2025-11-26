import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

from src.db import init_db_pool

from src.commands.report import Report
from src.commands.standings import Standings
from src.commands.test import Test
from src.commands.advance import Advance

load_dotenv()
BOT_TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))  

intents = discord.Intents.default()
intents.message_content = True 

class CFBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        await init_db_pool()

        await self.add_cog(Report(self))
        await self.add_cog(Standings(self))
        await self.add_cog(Test(self))
        await self.add_cog(Advance(self))

        self.tree.copy_global_to(guild=discord.Object(id=GUILD_ID))

        print("Syncing commands to the guild...")
        await self.tree.sync(guild=discord.Object(id=GUILD_ID))
        print("Commands synced successfully.")



bot = CFBot()

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("🏓 Pong! you should see a special message here")

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
