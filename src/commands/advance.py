import discord
from discord import app_commands
from discord.ext import commands

from src.db import advance_week, get_active_week_row
from src.utils import validate_admin


class Advance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("Advance cog loaded.")

    @app_commands.command(
        name="advance",
        description="Advance to the next week (admin only)."
    )
    async def advance(self, interaction: discord.Interaction):
        if not await validate_admin(interaction):
            return

        current = await get_active_week_row()
        if not current:
            await interaction.response.send_message(
                "No active week found to advance.",
                ephemeral=True,
            )
            return

        new_week = await advance_week()
        if not new_week:
            await interaction.response.send_message(
                "Failed to advance week.",
                ephemeral=True,
            )
            return

        msg = (
            f"Week advanced: {current['year']} Week {current['week_num']} ➜ "
            f"{new_week['year']} Week {new_week['week_num']}"
        )

        # Acknowledge to the admin ephemerally and announce to channel
        await interaction.response.send_message(msg, ephemeral=True)
        try:
            await interaction.channel.send(f"📅 {msg}")
        except Exception:
            # ignore if cannot send to channel
            pass


async def setup(bot):
    await bot.add_cog(Advance(bot))
