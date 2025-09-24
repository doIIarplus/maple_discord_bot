"""Social commands module for the MapleStory Discord Bot."""

import json
import logging
import os
import random
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands

from core.constants import GUILD_ID, MACRO_CHANNEL_ID
from core.config import MACROS_FILE, QUOTES_FILE
from services.data_service import DataService
from services.spinner import spin_wheel
from integrations.db import get_database

logger = logging.getLogger(__name__)

# Guild object for command registration
GUILD_ID_OBJECT = discord.Object(id=GUILD_ID)

# Constants
FORBIDDEN_MACROS = ["now", "m"]


class SocialCommands:
    """Social commands for the Discord bot."""

    def __init__(self, client: discord.Client, tree: app_commands.CommandTree):
        """
        Initialize social commands.

        Args:
            client: Discord client
            tree: Discord command tree
        """
        self.client = client
        self.tree = tree
        self._register_commands()

    def _register_commands(self):
        """Register all social commands with the command tree."""

        @self.tree.command(
            name="quote", description="Random quote", guild=GUILD_ID_OBJECT
        )
        async def quote(interaction: discord.Interaction):
            """Get a random quote from the quotes database."""
            await self.handle_quote(interaction)

        @self.tree.command(
            name="addquote", description="Add a quote", guild=GUILD_ID_OBJECT
        )
        @app_commands.describe(
            quote="The thing that was said", user="The person who said the thing"
        )
        async def add_quote(
            interaction: discord.Interaction, quote: str, user: discord.User
        ):
            """Add a new quote to the quotes database."""
            await self.handle_add_quote(interaction, quote, user)

        @self.tree.command(
            name="nickname", description="Change your preferred nickname"
        )
        @app_commands.describe(nickname="What you want to be called")
        async def nickname(interaction: discord.Interaction, nickname: str):
            """Change the user's preferred nickname."""
            await self.handle_nickname(interaction, nickname)

        @self.tree.command(
            name="register_macro", description="Registers a !macro for images / videos"
        )
        @app_commands.describe(
            macro="The macro command, activated with !<macro>",
            attachment="The picture / video you want to register with the macro",
            message="Optional text message for the macro",
        )
        async def register_macro(
            interaction: discord.Interaction,
            macro: str,
            attachment: Optional[discord.Attachment] = None,
            message: Optional[str] = None,
        ):
            """Register a new macro with attachment and/or message."""
            await self.handle_register_macro(interaction, macro, attachment, message)

        @self.tree.command(name="remove_macro", description="Removes a !macro")
        @app_commands.describe(macro="The macro to remove")
        async def remove_macro(interaction: discord.Interaction, macro: str):
            """Remove an existing macro."""
            await self.handle_remove_macro(interaction, macro)

        @self.tree.command(name="spin", description="Spin a wheel!")
        @app_commands.describe(
            options="Comma-separated list of options to spin for",
            title="Optional title for the wheel",
        )
        async def spin(
            interaction: discord.Interaction, options: str, title: Optional[str] = None
        ):
            """Spin a wheel with the provided options."""
            await self.handle_spin(interaction, options, title)

    async def handle_quote(self, interaction: discord.Interaction):
        """Get a random quote from the quotes database."""
        await interaction.response.defer()

        quotes = DataService.load_json_file(QUOTES_FILE, [])

        if not quotes:
            await interaction.followup.send("No quotes available.")
            return

        random_quote = random.choice(quotes)
        message = random_quote["message"]
        user = random_quote["user"]
        year = random_quote["year"]

        await interaction.followup.send(f"{message} - <@{user}>, {year}")

    async def handle_add_quote(
        self, interaction: discord.Interaction, quote: str, user: discord.User
    ):
        """Add a new quote to the quotes database."""
        await interaction.response.defer()

        current_year = datetime.now().year

        quotes = DataService.load_json_file(QUOTES_FILE, [])
        quotes.append({"user": user.id, "message": quote, "year": current_year})

        if DataService.save_json_file(QUOTES_FILE, quotes):
            await interaction.followup.send(
                f"Quote added: \n{quote} - <@{user.id}>, {current_year}"
            )
        else:
            await interaction.followup.send("Failed to save quote. Please try again.")

    async def handle_nickname(self, interaction: discord.Interaction, nickname: str):
        """Change the user's preferred nickname."""
        await interaction.response.defer()

        user_roles = interaction.user.roles
        is_user_member = False
        for role in user_roles:
            if "Members" in role.name:
                is_user_member = True

        if not is_user_member:
            # User is not member, just change the entire nickname.
            await interaction.user.edit(nick=nickname)
            await interaction.followup.send("Nickname successfully changed.")
        else:
            db = get_database()

            server_id = str(interaction.guild.id)
            players = db.get_players_by_discord_id(server_id, interaction.user.id)
            if not players:
                await interaction.followup.send(
                    "Error: You are not linked to any characters. Please reach out to an Admin."
                )
                return

            player = players[0]
            maple_user = player.maplestory_username
            new_nick = f"{nickname} | {maple_user}"
            if nickname == maple_user:
                new_nick = maple_user
            if len(new_nick) > 32:
                await interaction.followup.send(
                    "Nickname too long, please enter your nickname only, not your IGN. Your IGN will be added automatically."
                )
                return
            else:
                await interaction.user.edit(nick=new_nick)
                await interaction.followup.send("Nickname successfully changed.")

    async def handle_register_macro(
        self,
        interaction: discord.Interaction,
        macro: str,
        attachment: Optional[discord.Attachment] = None,
        message: Optional[str] = None,
    ):
        """Register a new macro with attachment and/or message."""
        await interaction.response.defer()

        if attachment is None and message is None:
            await interaction.followup.send(
                "Must include at least one attachment or message"
            )
            return

        # Use database for server-specific macros
        db = get_database()
        server_id = str(interaction.guild.id)

        if macro.lower() in FORBIDDEN_MACROS:
            await interaction.followup.send("Invalid macro, please choose another one.")
            return

        # Check if macro already exists in this server
        existing_macro = db.get_macro(server_id, "!" + macro)
        if existing_macro is not None:
            await interaction.followup.send(
                f"Macro !{macro} already exists. Remove it using /remove_macro or choose a new name."
            )
            return

        # Send message to macros channel
        attachment_id = None
        if attachment:
            macros_channel = self.client.get_channel(MACRO_CHANNEL_ID)
            if macros_channel:
                file = await attachment.to_file()
                macro_message = await macros_channel.send(file=file)
                # save message id
                attachment_id = macro_message.id
            else:
                await interaction.followup.send("Error: Could not find macros channel.")
                return

        message_text = message or ""

        # Save to database (server-specific)
        if db.create_macro(server_id, "!" + macro, attachment_id, message_text):
            await interaction.followup.send(
                f"Macro !{macro} successfully registered for this server."
            )
        else:
            await interaction.followup.send("Failed to save macro. Please try again.")

    async def handle_remove_macro(self, interaction: discord.Interaction, macro: str):
        """Remove an existing macro."""
        await interaction.response.defer()

        # Use database for server-specific macros
        db = get_database()
        server_id = str(interaction.guild.id)

        # Check if macro exists in this server
        existing_macro = db.get_macro(server_id, "!" + macro)
        if existing_macro is None:
            await interaction.followup.send(
                f"Macro !{macro} doesn't exist in this server."
            )
            return

        # Remove macro from database
        if db.delete_macro(server_id, "!" + macro):
            await interaction.followup.send(
                f"Macro !{macro} successfully removed from this server."
            )
        else:
            await interaction.followup.send("Failed to remove macro. Please try again.")

    async def handle_spin(
        self,
        interaction: discord.Interaction,
        options: str,
        title: Optional[str] = None,
    ):
        """Spin a wheel with the provided options."""
        await interaction.response.defer()

        options_list = options.replace(" ", "").split(",")

        if len(options_list) < 2:
            await interaction.followup.send(
                "Please provide at least 2 options separated by commas."
            )
            return

        try:
            result, gif_file, path = spin_wheel(options_list, title=title)
            file = discord.File(path, filename=gif_file)
            await interaction.followup.send(content=f"{result}", file=file)
        except Exception as e:
            logger.error(f"Error creating spinner: {e}")
            await interaction.followup.send("Error creating spinner. Please try again.")
