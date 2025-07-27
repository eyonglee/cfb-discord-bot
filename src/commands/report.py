import discord
from discord import app_commands
from discord.ext import commands

class Report(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("Report cog loaded.")

    @app_commands.command(
        name="report",
        description="Report your result or issue."
    )
    @app_commands.describe(
        reason="The details of your report."
    )
    async def report(self, interaction: discord.Interaction, reason: str):
        """Record a report via slash command."""
        # Handle your report logic here
        await interaction.response.send_message(f"Report received: {reason}", ephemeral=True)