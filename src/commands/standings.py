import discord
from discord import app_commands
from discord.ext import commands

from src.db import get_standings, get_user_team
from src.utils import is_admin

class Standings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("Standings cog loaded.")

    @app_commands.command(
        name="standings",
        description="List the current standings of each coach."
    )
    async def standings(self, interaction: discord.Interaction):
        """A simple test command."""
        # Admins post publicly; non-admins get an ephemeral reply.
        admin = await is_admin(interaction)

        standings = await get_standings()

        try:
            embed = discord.Embed(
                title="Current Standings",
                description="Here are the current standings of all coaches:",
                color=discord.Color.blue()
            )

            for idx, record in enumerate(standings, start=1):
                team = await get_user_team(record['discord_id'])
                username = team['username'] if team else "Unknown Coach"
                name = team['name'] if team else "Unknown Team"
                wins = record['wins']
                losses = record['losses']
                ties = record['ties']
                embed.add_field(
                    name=f"{idx}. {username} {name}",
                    value=f"Wins: {wins}, Losses: {losses}, Ties: {ties}",
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=not admin)
        except Exception as e:
            print(f"Error generating standings embed: {e}")
            # If we've already responded, use followup to avoid InteractionResponded
            if interaction.response.is_done():
                await interaction.followup.send(
                    "Sorry, something went wrong fetching the standings.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Sorry, something went wrong fetching the standings.",
                    ephemeral=True
                )
    
