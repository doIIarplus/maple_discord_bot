"""Server setup commands for the MapleStory Discord Bot."""

import discord
from discord import app_commands
from typing import Optional
import logging

from integrations.db import get_database

logger = logging.getLogger(__name__)

# MapleStory worlds
MAPLESTORY_WORLDS = ["Kronos", "Hyperion", "Scania", "Bera"]


class WorldSelect(discord.ui.Select):
    """Dropdown for selecting MapleStory world."""

    def __init__(self, guild_name: str, setup_user_id: str):
        self.guild_name = guild_name
        self.setup_user_id = setup_user_id

        # Create options for each world
        options = [
            discord.SelectOption(
                label=world, description=f"Set guild world to {world}", value=world
            )
            for world in MAPLESTORY_WORLDS
        ]

        super().__init__(
            placeholder="Choose your MapleStory world...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle world selection."""
        if str(interaction.user.id) != self.setup_user_id:
            await interaction.response.send_message(
                "❌ Only the user who started setup can complete it.", ephemeral=True
            )
            return

        selected_world = self.values[0]
        server_id = str(interaction.guild.id)

        # Save server profile to database
        db = get_database()
        success = db.create_server_profile(
            server_id=server_id,
            guild_name=self.guild_name,
            maplestory_world=selected_world,
            setup_by_user_id=self.setup_user_id,
        )

        if success:
            embed = discord.Embed(
                title="✅ Server Setup Complete!",
                description=f"**Guild Name:** {self.guild_name}\n**MapleStory World:** {selected_world}",
                color=discord.Color.green(),
            )
            embed.add_field(
                name="What's Next?",
                value=(
                    "🎮 Users can now use `/link` to connect their Discord to MapleStory characters\n"
                    "📊 Use `/gpq [score]` to track weekly Guild Party Quest scores\n"
                    "📈 Use `/graph` and `/profile` to view GPQ statistics\n"
                    "🎭 Register server-specific macros with `/register_macro`\n"
                    "❓ Use `/help` or `!help` to see all available commands"
                ),
                inline=False,
            )

            await interaction.response.edit_message(embed=embed, view=None)

            logger.info(
                f"Server {server_id} completed setup: {self.guild_name} on {selected_world}"
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to save server configuration. Please try again.",
                ephemeral=True,
            )


class WorldSelectView(discord.ui.View):
    """View containing the world selection dropdown."""

    def __init__(self, guild_name: str, setup_user_id: str):
        super().__init__(timeout=300)  # 5 minute timeout
        self.add_item(WorldSelect(guild_name, setup_user_id))

    async def on_timeout(self):
        """Handle view timeout."""
        # Disable all components
        for item in self.children:
            item.disabled = True


class SetupCommands:
    """Server setup commands."""

    def __init__(self, client: discord.Client, tree: app_commands.CommandTree):
        self.client = client
        self.tree = tree
        self._register_commands()

    def _register_commands(self):
        """Register setup commands."""

        @self.tree.command(
            name="setup",
            description="Set up this Discord server for MapleStory bot functionality",
        )
        @app_commands.describe(
            guild_name="Your MapleStory guild name",
        )
        async def setup(interaction: discord.Interaction, guild_name: str):
            """Set up the server for MapleStory bot functionality."""
            await self.handle_setup(interaction, guild_name)

    async def handle_setup(self, interaction: discord.Interaction, guild_name: str):
        """Handle server setup process."""
        # Check if user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need administrator permissions to set up the server.",
                ephemeral=True,
            )
            return

        server_id = str(interaction.guild.id)
        db = get_database()

        # Check if server is already set up
        if db.is_server_setup_complete(server_id):
            profile = db.get_server_profile(server_id)
            embed = discord.Embed(
                title="⚠️ Server Already Set Up",
                description=(
                    f"This server is already configured:\n\n"
                    f"**Guild Name:** {profile.guild_name}\n"
                    f"**MapleStory World:** {profile.maplestory_world}\n"
                    f"**Set up by:** <@{profile.setup_by_user_id}>\n"
                    f"**Set up at:** <t:{int(profile.setup_at.timestamp()) if hasattr(profile.setup_at, 'timestamp') else 0}:F>"
                ),
                color=discord.Color.orange(),
            )
            embed.add_field(
                name="Need to Change Settings?",
                value="Contact the bot administrator to update server configuration.",
                inline=False,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Validate guild name
        if not guild_name or len(guild_name.strip()) < 2:
            await interaction.response.send_message(
                "❌ Please provide a valid guild name (at least 2 characters).",
                ephemeral=True,
            )
            return

        guild_name = guild_name.strip()

        # Create setup embed with world selection
        embed = discord.Embed(
            title="🔧 Server Setup",
            description=(
                f"**Setting up:** {interaction.guild.name}\n"
                f"**Guild Name:** {guild_name}\n\n"
                "Please select your MapleStory world from the dropdown below:"
            ),
            color=discord.Color.blue(),
        )

        # Create view with world selection dropdown
        view = WorldSelectView(guild_name, str(interaction.user.id))

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


def check_server_setup(interaction: discord.Interaction) -> bool:
    """Check if server has completed setup. Returns True if setup is complete."""
    db = get_database()
    server_id = str(interaction.guild.id)
    return db.is_server_setup_complete(server_id)


async def send_setup_required_message(interaction: discord.Interaction):
    """Send a message directing users to complete server setup."""
    embed = discord.Embed(
        title="⚠️ Server Setup Required",
        description=(
            "This server hasn't been set up for MapleStory bot functionality yet.\n\n"
            "**An administrator needs to run `/setup` first.**"
        ),
        color=discord.Color.red(),
    )
    embed.add_field(
        name="For Administrators",
        value="Run `/setup [guild_name]` to configure this server for GPQ tracking.",
        inline=False,
    )
    embed.add_field(
        name="What Setup Configures",
        value=(
            "• Your MapleStory guild name\n"
            "• Your MapleStory world (Kronos, Hyperion, Scania, or Bera)\n"
            "• Enables GPQ score tracking and player linking"
        ),
        inline=False,
    )

    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)
