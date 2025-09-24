"""Utility commands for the Discord bot."""

import discord
from discord import app_commands
from typing import Optional
import logging

from utils.discord_utils import exception_handler
from core.config import DEFAULT_SYSTEM_PROMPT
from core.constants import GUILD_ID

GUILD_ID_OBJECT = discord.Object(id=GUILD_ID)


class UtilityCommands:
    """Container for utility slash commands."""

    def __init__(self, client: discord.Client, tree: app_commands.CommandTree):
        self.client = client
        self.tree = tree
        self._register_commands()

    def _register_commands(self):
        """Register all utility commands with the command tree."""

        @self.tree.command(
            name="test",
            description="Test command for debugging purposes",
            guild=GUILD_ID_OBJECT,
        )
        @exception_handler
        async def test(interaction: discord.Interaction):
            """Test command for debugging purposes."""
            await self.handle_test(interaction)

        @self.tree.command(
            name="parse_time",
            description="Parse and format time input",
            guild=GUILD_ID_OBJECT,
        )
        @app_commands.describe(
            time_input="Time to parse (e.g., 'tomorrow 3pm', 'next friday 7:30')"
        )
        @exception_handler
        async def parse_time(interaction: discord.Interaction, time_input: str):
            """Parse and format time input using the date_parse module."""
            await self.handle_parse_time(interaction, time_input)

    async def handle_test(self, interaction: discord.Interaction):
        """Test command for debugging purposes."""
        await interaction.response.send_message("Test command working!", ephemeral=True)
        logging.info(f"Test command executed by {interaction.user}")

    async def handle_parse_time(
        self, interaction: discord.Interaction, time_input: str
    ):
        """Parse and format time input using the date_parse module."""
        try:
            from services.date_parse import parse_input, format_availability

            parsed_time = parse_input(time_input)
            if parsed_time:
                formatted = format_availability([parsed_time])
                embed = discord.Embed(
                    title="Time Parsing Result",
                    description=f"**Input:** {time_input}\\n**Parsed:** {formatted}",
                    color=discord.Color.green(),
                )
            else:
                embed = discord.Embed(
                    title="Time Parsing Failed",
                    description=f"Could not parse: {time_input}",
                    color=discord.Color.red(),
                )

            await interaction.response.send_message(embed=embed)

        except ImportError:
            await interaction.response.send_message(
                "Date parsing module not available.", ephemeral=True
            )
        except Exception as e:
            logging.error(f"Error in parse_time: {e}")
            await interaction.response.send_message(
                f"Error parsing time: {str(e)}", ephemeral=True
            )


# Global variable for system prompt - this would be better managed
# by the AI service in the main bot integration
current_prompt = DEFAULT_SYSTEM_PROMPT
