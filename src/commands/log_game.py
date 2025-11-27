import discord
from discord import app_commands, ui
from discord.ext import commands

from src.db import (
    get_teams,
    add_result,
    get_users,
    get_team,
    maybe_auto_advance_week,
    get_active_week,
    get_game,
    has_played_team_this_year,
)
from src.utils import validate_user, validate_opponent


class ReportModal(ui.Modal):
    def __init__(self, opponent_id: int, user_id: int, existing: dict | None = None):
        super().__init__(title="Game Report")
        self.opponent_id = opponent_id
        self.user_id = user_id

        default_user_score = ""
        default_opp_score = ""
        default_notes = ""
        if existing is not None:
            if existing.get("user_score") is not None:
                default_user_score = str(existing["user_score"])
            if existing.get("opp_score") is not None:
                default_opp_score = str(existing["opp_score"])
            if existing.get("notes"):
                default_notes = existing["notes"]

        # Inputs for the rest of the data
        self.user_score = ui.TextInput(
            label="Your Score",
            placeholder="e.g. 24",
            required=True,
            max_length=3,
            default=default_user_score,
        )
        self.opp_score = ui.TextInput(
            label="Opponent Score",
            placeholder="e.g. 17",
            required=True,
            max_length=3,
            default=default_opp_score,
        )
        self.notes = ui.TextInput(
            label="Notes (optional)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=200,
            default=default_notes,
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

        summary = f"✅ Recorded game vs **{team['name']}**."
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

        # Send the confirmation message to the channel so everyone can see it
        await interaction.response.send_message(summary, ephemeral=False)

        # After recording, check if all users have reported and advance automatically
        try:
            advanced = await maybe_auto_advance_week()
            if advanced:
                channel = interaction.channel
                await channel.send(
                    f"📅 All reports received. Advancing to Week {advanced['week_num']} ({advanced['year']})."
                )
        except Exception:
            # Do not fail the user flow if auto-advance check errors
            pass

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

class ConfirmEditView(ui.View):
    def __init__(self, user_id: int, opponent_id: int, existing: dict):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.opponent_id = opponent_id
        self.existing = existing

    @ui.button(label="Yes", style=discord.ButtonStyle.primary)
    async def yes(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This button isn't for you.", ephemeral=True
            )
            return

        await interaction.response.send_modal(
            ReportModal(self.opponent_id, self.user_id, existing=self.existing)
        )
        self.stop()

    @ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This button isn't for you.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Okay, keeping the existing game for this week.",
            ephemeral=True,
        )
        self.stop()

    @ui.button(label="Bye", style=discord.ButtonStyle.secondary)
    async def bye_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This button isn't for you.", ephemeral=True
            )
            return

        result = {
            "discord_id": self.user_id,
            "opponent_id": None,
            "user_score": None,
            "opponent_score": None,
            "user_win": None,
            "notes": "Bye week",
            "user_game": False,
            "bye": True,
        }

        await add_result(result)
        await interaction.response.send_message(
            "✅ Logged a bye week with no opponent or score.",
            ephemeral=False,
        )
        self.stop()


class Report(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.teams = []
        bot.loop.create_task(self._load_teams())
        print("LogGame cog loaded.")
    
    async def _load_teams(self):
        self.teams = await get_teams()

    @app_commands.command(
        name="loggame",
        description="Log your game or a bye week."
    )
    @app_commands.describe(
        opponent="Search and select your opponent (type to autocomplete)"
    )
    async def loggame(self, interaction: discord.Interaction, opponent: str):
        """Entry point for logging a game or bye week."""
        if not await validate_user(interaction):
            return

        # Handle BYE directly from the opponent option
        if opponent == "BYE":
            result = {
                "discord_id": interaction.user.id,
                "opponent_id": None,
                "user_score": None,
                "opponent_score": None,
                "user_win": None,
                "notes": "Bye week",
                "user_game": False,
                "bye": True,
            }
            await add_result(result)
            await interaction.response.send_message(
                "✅ Logged a bye week with no opponent or score.",
                ephemeral=False,
            )
            return

        opponent_id = await validate_opponent(interaction, opponent)

        # Prevent playing the same team twice in the same season.
        if await has_played_team_this_year(interaction.user.id, int(opponent_id)):
            await interaction.response.send_message(
                "Oops! You have already played that team this season! "
                "If you believe this is a mistake, contact a commissioner.",
                ephemeral=True,
            )
            return

        # For non-bye games, immediately go into the existing/edit flow.
        week_num = await get_active_week()
        if week_num is None:
            await interaction.response.send_message(
                "No active week is set. Please contact an admin.",
                ephemeral=True,
            )
            return

        existing = await get_game(week_num, interaction.user.id)
        if not existing:
            await interaction.response.send_modal(
                ReportModal(opponent_id, interaction.user.id)
            )
            return

        # If this is already a user-vs-user game, block changes and send guidance.
        if existing.get("user_game"):
            await interaction.response.send_message(
                "Oops! A user game has already been logged for this week! "
                "Please contact a commissioner to make a fix!",
                ephemeral=True,
            )
            return

        view = ConfirmEditView(interaction.user.id, opponent_id, existing)
        await interaction.response.send_message(
            "Game already logged for this week! Would you like to edit?",
            view=view,
            ephemeral=True,
        )

    @loggame.autocomplete('opponent')
    async def loggame_autocomplete(self, interaction: discord.Interaction, current: str):
        """Provide autocomplete suggestions for the opponent field, optionally including BYE."""
        matches = [t for t in self.teams if current.lower() in t['name'].lower()]
        matches = sorted(matches, key=lambda x: x['name'])[:25]

        team_choices = [
            app_commands.Choice(name=t["name"], value=str(t["team_id"])) for t in matches
        ]

        # When the user hasn't started typing, show BYE at the top once.
        if not current.strip():
            bye_choice = app_commands.Choice(name="BYE", value="BYE")
            # Prepend BYE; Discord handles ordering after that.
            return [bye_choice] + team_choices[:24]

        return team_choices
