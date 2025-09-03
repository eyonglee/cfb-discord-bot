import discord

from src.db import get_users

async def validate_admin(interaction: discord.Interaction) -> bool:
    user = await get_users()
    if not any(interaction.user.id in d.values() and d.get("admin") for d in user):
        await interaction.response.send_message(
            "You are not an admin! Please contact an admin.",
            ephemeral=True
        )
        return False
    return True

async def validate_user(interaction: discord.Interaction) -> bool:
    user = await get_users()
    if not any(interaction.user.id in d.values() for d in user):
        await interaction.response.send_message(
            "You are not a coach! Please contact an admin.",
            ephemeral=True
        )
        return False
    return True

async def validate_opponent(interaction: discord.Interaction, opponent: str) -> int | None:
    try:
        return int(opponent)
    except ValueError:
        await interaction.response.send_message("Invalid opponent selection.", ephemeral=True)
        return