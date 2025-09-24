"""Main Discord bot client and event handlers."""

import os
import random
import re
import discord
from discord import app_commands
from discord.ext import tasks
import json
import logging as logger
import traceback
from typing import Dict, List, Optional
import asyncio
from collections import deque
from datetime import datetime, timedelta, timezone
import pytz
import dateparser

from core.config import DISCORD_BOT_TOKEN, DEFAULT_SYSTEM_PROMPT, MACROS_FILE
from core.constants import GUILD_ID, MACRO_CHANNEL_ID, WELCOME_CHANNEL_ID, Timezones
from core.tasks import TaskManager
from services.ai_service import LLMService
from services.data_service import DataService
from utils.discord_utils import exception_handler, send_long_message
from commands.gpq_commands import GPQCommands
from commands.hexa_commands import HexaCommands
from commands.monitoring_commands import MonitoringCommands
from commands.social_commands import SocialCommands
from commands.ai_commands import AICommands
from commands.utility_commands import UtilityCommands
from commands.setup_commands import SetupCommands
from core.constants import GUILD_ID, WELCOME_CHANNEL_ID


class SpookieBot(discord.Client):
    """Main Discord bot client."""

    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(intents=intents)

        # Discord app commands tree
        self.tree = app_commands.CommandTree(self)

        # Services
        self.llm_service = LLMService()

        # Task manager for background tasks
        self.task_manager = TaskManager(self)

        # Queue for ping monitoring
        self.queue = deque()

        # Command modules
        self.gpq_commands = None
        self.hexa_commands = None
        self.monitoring_commands = None
        self.social_commands = None
        self.ai_commands = None
        self.utility_commands = None

        # Set up logging
        logger.basicConfig(
            format="%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d:%H:%M:%S",
            level=logger.INFO,
        )

    async def setup_hook(self):
        """Set up the bot after login."""
        logger.info("Setting up bot...")

        # Initialize command modules
        self.setup_commands = SetupCommands(self, self.tree)
        self.gpq_commands = GPQCommands(self, self.tree)
        self.hexa_commands = HexaCommands(self, self.tree)
        self.monitoring_commands = MonitoringCommands(self, self.tree)
        self.social_commands = SocialCommands(self, self.tree)
        self.ai_commands = AICommands(self, self.tree)
        self.utility_commands = UtilityCommands(self, self.tree)

        # Sync command tree
        await self.tree.sync()
        logger.info("Command tree synced")

        # Initialize monitoring
        self.monitoring_commands.initialize_monitoring()
        logger.info("Monitoring initialized")

        # Start background tasks
        self.task_manager.start_all_tasks()
        logger.info("Background tasks started")

        logger.info("Bot setup complete")

    async def on_ready(self):
        """Called when the bot is ready."""
        logger.info(f"Bot is ready! Logged in as {self.user}")
        logger.info(f"Bot is in {len(self.guilds)} guilds")
        for guild in self.guilds:
            logger.info(f"{guild.name} (id: {guild.id})")

    @exception_handler
    async def on_message(self, message: discord.Message):
        """Handle incoming messages."""
        if message.author.bot:
            return

        if (
            "<@1228796854272004096>" == message.content
            and message.author.id != 1228796854272004096
        ):
            if message.author.id == 1156804553459638272:
                await message.channel.send("stop fking pinging me ryan")
            else:
                await message.channel.send("what do u want lol")
            return

        # Handle specific message patterns
        # Handle !time command
        if message.content.startswith("!time"):
            await self._handle_time_command(message)
            return

        # Handle !m command (list macros)
        if message.content == "!m":
            await self._handle_list_macros(message)
            return

        # Handle !help command
        if message.content == "!help":
            await self._handle_help_command(message)
            return

        # Handle macro commands (messages starting with !)
        if message.content.startswith("!") and len(message.content) > 1:
            await self._handle_macro_command(message)
            return

        # Check if the bot was mentioned or the message is a DM
        bot_mentioned = self.user in message.mentions
        is_dm = isinstance(message.channel, discord.DMChannel)

        if bot_mentioned or is_dm:
            # Process with AI service
            server_id = str(message.guild.id) if message.guild else "DM"
            channel_id = str(message.channel.id)

            # Build context for AI
            files = []
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith(
                    "image/"
                ):
                    files.append(attachment)

            server_id = int(server_id)
            channel_id = int(channel_id)
            await self.llm_service.build_context(
                message=message, server=server_id, strip_mention=False, files=files
            )

            # Generate response
            try:
                async with message.channel.typing():
                    response = await self.llm_service.query_ollama(
                        server_id, channel_id
                    )

                    if response:
                        text = str(response[0])
                        # Split long responses across multiple messages
                        match = re.search(r"\{timeout:\s*(\d+)\}", text)
                        text = re.sub(r"\{timeout:\s*\d+\}", "", text)

                        if match:
                            timeout_value = int(match.group(1))
                            logger.info(f"Timing out user {message.author.display_name} for {timeout_value} minutes")
                            await message.author.timeout(timedelta(minutes=timeout_value), reason=f"timed out by spookiebot")

                        await send_long_message(message.channel, text)
                    else:
                        await message.channel.send(
                            "I'm having trouble generating a response right now."
                        )

            except Exception as e:
                logger.error(f"Error generating AI response: {e}")
                traceback.print_exc()
                await message.channel.send(
                    "Sorry, I encountered an error while processing your message."
                )

    @exception_handler
    async def on_member_join(self, member: discord.Member):
        pass
        # if member.guild.id != GUILD_ID:
        #     return
        # just_joined_channel = 1228053294463582350
        # channel = self.get_channel(just_joined_channel)
        # await asyncio.sleep(3)

        # img_dir = "src/images" <- needs to be changed into a relative dir
        # random_image = random.choice(os.listdir(img_dir))
        # file_location = os.path.join(img_dir, random_image)
        # if "mov" in file_location:
        #     filename = "arespukey.mov"
        # else:
        #     filename = "arespukey.png"
        # file = discord.File(file_location, filename=filename)
        # logger.info(f"Sending welcome message from file {random_image}")

        # await channel.send(f"<@{member.id}> R>Spookie", file=file)

    @exception_handler
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle reaction additions."""
        # This can be used for reaction-based features
        # Currently left as placeholder for future features
        pass

    async def close(self):
        """Clean up when shutting down."""
        logger.info("Shutting down bot...")

        # Stop background tasks
        self.task_manager.stop_all_tasks()

        # Clean up monitoring
        if self.monitoring_commands:
            self.monitoring_commands.cleanup_monitoring()

        # Close LLM service
        await self.llm_service.close()

        # Call parent close
        await super().close()

        logger.info("Bot shutdown complete")

    async def _handle_time_command(self, message: discord.Message):
        """Handle !time command for timezone conversion."""
        try:
            user_time = (
                message.content.split(" ", 1)[1]
                if len(message.content.split(" ", 1)) > 1
                else ""
            )
            if not user_time:
                await message.channel.send(
                    "❌ Please provide a time. Example: `!time today 8pm`"
                )
                return

            user_tz = "UTC"
            has_tz_role = False

            # Check for timezone role
            for role in message.author.roles:
                for tz in Timezones:
                    if role.name == tz.name:
                        has_tz_role = True
                        user_tz = tz.value
                        break

            confirmation_msg = ""
            if not has_tz_role:
                confirmation_msg = "User does not have a timezone role. Assuming UTC!\n"

            try:
                tz = pytz.timezone(user_tz if user_tz != "UTC" else "Etc/UTC")
            except pytz.UnknownTimeZoneError:
                await message.channel.send(f"❌ Unknown timezone: {user_tz}")
                return

            parsed_date = dateparser.parse(
                user_time,
                settings={
                    "TIMEZONE": tz.zone,
                    "RETURN_AS_TIMEZONE_AWARE": True,
                    "PREFER_DATES_FROM": "future",
                },
            )

            if not parsed_date:
                await message.channel.send(
                    "❌ Couldn't understand the date. Try something like 'Saturday at 10am'."
                )
                return

            unix_timestamp = int(parsed_date.timestamp())
            confirmation_msg += f"<t:{unix_timestamp}:F> (<t:{unix_timestamp}:R>)"

            await message.channel.send(confirmation_msg)

        except Exception as e:
            logger.error(f"Error handling time command: {e}")
            await message.channel.send("❌ Error processing time command.")

    async def _handle_list_macros(self, message: discord.Message):
        """Handle !m command to list all macros."""
        try:
            from integrations.db import get_database

            db = get_database()
            server_id = str(message.guild.id)

            macro_names = db.get_all_macros(server_id)
            if macro_names:
                all_macros = ", ".join(sorted(macro_names))
                await message.channel.send(all_macros)
            else:
                await message.channel.send(
                    "No macros registered for this server. Use `/register_macro` to add some!"
                )
        except Exception as e:
            logger.error(f"Error listing macros: {e}")
            await message.channel.send("❌ Error loading macros.")

    async def _handle_help_command(self, message: discord.Message):
        """Handle !help command."""
        help_text = (
            "**SpookieBot Commands**\n"
            "\n**Slash Commands:**\n"
            "`/gpq [score] [character]` - Add this week's GPQ score\n"
            "`/graph [character] [num_weeks]` - Graph last GPQ scores\n"
            "`/profile [character]` - Check GPQ profile\n"
            "`/list` - List linked Maplestory characters\n"
            "`/nickname [nickname]` - Change your preferred nickname\n"
            "`/quote` - Random quote\n"
            "`/addquote [quote] [user]` - Add a quote\n"
            "`/register_macro [macro] [attachment] [message]` - Registers a !macro\n"
            "`/remove_macro [macro]` - Removes a !macro\n"
            "`/ping` - Lists out channel latency info\n"
            "`/ping_graph [channel]` - Displays a graph of a channel ping over time\n"
            "`/hexa_calc` - Calculate Hexa skill costs\n"
            "`/hexa_load [character]` - Load saved Hexa skill data\n"
            "`/hexa_list` - List all your saved Hexa skill characters\n"
            "`/spin [options] [title]` - Spin a wheel\n"
            "\n**Prefix Commands:**\n"
            "`!help` - Show this help message\n"
            "`!m` - List all available macros\n"
            "`!time [time]` - Convert user's local time to UTC and relative time, e.g. !time today 8pm. User must have timezone role\n"
            "`![macro]` - Use a registered macro\n"
        )
        await message.channel.send(help_text)

    async def _handle_macro_command(self, message: discord.Message):
        """Handle !macro commands."""
        try:
            from integrations.db import get_database

            db = get_database()
            server_id = str(message.guild.id)

            # Remove the ! prefix for lookup
            macro_name = message.content
            macro_data = db.get_macro(server_id, macro_name)

            if macro_data is None:
                # Macro not found, ignore silently
                return

            attachment_id, message_content = macro_data
            final_message = ""

            # Handle attachment
            if attachment_id:
                try:
                    macro_channel = self.get_channel(MACRO_CHANNEL_ID)
                    if macro_channel:
                        macro_message = await macro_channel.fetch_message(attachment_id)
                        if macro_message.attachments:
                            attachment_link = macro_message.attachments[0].url
                            final_message = attachment_link
                except Exception as e:
                    traceback.print_exc()
                    logger.error(f"Error fetching macro attachment: {e}")

            # Handle text content
            if message_content:
                if final_message:
                    final_message += f"\n{message_content}"
                else:
                    final_message = message_content

            # Send the response
            if final_message:
                from integrations.latex_utils import split_text_and_latex

                messages = split_text_and_latex(final_message)
                for msg in messages:
                    await message.channel.send(msg)

        except Exception as e:
            logger.error(f"Error handling macro command: {e}")


def run_bot():
    """Run the Discord bot."""
    if not DISCORD_BOT_TOKEN:
        logger.error(
            "No Discord bot token found! Please set DISCORD_BOT_TOKEN environment variable."
        )
        return

    bot = SpookieBot()

    try:
        bot.run(DISCORD_BOT_TOKEN)
    except discord.LoginFailure:
        logger.error("Failed to login - invalid bot token")
    except Exception as e:
        logger.error(f"Unexpected error running bot: {e}")
        traceback.print_exc()
    finally:
        logger.info("Bot run finished")


if __name__ == "__main__":
    run_bot()
