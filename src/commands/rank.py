import discord
from discord import app_commands
from discord.ext import commands

from src.db import get_users, get_user_team
from src.utils import validate_admin


class Rank(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("Rank cog loaded.")

    @app_commands.command(
        name="rank",
        description="View and manage a ranking of all users (admin only)."
    )
    async def rank(self, interaction: discord.Interaction):
        """
        Simple initial screen: show all users with an index so commissioners
        can decide on rankings. Later we can extend this to accept edits.
        """
        if not await validate_admin(interaction):
            return

        users = await get_users()
        
        if not users:
            await interaction.response.send_message(
                "No users found to rank.",
                ephemeral=True,
            )
            return

        # Sort users by coach_name if present, otherwise by discord_id
        users_sorted = sorted(
            users,
            key=lambda u: (u.get("username") or "", str(u["discord_id"]))
        )

        lines = []
        for idx, u in enumerate(users_sorted, start=1):
            name = u.get("username")
            team = await get_user_team(u["discord_id"])
            team_str = f" (Team {team})" if team is not None else ""
            lines.append(f"{idx}. {name}{team_str}")

        content = "🏅 **Current Coaches (for ranking):**\n" + "\n".join(lines)

        await interaction.response.send_message(content, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Rank(bot))

