import discord
from discord import app_commands, ui
from discord.ext import commands

from src.db import get_teams, add_result, get_users, get_team


# Modal for collecting scores, notes, and remembering opponent name
class ReportModal(ui.Modal):
    def __init__(self, opponent_id: int, user_id: int):
        super().__init__(title="Game Report")
        self.opponent_id = opponent_id
        self.user_id = user_id

        # Inputs for the rest of the data
        self.user_score = ui.TextInput(
            label="Your Score",
            placeholder="e.g. 24",
            required=True,
            max_length=3
        )
        self.opp_score = ui.TextInput(
            label="Opponent Score",
            placeholder="e.g. 17",
            required=True,
            max_length=3
        )
        self.notes = ui.TextInput(
            label="Notes (optional)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=200
        )


        # Add the inputs to the modal
        self.add_item(self.user_score)
        self.add_item(self.opp_score)
        self.add_item(self.notes)

    async def on_submit(self, interaction: discord.Interaction):
        # Helper to parse optional ints
        def _to_int(val: str | None):
            if val is None:
                return None
            val = val.strip()
            if not val:
                return None
            if not val.isdigit():
                return None
            return int(val)

        us = _to_int(self.user_score.value)
        os = _to_int(self.opp_score.value)

        # Validate that both scores are provided together or both omitted
        if us is None or os is None:
            await interaction.response.send_message(
                "Please provide **both** scores or leave both blank.",
                ephemeral=True
            )
            return
        
        user_game = False
        users = await get_users()

        if any(self.opponent_id in d.values() for d in users):
            user_game = True

        user_win = None
        if us is not None and os is not None:
            if us > os:
                user_win = True
            elif us < os:
                user_win = False
            else:
                user_win = None

        result = {
            "discord_id": self.user_id,
            "opponent_id": self.opponent_id,
            "user_score": us,
            "opponent_score": os,
            "user_win": user_win,
            "notes": self.notes.value.strip() if self.notes.value else None,
            "user_game": user_game
        }

        await add_result(result)
        team = await get_team(self.opponent_id)

        summary = f"✅ Recorded report vs **{team['name']}**."
        if us is not None and os is not None:
            if us > os:
                outcome = "WIN"
            elif us < os:
                outcome = "LOSS"
            else:
                outcome = "TIE"
            summary += f"\nScore: **{us}–{os}**\nOutcome: **{outcome}**"

        if self.notes.value:
            summary += f"\nNotes: {self.notes.value.strip()}"

        # TODO: upsert into DB (games table) using the selected opponent and scores
        await interaction.response.send_message(summary, ephemeral=True)

    async def on_error(self, error: Exception, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.send_message(
                "Sorry, something went wrong saving your report.",
                ephemeral=True
            )
        except Exception:
            # If the initial response was already sent, fall back to followup
            await interaction.followup.send(
                "Sorry, something went wrong saving your report.",
                ephemeral=True
            )

class Report(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.teams = []
        bot.loop.create_task(self._load_teams())
        print("Report cog loaded.")
    
    async def _load_teams(self):
        self.teams = await get_teams()

    async def _validate_user(self, interaction: discord.Interaction) -> None:
        user = await get_users()
        if not any(interaction.user.id in d.values() for d in user):
            await interaction.response.send_message(
                "You are not a coach! Please contact an admin.",
                ephemeral=True
            )
            return False
        return True

    async def _validate_opponent(self, interaction: discord.Interaction, opponent: str) -> int | None:
        try:
            return int(opponent)
        except ValueError:
            await interaction.response.send_message("Invalid opponent selection.", ephemeral=True)
            return

    @app_commands.command(
        name="report",
        description="Report your result or issue."
    )
    @app_commands.describe(
        opponent="Search and select your opponent (type to autocomplete)"
    )
    async def report(self, interaction: discord.Interaction, opponent: str):
        """Record a report via slash command."""
        if not await self._validate_user(interaction):
            return

        opponent_id = await self._validate_opponent(interaction, opponent)

        await interaction.response.send_modal(ReportModal(opponent_id, interaction.user.id))

    @report.autocomplete('opponent')
    async def report_autocomplete(self, interaction: discord.Interaction, current: str):
        """Provide autocomplete suggestions for the opponent field."""
        matches = [t for t in self.teams if current.lower() in t['name'].lower()]
        matches = sorted(matches, key=lambda x: x['name'])[:25]
        return [app_commands.Choice(name=t['name'], value=str(t['team_id'])) for t in matches]