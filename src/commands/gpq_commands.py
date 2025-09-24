"""GPQ (Guild Party Quest) commands module for the MapleStory Discord Bot."""

import asyncio
import os
import re
import shutil
import statistics
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Union

import discord
import requests
from discord import app_commands
from matplotlib import pyplot as plt

from core.constants import GUILD_ID, REMINDER_CHANNEL_ID
from core.config import DEFAULT_SYSTEM_PROMPT
from integrations.culvert_reader import parse_results, send_request
from services.data_service import DataService
from integrations.db import get_database
from commands.setup_commands import check_server_setup, send_setup_required_message
from utils.time_utils import (
    get_current_datetime,
    get_current_week,
    get_last_week,
    get_string_for_week,
    get_week_ago,
)
from utils.legacy_utils import (
    batch_list,
    clean_sheet_value,
    convert_none_in_list,
    pad_list,
    remove_leading_nones,
    sum_cell_scores,
)

import logging

logger = logging.getLogger(__name__)

# Constants for GPQ functionality
EMOJI_ONE_TO_NINE = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
EMOJI_TO_INDEX_MAP = {emoji: i for i, emoji in enumerate(EMOJI_ONE_TO_NINE)}

DEFAULT_EDGE_COLOR = "A4BFEB"
DEFAULT_BAR_COLOR = "A4BFEB"


GUILD_CHAT_CHANNEL = 1228482038437515366
MEMBER_ROLE_ID = 1228053292886528106


class GPQCommands:
    """Container class for all GPQ-related slash commands and helper functions."""

    def __init__(self, client: discord.Client, tree: app_commands.CommandTree):
        """Initialize GPQ commands with Discord client and command tree."""
        self.client = client
        self.tree = tree
        self._register_commands()

    def _register_commands(self) -> None:
        """Register all GPQ slash commands with the command tree."""

        @self.tree.command(name="gpq", description="Add this week's GPQ score")
        @app_commands.describe(
            score="Your GPQ score.",
            character="The Maplestory character name.",
            prev_week="Whether to record score for previous week",
        )
        async def gpq_score(
            interaction: discord.Interaction,
            score: int,
            character: Optional[str] = None,
            prev_week: Optional[bool] = False,
        ):
            """Add a GPQ score for the current or previous week."""
            await self.handle_gpq_score(interaction, score, character, prev_week)

        @self.tree.command(name="profile", description="Check GPQ profile")
        @app_commands.describe(character="The Maplestory character name.")
        async def gpq_profile(
            interaction: discord.Interaction, character: Optional[str]
        ):
            """Display GPQ profile for a character."""
            await self.handle_gpq_profile(interaction, character)

        @self.tree.command(name="graph", description="Graph last GPQ scores")
        @app_commands.describe(
            character="The Maplestory character name.",
            num_weeks="Number of weeks to graph.",
            bar_color='Hex color of bar. Enter "0" to reset to default',
            edge_color='Hex color of edge. Enter "0" to reset to default',
        )
        async def gpq_graph(
            interaction: discord.Interaction,
            character: Optional[str],
            num_weeks: int = 7,
            bar_color: str = DEFAULT_BAR_COLOR,
            edge_color: str = DEFAULT_EDGE_COLOR,
        ):
            """Generate a graph of GPQ scores over time."""
            await self.handle_gpq_graph(
                interaction, character, num_weeks, bar_color, edge_color
            )

        @self.tree.command(
            name="manual-reminder",
            description="Manually send the reminder message in this channel",
        )
        @app_commands.describe(mention="Actually mention the users.")
        async def gpq_reminder(interaction: discord.Interaction, mention: bool = False):
            """Manually trigger GPQ reminder."""
            await self.handle_manual_reminder(interaction, mention)

        @self.tree.command(
            name="list",
            description="List the linked Maplestory characters associated with your account",
        )
        async def list_chars(interaction: discord.Interaction):
            """List all characters linked to the user."""
            await self.handle_list_characters(interaction)

        @self.tree.command(
            name="rename",
            description="Rename an existing member for ign changes",
        )
        @app_commands.describe(previous_ign="Their previous IGN", new_ign="The new IGN")
        async def rename_user(
            interaction: discord.Interaction, previous_ign: str, new_ign: str
        ):
            """Rename a character in the system."""
            await self.handle_rename_user(interaction, previous_ign, new_ign)

        @self.tree.command(
            name="link",
            description="Link Discord user with Maplestory name",
        )
        @app_commands.describe(
            maple_name="The Maplestory character name.",
            discord_user="The associated Discord user.",
        )
        async def link_user(
            interaction: discord.Interaction,
            maple_name: str,
            discord_user: discord.User,
        ):
            """Link a Discord user to a MapleStory character."""
            await self.handle_link_user(interaction, maple_name, discord_user)

        @self.tree.command(
            name="unlink",
            description="Unlinks all igns for the discord user.",
        )
        @app_commands.describe(discord_user="The Discord user.")
        async def unlink_user(
            interaction: discord.Interaction, discord_user: discord.User
        ):
            """Unlink all characters from a Discord user."""
            await self.handle_unlink_user(interaction, discord_user)

        @self.tree.command(
            name="guild_graph",
            description="Display cumulative GPQ scores for the entire guild (Admin only)",
        )
        @app_commands.describe(
            num_weeks="Number of weeks to graph.",
            bar_color='Hex color of bar. Enter "0" to reset to default',
            edge_color='Hex color of edge. Enter "0" to reset to default',
        )
        async def guild_graph(
            interaction: discord.Interaction,
            num_weeks: int = 12,
            bar_color: str = DEFAULT_BAR_COLOR,
            edge_color: str = DEFAULT_EDGE_COLOR,
        ):
            """Generate a graph of guild cumulative GPQ scores over time."""
            await self.handle_guild_graph(interaction, num_weeks, bar_color, edge_color)

    async def handle_gpq_score(
        self,
        interaction: discord.Interaction,
        score: int,
        character: Optional[str] = None,
        prev_week: Optional[bool] = False,
    ) -> None:
        """Handle adding a GPQ score."""
        await interaction.response.defer()

        # Check if server is set up
        if not check_server_setup(interaction):
            await send_setup_required_message(interaction)
            return

        db = get_database()

        is_admin = interaction.permissions.manage_roles

        # TODO: Refactor to use new database methods instead of legacy sheet methods
        server_id = str(interaction.guild.id)
        player_ids = await self.get_validated_player_ids_for_user_or_character(
            interaction, db, server_id, character, check_owned=not is_admin
        )
        if not player_ids:
            try:
                await interaction.followup.send(f"Error: No maplestory user associated")
            except Exception as e:
                logger.info(f"Error while sending response: {e}")
            return

        num_characters = len(player_ids)

        if num_characters > 1 and character is None:
            await interaction.followup.send(
                f"Error: More than 1 character is linked to this account - please specify character."
            )
            return

        player_id = player_ids[0]
        current_week = get_current_week()
        target_week = get_last_week() if prev_week else current_week

        # Get player's existing scores to find highest score
        player_scores = db.get_player_scores(player_id)
        existing_scores = [score.score for score in player_scores]
        highest_score = max(existing_scores) if existing_scores else 0

        # Record the new score
        db.record_score_for_week(player_id, target_week, score)

        maple_user = db.get_maplestory_username(player_id)

        if score > highest_score:
            await interaction.followup.send(
                f"{maple_user.upper()} SCORED A NEW HIGH SCORE OF {score} FOR THE WEEK OF {current_week} <a:poggSpin:1374647425792479262> <a:poggSpin:1374647425792479262> <a:poggSpin:1374647425792479262>"
            )
        else:
            await interaction.followup.send(
                f"{maple_user} scored {score} for the week of {current_week}"
            )

    async def handle_gpq_profile(
        self, interaction: discord.Interaction, character: Optional[str]
    ) -> None:
        """Handle GPQ profile display."""
        # Check if server is set up
        if not check_server_setup(interaction):
            await interaction.response.defer()
            await send_setup_required_message(interaction)
            return

        await self.async_update_guild_profile(interaction, character, None, None)

    async def handle_gpq_graph(
        self,
        interaction: discord.Interaction,
        character: Optional[str],
        num_weeks: int = 7,
        bar_color: str = DEFAULT_BAR_COLOR,
        edge_color: str = DEFAULT_EDGE_COLOR,
    ) -> None:
        """Handle GPQ graph generation."""
        # Check if server is set up
        if not check_server_setup(interaction):
            await interaction.response.defer()
            await send_setup_required_message(interaction)
            return

        if num_weeks <= 0:
            await interaction.response.send_message(
                "Error: num_weeks cannot be 0 or less."
            )
            return

        valid_bar_color = (
            re.search(r"^(?:[0-9a-fA-F]{3}){1,2}$", bar_color) or bar_color == "0"
        )
        valid_edge_color = (
            re.search(r"^(?:[0-9a-fA-F]{3}){1,2}$", edge_color) or edge_color == "0"
        )

        if not valid_bar_color or not valid_edge_color:
            await interaction.response.send_message(
                "Invalid color code. Please enter a valid hex color (e.g. ffffff)"
            )
            return

        if bar_color == "0":
            # Reset bar color
            self.update_colors(
                str(interaction.user.id), bar_color=DEFAULT_BAR_COLOR, edge_color=None
            )
        elif bar_color != DEFAULT_BAR_COLOR:
            # Update bar color
            self.update_colors(
                str(interaction.user.id), bar_color=bar_color, edge_color=None
            )

        if edge_color == "0":
            # Reset edge color
            self.update_colors(
                str(interaction.user.id), bar_color=None, edge_color=DEFAULT_EDGE_COLOR
            )
        elif edge_color != DEFAULT_BAR_COLOR:
            # Update edge color
            self.update_colors(
                str(interaction.user.id), bar_color=None, edge_color=edge_color
            )

        colors = self.get_colors_for_user(str(interaction.user.id))
        if colors:
            bar_color = colors[0]
            edge_color = colors[1]
        else:
            self.update_colors(
                str(interaction.user.id),
                bar_color=DEFAULT_BAR_COLOR,
                edge_color=DEFAULT_EDGE_COLOR,
            )
            bar_color = DEFAULT_BAR_COLOR
            edge_color = DEFAULT_EDGE_COLOR

        await self.async_update_gpq_graph(
            interaction=interaction,
            character=character,
            character_index=None,
            num_weeks=num_weeks,
            original_message=None,
            bar_color=bar_color,
            edge_color=edge_color,
        )

    async def handle_manual_reminder(
        self, interaction: discord.Interaction, mention: bool = False
    ) -> None:
        """Handle manual GPQ reminder."""
        user_roles = interaction.user.roles
        is_user_gpq_police = False
        for role in user_roles:
            if "GPQ Enforcer" in role.name:
                is_user_gpq_police = True

        if not interaction.permissions.manage_roles and not is_user_gpq_police:
            await interaction.response.send_message(
                "You do not have permissions to run this command."
            )
            return

        await interaction.response.defer()
        await self.send_reminder(interaction.followup, mention)

    async def handle_list_characters(self, interaction: discord.Interaction) -> None:
        """Handle listing user's characters."""
        await interaction.response.defer()

        # Check if server is set up
        if not check_server_setup(interaction):
            await send_setup_required_message(interaction)
            return

        db = get_database()  # TODO: Refactor to use proper database methods
        server_id = str(interaction.guild.id)
        player_ids = await self.get_validated_player_ids_for_user_or_character(
            interaction, db, server_id, None
        )
        if not player_ids:
            await interaction.followup.send("No characters found for your account.")
            return

        characters = [db.get_maplestory_username(player_id) for player_id in player_ids]
        await interaction.followup.send(f"{', '.join(characters)}")

    async def handle_rename_user(
        self, interaction: discord.Interaction, previous_ign: str, new_ign: str
    ) -> None:
        """Handle renaming a character."""
        await interaction.response.defer()
        if not interaction.permissions.manage_roles:
            await interaction.followup.send(
                "You do not have permissions to run this command."
            )
            return

        db = get_database()  # TODO: Refactor to use proper database methods

        # Get player ID for ign
        server_id = str(interaction.guild.id)
        player_id_for_user = db.get_row_for_maplestory_username(
            server_id, previous_ign, case_sensitive=True, fail_on_not_found=True
        )

        if not player_id_for_user:
            await interaction.followup.send(
                f"{previous_ign} not found in the database."
            )
            return

        # Copy player data
        data = db.get_player_data(player_id_for_user)
        data[0] = new_ign

        # Delete old player
        db.delete_player_by_id(player_id_for_user)

        # Create new player with updated name
        new_player_id = db.create_player_from_data(data)
        logger.info(f"Created new player with ID {new_player_id}")

        await interaction.followup.send(
            f"Successfully renamed {previous_ign} to {new_ign}"
        )

    async def handle_link_user(
        self,
        interaction: discord.Interaction,
        maple_name: str,
        discord_user: discord.User,
    ) -> None:
        """Handle linking a Discord user to a MapleStory character."""
        await interaction.response.defer()

        # Check if server is set up
        if not check_server_setup(interaction):
            await send_setup_required_message(interaction)
            return

        if not interaction.permissions.manage_roles:
            await interaction.followup.send(
                "You do not have permissions to run this command."
            )
            return

        db = get_database()  # TODO: Refactor to use proper database methods
        server_id = str(interaction.guild.id)
        player_id = db.get_row_for_maplestory_username(
            server_id, maple_name, fail_on_not_found=False, case_sensitive=True
        )
        if player_id is None:
            await interaction.followup.send(f"Error: Cannot find user {maple_name}")
            return

        db.link_user(player_id, discord_user, maple_name)

        if discord_user.get_role(MEMBER_ROLE_ID) is not None:
            await interaction.followup.send(
                f"Successfully linked {maple_name} to <@{discord_user.id}>."
            )
            return

        # Assign role to user
        guild = self.client.get_guild(GUILD_ID)
        role = guild.get_role(MEMBER_ROLE_ID)
        await discord_user.add_roles(role)

        # Change user nickname
        nickname = maple_name
        discord_name = discord_user.display_name or discord_user.name
        new_nickname = f"{discord_name} | {nickname}"
        if len(new_nickname) > 32:
            new_nickname = nickname
        await discord_user.edit(nick=f"{nickname}")

        response = "\n".join(
            [
                f"Successfully linked {maple_name} to <@{discord_user.id}>.\n",
                f"Welcome <@{discord_user.id}>! You've been given access to our discord bots.\n",
                "Please submit your culvert score weekly using the `/gpq [score]` command in https://discord.com/channels/1228053292261572628/1228053295940112525\n",
                "Grab your roles at <id:customize> and https://discord.com/channels/1228053292261572628/1228053295382265932\n",
                "And feel free to join vc! <a:ghostL:1228901617936371753>\n",
                "P.S. If you want to change your nickname, use the `/nickname` command from SpookieBot!",
            ]
        )

        guild_channel = self.client.get_channel(GUILD_CHAT_CHANNEL)
        await guild_channel.send(
            f"<@{discord_user.id}> just joined the guild. Welcome!"
        )

        await interaction.followup.send(response)

    async def handle_unlink_user(
        self, interaction: discord.Interaction, discord_user: discord.User
    ) -> None:
        """Handle unlinking all characters from a Discord user."""
        await interaction.response.defer()

        # Check if server is set up
        if not check_server_setup(interaction):
            await send_setup_required_message(interaction)
            return

        if not interaction.permissions.manage_roles:
            await interaction.followup.send(
                "You do not have permissions to run this command."
            )
            return

        db = get_database()  # TODO: Refactor to use proper database methods

        # get all player IDs for user
        server_id = str(interaction.guild.id)
        user_player_ids = db.get_rows_for_discord_id(server_id, discord_user.id)

        # Copy player data to left/kicked table
        player_data_list = []
        for player_id in user_player_ids:
            player_data = db.get_player_data(player_id)
            player_data_list.append(player_data)

        db.add_players_to_left_kicked(player_data_list)

        # Delete players
        for player_id in user_player_ids:
            db.delete_player_by_id(player_id)

        await interaction.followup.send(
            f"Successfully unlinked users for {discord_user}"
        )

    async def handle_guild_graph(
        self,
        interaction: discord.Interaction,
        num_weeks: int = 12,
        bar_color: str = DEFAULT_BAR_COLOR,
        edge_color: str = DEFAULT_EDGE_COLOR,
    ) -> None:
        """Handle guild cumulative GPQ graph generation."""
        await interaction.response.defer()

        # Check if server is set up
        if not check_server_setup(interaction):
            await send_setup_required_message(interaction)
            return

        # Check admin permissions
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.followup.send(
                "❌ You need manage roles permission to view guild statistics.",
                ephemeral=True,
            )
            return

        if num_weeks <= 0:
            await interaction.followup.send(
                "❌ Number of weeks must be greater than 0."
            )
            return

        # Validate colors
        valid_bar_color = (
            re.search(r"^(?:[0-9a-fA-F]{3}){1,2}$", bar_color) or bar_color == "0"
        )
        valid_edge_color = (
            re.search(r"^(?:[0-9a-fA-F]{3}){1,2}$", edge_color) or edge_color == "0"
        )

        if not valid_bar_color or not valid_edge_color:
            await interaction.followup.send(
                "Error: Color must be a 3 or 6 digit hex code or '0' to reset to default."
            )
            return

        if bar_color == "0":
            bar_color = DEFAULT_BAR_COLOR
        if edge_color == "0":
            edge_color = DEFAULT_EDGE_COLOR

        db = get_database()
        server_id = str(interaction.guild.id)

        # Get server profile for guild name
        server_profile = db.get_server_profile(server_id)
        guild_name = server_profile.guild_name if server_profile else "Guild"

        # Get cumulative scores by week
        cumulative_scores = db.get_guild_cumulative_scores_by_weeks(
            server_id, num_weeks
        )

        if not cumulative_scores:
            await interaction.followup.send("No GPQ data found for this guild.")
            return

        # Prepare data for plotting
        weeks = list(cumulative_scores.keys())
        scores = list(cumulative_scores.values())

        # Create shortened week labels for display
        week_labels = []
        for week in weeks:
            try:
                # Convert to short format for display
                from utils.time_utils import get_string_for_week

                # Parse and reformat for consistency
                week_labels.append(week.split("/")[0] + "/" + week.split("/")[1])
            except:
                week_labels.append(week)

        # Generate graph
        plt.close()
        plt.style.use(
            os.path.join(os.path.dirname(__file__), "..", "styles", "spooky.mplstyle")
        )

        plt.figure(figsize=(12, 8))
        plt.title(f"{guild_name} - Guild Cumulative GPQ Scores", fontsize="xx-large")

        p = plt.bar(
            week_labels,
            scores,
            align="center",
            edgecolor=f"#{edge_color}",
            linewidth=2,
            color=f"#{bar_color}",
        )

        # Add score labels on bars if not too many weeks
        if num_weeks <= 15:
            # Format labels with M/B notation
            formatted_labels = [self._format_score_display(score) for score in scores]
            plt.bar_label(
                p,
                labels=formatted_labels,
                bbox=dict(
                    facecolor="#e0e0e0",
                    boxstyle="round",
                    linewidth=0,
                ),
                padding=10,
                fontsize="large",
                color="black",
            )

        plt.ylim(bottom=0, top=(max(scores) * 1.15) if scores else 100000)

        # Handle x-axis label overlap
        if num_weeks > 15:
            plt.xticks(rotation=45, ha="right")
            ax = plt.gca()
            labels = ax.get_xticklabels()
            for i, label in enumerate(labels):
                if i != 0 and i != len(labels) - 1 and i % 2 != 0:
                    label.set_visible(False)
        elif num_weeks > 10:
            plt.xticks(rotation=45, ha="right")
        elif num_weeks > 6:
            plt.xticks(rotation=20, ha="right")

        plt.ylabel("Total Guild GPQ Score", fontsize="large")
        plt.xlabel("Week", fontsize="large")

        # Add average line
        if scores:
            avg_score = sum(scores) / len(scores)
            plt.axhline(
                y=avg_score, color="mediumaquamarine", linestyle="dashed", alpha=0.7
            )

        file_location = os.path.join("/tmp", str(uuid.uuid4()) + ".png")
        plt.savefig(file_location, dpi=150, bbox_inches="tight")

        # Create embed with guild stats
        embed = discord.Embed(title=f"{guild_name} - Guild GPQ Statistics")

        if scores:
            total_weeks = len(scores)
            avg_score = sum(scores) / total_weeks
            highest_week = max(scores)
            lowest_week = min(scores)

            embed.add_field(
                name="📊 Weeks Analyzed", value=f"{total_weeks}", inline=True
            )
            embed.add_field(
                name="📈 Average Weekly Total",
                value=self._format_score_display(avg_score),
                inline=True,
            )
            embed.add_field(
                name="🎯 Highest Week",
                value=self._format_score_display(highest_week),
                inline=True,
            )
            embed.add_field(
                name="📉 Lowest Week",
                value=self._format_score_display(lowest_week),
                inline=True,
            )
            embed.add_field(
                name="🌍 MapleStory World",
                value=server_profile.maplestory_world,
                inline=True,
            )
            embed.add_field(
                name="📋 Total Players",
                value=f"{len(db.get_all_players(server_id))}",
                inline=True,
            )

        file = discord.File(file_location, filename="guild_graph.png")
        embed.set_image(url="attachment://guild_graph.png")

        await interaction.followup.send(embed=embed, file=file)

        # Clean up
        os.remove(file_location)
        plt.close()

    def _format_score_display(self, score: float) -> str:
        """Format score for display with M/B notation."""
        if score >= 1_000_000_000:  # Billion
            return f"{score / 1_000_000_000:.1f}B"
        elif score >= 1_000_000:  # Million
            return f"{score / 1_000_000:.1f}M"
        else:  # Less than million, show raw number with commas
            return f"{score:,.0f}"

    async def get_validated_player_ids_for_user_or_character(
        self,
        interaction: discord.Interaction,
        db,  # MapleDatabase instance
        server_id: str,
        character: Optional[str],
        *,
        check_owned=False,
    ) -> Optional[List[int]]:
        """
        Get validated player IDs for a user or character.

        Args:
            interaction: Discord interaction object
            db: Database instance
            character: Character name (optional)
            check_owned: Whether to check if the user owns the character

        Returns:
            List of player IDs or None if validation fails
        """
        if character is not None:
            player_id = db.get_row_for_maplestory_username(
                server_id, character, fail_on_not_found=True, case_sensitive=False
            )
            if player_id is None:
                await interaction.followup.send(f"Error: No record for {character}")
                return None

            if check_owned:
                discord_id = db.get_discord_id(player_id)
                logger.info(f"{discord_id}, {interaction.user.id}")
                if str(discord_id) != str(interaction.user.id):
                    maple_user = db.get_maplestory_username(player_id)
                    await interaction.followup.send(
                        f"Error: You are not associated to {maple_user}."
                    )
                    return None

            return [player_id]

        player_ids = db.get_rows_for_discord_id(server_id, interaction.user.id)
        logger.info(f"{player_ids=}")
        if not player_ids:
            await interaction.followup.send(
                f"Error: No linked Maplestory users for <@{interaction.user.id}>"
            )
            return None

        return player_ids

    async def send_reminder(
        self, target: Union[discord.TextChannel, discord.Webhook], mention: bool
    ) -> None:
        """
        Send GPQ reminder to the specified target.

        Args:
            target: Channel or webhook to send reminder to
            mention: Whether to actually mention users
        """
        db = get_database()  # TODO: Refactor to use proper database methods

        current_date = get_current_datetime()
        current_week = get_string_for_week(current_date, True)

        logger.info(f"Current week: {current_week}")

        # Get all players and their current week scores for this server
        server_id = (
            str(target.guild.id)
            if hasattr(target, "guild") and target.guild
            else str(GUILD_ID)
        )
        players_with_scores = db.get_scores_for_week(server_id, current_week)

        missing_users: Set[str] = set()
        for player, score in players_with_scores:
            # If player has no score or score is 0, they haven't done GPQ
            if score is None or score == 0:
                if player.discord_id:
                    missing_users.add(player.discord_id)

        # GPQ deadline
        target_time = current_date - timedelta(minutes=10)
        target_unixtime = int(target_time.timestamp())

        if len(missing_users) == 0:
            await target.send("Everyone has done GPQ this week?!")
            return

        if mention:
            users_as_mentions = [f"<@{x}>" for x in missing_users]
        else:
            users_as_mentions = [f"{x}" for x in missing_users]

        # Just in case we hit the per-message character limit.
        batches = batch_list(users_as_mentions, 50)

        last_week_score = sum_cell_scores(last_week_cells)
        current_score = sum_cell_scores(cells)

        delta = (
            current_score / last_week_score * 100 - 100 if last_week_score > 0 else 0
        )
        plus_sign = "+" if delta > 0 else ""

        content = "\n".join(
            [
                f"**Last week GPQ total:** {last_week_score}",
                f"**Current GPQ total:** {current_score} ({plus_sign}{int(delta)}%)",
                "",
                "**NOTE: If you are getting pinged but already ran culvert this week, it means your score isn't in the system. Enter it in <#1228053295940112525> using /gpq <score>!**",
                "",
                f"The following people have not run GPQ yet! Please run before <t:{target_unixtime}:F> (<t:{target_unixtime}:R>)!",
                "",
                " ".join(batches[0]),
            ]
        )

        await target.send(content)
        for batch in batches[1:]:
            pings = " ".join(batch)
            await target.send(pings)

    async def async_update_guild_profile(
        self,
        interaction: discord.Interaction,
        character: Optional[str],
        character_index: Optional[int],
        original_message: Optional[discord.Message] = None,
    ) -> None:
        """
        Update and display a guild member's GPQ profile.

        Args:
            interaction: Discord interaction object
            character: Character name (optional)
            character_index: Character index for multi-character users
            original_message: Original message to edit (for reactions)
        """
        if not original_message:
            await interaction.response.defer()

        db = get_database()  # TODO: Refactor to use proper database methods

        server_id = str(interaction.guild.id)
        player_ids = await self.get_validated_player_ids_for_user_or_character(
            interaction, db, server_id, character
        )
        if not player_ids:
            await interaction.followup.send(
                "Error: Cannot find characters linked to user"
            )
            return

        player_id = (
            player_ids[0] if not character_index else player_ids[character_index]
        )

        current_week = get_current_week()

        # Get all player scores
        player_scores = db.get_player_scores(player_id)
        scores = [score.score for score in player_scores]
        scores = remove_leading_nones(scores)

        # Ignore the current week if the user hasn't done GPQ yet.
        if len(scores) > 0 and scores[-1] is None:
            scores = scores[:-1]

        maple_user = db.get_maplestory_username(player_id)

        embed = discord.Embed(
            title=f"{maple_user} Guild Profile - {current_week}",
        )

        if character is None:
            characters = [
                db.get_maplestory_username(player_id) for player_id in player_ids
            ]
            if len(characters) > 1:
                for i, name in enumerate(characters):
                    embed.add_field(
                        name=f"Character {i + 1}", value=f"{name}", inline=True
                    )

        last_valid_scores = [s for s in scores if s is not None and s > 0]
        if len(last_valid_scores) > 0:
            last_score = last_valid_scores[-1]
            embed.add_field(name="Last Score", value=last_score, inline=True)
        else:
            embed.add_field(name="Last Score", value="N/A", inline=True)

        # Could be up to 4, which is also ok.
        last_four_scores = scores[-4:]
        last_four_scores = convert_none_in_list(last_four_scores, 0)

        attempts_in_last_four_scores = [
            score for score in last_four_scores if score > 0
        ]
        if len(attempts_in_last_four_scores) > 0:
            monthly_average = round(
                sum(attempts_in_last_four_scores) / len(attempts_in_last_four_scores)
            )
            embed.add_field(name="Last 4 Average", value=monthly_average, inline=True)
        else:
            embed.add_field(name="Last 4 Average", value="N/A", inline=True)

        if len(last_four_scores) > 0:
            num_last_four_participated = len(attempts_in_last_four_scores)
            last_four_participation = (
                num_last_four_participated * 100.0 / len(last_four_scores)
            )
            embed.add_field(
                name="Last 4 Participation",
                value=f"{num_last_four_participated}/{len(last_four_scores)} ({round(last_four_participation)}%)",
                inline=True,
            )
        else:
            embed.add_field(name="Last 4 Participation", value=f"N/A", inline=True)

        embed.add_field(name="\u200b", value="```Lifetime Scores```", inline=False)

        scores_since_guild_joined = convert_none_in_list(scores, 0)

        if len(scores_since_guild_joined) > 0:
            highest_score = max(scores_since_guild_joined)
            embed.add_field(name="Personal Best", value=highest_score, inline=True)
        else:
            embed.add_field(name="Personal Best", value="N/A", inline=True)

        if len(scores_since_guild_joined) > 0:
            lifetime_score = sum(scores_since_guild_joined)
            embed.add_field(name="Lifetime Total", value=lifetime_score, inline=True)
        else:
            embed.add_field(name="Lifetime Total", value="N/A", inline=True)

        nonzero_scores_since_guild_joined = [
            v for v in scores_since_guild_joined if v > 0
        ]
        if len(nonzero_scores_since_guild_joined) > 0:
            total_average = round(
                sum(scores_since_guild_joined) / len(nonzero_scores_since_guild_joined)
            )
            embed.add_field(name="Total Average", value=total_average, inline=True)
        else:
            embed.add_field(name="Total Average", value="N/A", inline=True)

        if len(scores_since_guild_joined) > 0:
            num_participated = len(nonzero_scores_since_guild_joined)
            num_total = len(scores_since_guild_joined)
            participation = round(num_participated * 100.0 / num_total)
            embed.add_field(
                name="Participation",
                value=f"{num_participated}/{num_total} ({participation}%)",
                inline=True,
            )
        else:
            embed.add_field(name="Participation", value=f"N/A", inline=True)

        embed.set_footer(text="Submit scores with /gpq, visualize scores with /graph.")

        character_file_location = None
        try:
            response = requests.get(
                f"https://www.nexon.com/api/maplestory/no-auth/v1/ranking/na?type=overall&id=weekly&reboot_index=0&page_index=1&character_name={maple_user}"
            )
            data = response.json()
            character_url = data["ranks"][0]["characterImgURL"]

            file_location = os.path.join("/tmp", str(uuid.uuid4()) + ".png")
            response = requests.get(character_url, stream=True)
            with open(file_location, "wb") as out_file:
                shutil.copyfileobj(response.raw, out_file)

            character_file_location = file_location
        except Exception as e:
            logger.info("Error fetching image", e)

        file = None
        if character_file_location is not None:
            file = discord.File(character_file_location, filename="character.png")
            embed.set_thumbnail(url="attachment://character.png")

        if not original_message:
            message = await interaction.followup.send(embed=embed, file=file)
        else:
            if file:
                message = await original_message.edit(embed=embed, attachments=[file])
            else:
                # embed.set_thumbnail(None)
                message = await original_message.edit(embed=embed, attachments=[])

        if character is None:
            num_characters = len(rows)
            for emoji in EMOJI_ONE_TO_NINE[0:num_characters]:
                await message.add_reaction(emoji)

        if character_file_location:
            os.remove(character_file_location)

    async def async_update_gpq_graph(
        self,
        interaction: discord.Interaction,
        character: Optional[str],
        character_index: Optional[int],
        num_weeks: int = 7,
        original_message: Optional[discord.Message] = None,
        bar_color: str = DEFAULT_BAR_COLOR,
        edge_color: str = DEFAULT_EDGE_COLOR,
    ) -> None:
        """
        Generate and display a GPQ score graph.

        Args:
            interaction: Discord interaction object
            character: Character name (optional)
            character_index: Character index for multi-character users
            num_weeks: Number of weeks to display
            original_message: Original message to edit (for reactions)
            bar_color: Hex color for bars
            edge_color: Hex color for bar edges
        """
        if not original_message:
            await interaction.response.defer()

        db = get_database()  # TODO: Refactor to use proper database methods
        server_id = str(interaction.guild.id)
        player_ids = await self.get_validated_player_ids_for_user_or_character(
            interaction, db, server_id, character
        )
        logger.info(player_ids)
        if not player_ids:
            return
        player_id = (
            player_ids[0] if not character_index else player_ids[character_index]
        )

        current_week = get_current_week()
        logger.info(current_week)

        starting_weeks_ago = 0

        # Get all player scores
        player_scores = db.get_player_scores(player_id)
        scores = [score.score for score in player_scores]
        logger.info(f"{scores=}")

        # Ignore the current week if the user hasn't done GPQ yet.
        if scores and scores[-1] is None:
            scores = scores[:-1]
            starting_weeks_ago = 1

        scores = convert_none_in_list(scores, 0)
        scores = pad_list(scores, num_weeks, 0, True)
        highest_score = max(scores) if scores else 0
        sandbag_limit = highest_score * 0.85
        scores = scores[-num_weeks:]

        times = []
        for x in range(num_weeks + starting_weeks_ago - 1, starting_weeks_ago - 1, -1):
            week = get_week_ago(x)
            time = get_string_for_week(week, False)
            times.append(time)

        logger.info(f"{times=}")

        maple_user = db.get_maplestory_username(player_id)

        plt.close()

        plt.style.use(
            os.path.join(os.path.dirname(__file__), "..", "styles", "spooky.mplstyle")
        )

        plt.title(maple_user, fontsize="xx-large")
        p = plt.bar(
            times,
            scores,
            align="center",
            edgecolor=f"#{edge_color}",
            linewidth=2,
            color=f"#{bar_color}",
        )
        if num_weeks <= 10:
            # Format labels with M/B notation
            formatted_labels = [self._format_score_display(score) for score in scores]
            plt.bar_label(
                p,
                labels=formatted_labels,
                bbox=dict(
                    facecolor="#e0e0e0",
                    boxstyle="round",
                    linewidth=0,
                ),
                padding=10,
                fontsize="large",
                color="black",
            )
        plt.ylim(bottom=0, top=(max(scores) / 7) + max(scores) if scores else 100)

        # Handle x-axis label overlap based on number of weeks
        if num_weeks > 15:
            # For many weeks, rotate labels and show every other label, but keep the last one
            plt.xticks(rotation=45, ha="right")
            ax = plt.gca()
            labels = ax.get_xticklabels()
            for i, label in enumerate(labels):
                # Show first, last, and every other label
                if i != 0 and i != len(labels) - 1 and i % 2 != 0:
                    label.set_visible(False)
        elif num_weeks > 10:
            # For moderate weeks, just rotate labels
            plt.xticks(rotation=45, ha="right")
        elif num_weeks > 6:
            # For few weeks, rotate slightly
            plt.xticks(rotation=20, ha="right")

        # Plot highest score line
        plt.axhline(
            y=highest_score,
            color="mediumaquamarine",
            linestyle="dashed",
        )
        # Plot sandbag limit line
        plt.axhline(y=sandbag_limit, color="tomato", linestyle="dashed")

        file_location = os.path.join("/tmp", str(uuid.uuid4()) + ".png")
        plt.savefig(file_location)

        embed = discord.Embed(title="GPQ Score History")
        if character is None:
            characters = [
                db.get_maplestory_username(player_id) for player_id in player_ids
            ]
            if len(characters) > 1:
                for i, name in enumerate(characters):
                    embed.add_field(
                        name=f"Character {i + 1}", value=f"{name}", inline=True
                    )
        file = discord.File(file_location, filename="graph.png")
        embed.set_image(url="attachment://graph.png")

        if not original_message:
            if scores and scores[-1] < sandbag_limit:
                message = await interaction.followup.send(
                    "SANDBAGGER DETECTED <:ghostKnife:1229865119698259989>",
                    embed=embed,
                    file=file,
                )
            else:
                message = await interaction.followup.send(embed=embed, file=file)
        else:
            message = await original_message.edit(embed=embed, attachments=[file])

        if character is None:
            num_characters = len(player_ids)
            characters = [
                db.get_maplestory_username(player_id) for player_id in player_ids
            ]
            if len(characters) > 1:
                for emoji in EMOJI_ONE_TO_NINE[0:num_characters]:
                    await message.add_reaction(emoji)

        os.remove(file_location)

    def get_colors_for_user(
        self, discord_id: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Get user's color preferences for graphs.

        Args:
            discord_id: Discord user ID

        Returns:
            Tuple of (bar_color, edge_color) or (None, None) if not found
        """
        from core.config import COLORS_FILE
        import json

        try:
            with open(COLORS_FILE) as f:
                colors_dict = json.load(f)
            colors = colors_dict.get(discord_id, None)
            if colors and isinstance(colors, list) and len(colors) >= 2:
                return colors[0], colors[1]
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass
        return None, None

    def update_colors(
        self, discord_id: str, bar_color: Optional[str], edge_color: Optional[str]
    ) -> None:
        """
        Update user's color preferences for graphs.

        Args:
            discord_id: Discord user ID
            bar_color: Bar color (optional)
            edge_color: Edge color (optional)
        """
        from core.config import COLORS_FILE
        import json

        try:
            with open(COLORS_FILE) as f:
                colors_dict = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            colors_dict = {}

        colors = colors_dict.get(discord_id, None)

        if colors:
            if bar_color:
                colors[0] = bar_color
            if edge_color:
                colors[1] = edge_color
        else:
            colors = [bar_color or DEFAULT_BAR_COLOR, edge_color or DEFAULT_EDGE_COLOR]

        colors_dict[discord_id] = colors

        with open(COLORS_FILE, "w") as f:
            json.dump(colors_dict, f)

    async def upload_culvert_attachment(
        self,
        message: discord.Message,
        attachment: discord.Attachment,
        prev_week: bool = False,
    ) -> None:
        """
        Process culvert score attachment and update scores.

        Args:
            message: Discord message with attachment
            attachment: The attachment containing culvert scores
            prev_week: Whether to record scores for previous week
        """
        ign_to_culvert = {}

        file_path = os.path.join("/tmp", str(uuid.uuid4()) + ".png")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        await attachment.save(file_path)

        try:
            result = parse_results(send_request(file_path))
        except Exception as e:
            logger.error(e)
            await message.channel.send(f"Error processing attachment: {e}")
            return

        unprocessed_igns = set()
        updated_scores = {}

        for ign, culvert in result.items():
            unprocessed_igns.add(ign)
            # Clean up the ign
            ign_to_culvert[ign] = culvert

        os.remove(file_path)

        # Get all database data
        db = get_database()  # TODO: Refactor to use proper database methods
        values = db.get_all_gpq_cells()

        # Insert new scores
        current_week = get_current_week()
        target_week = get_last_week() if prev_week else current_week

        # Process each IGN and update scores
        for ign, score in ign_to_culvert.items():
            try:
                # Need to get server_id from message context
                server_id = str(message.guild.id) if message.guild else None
                if not server_id:
                    continue
                player_id = db.get_row_for_maplestory_username(
                    server_id, ign, case_sensitive=False
                )
                if player_id:
                    db.record_score_for_week(player_id, target_week, score)
                    updated_scores[ign] = score
                    unprocessed_igns.discard(ign)
            except Exception as e:
                logger.error(f"Error updating score for {ign}: {e}")

        # Send response about processed scores
        response_parts = []
        if updated_scores:
            response_parts.append("Successfully updated scores:")
            for ign, score in updated_scores.items():
                response_parts.append(f"  {ign}: {score}")

        if unprocessed_igns:
            response_parts.append(
                "\nFailed to process the following IGNs. Use /gpq to manually input scores:"
            )
            for ign in unprocessed_igns:
                response_parts.append(f"  {ign}")

        if response_parts:
            await message.channel.send("\n".join(response_parts))
        else:
            await message.channel.send("No scores were processed from the attachment.")
