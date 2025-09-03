import discord
from discord import app_commands
from discord.ext import commands

from src.db import get_users
from src.utils import validate_admin

class Test(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("Test cog loaded.")

    @app_commands.command(
        name="test",
        description="A test command to check if the / commands are working."
    )
    async def test(self, interaction: discord.Interaction):
        """A simple test command."""
        if not await validate_admin(interaction):
            return
        
        channel = interaction.channel
        await interaction.response.send_message("Test command executed successfully!", ephemeral=True)

        await channel.send("This message is sent to the channel as a test.")

    @app_commands.command(
        name="list_users",
        description="List all users in the database."
    )
    async def list_users(self, interaction: discord.Interaction):
        """Fetch and display all users from the database."""
        users = await get_users()
        if not users:
            await interaction.response.send_message("No users found in the database.", ephemeral=True)
            return
        
        user_list = "\n".join([f"{user['discord_id']}: {user['username']}" for user in users])
        await interaction.response.send_message(f"Users:\n{user_list}", ephemeral=True)