"""AI-related commands for the Discord bot."""

import discord
from discord import app_commands
from typing import Optional, List
import logging

from utils.discord_utils import exception_handler
from services.ai_service import LLMService
from core.constants import GUILD_ID

GUILD_ID_OBJECT = discord.Object(id=GUILD_ID)


class AICommands:
    """Container for AI-related slash commands."""

    def __init__(self, client: discord.Client, tree: app_commands.CommandTree):
        self.client = client
        self.tree = tree
        self.llm_service = LLMService()
        self._register_commands()

    def _register_commands(self):
        """Register all AI commands with the command tree."""

        @self.tree.command(
            name="generate_image",
            description="Generate an image using AI",
            guild=GUILD_ID_OBJECT,
        )
        @app_commands.describe(
            prompt="Description of the image to generate",
            negative_prompt="What to avoid in the image (optional)",
        )
        @exception_handler
        async def generate_image(
            interaction: discord.Interaction,
            prompt: str,
            negative_prompt: Optional[str] = None,
        ):
            """Generate an image using AI."""
            await self.handle_generate_image(
                interaction, prompt, negative_prompt
            )

        @self.tree.command(
            name="set_system_prompt",
            description="Set the AI system prompt (Admin only)",
            guild=GUILD_ID_OBJECT,
        )
        @app_commands.describe(prompt="New system prompt for the AI")
        @exception_handler
        async def set_system_prompt(interaction: discord.Interaction, prompt: str):
            """Set the AI system prompt."""
            await self.handle_set_system_prompt(interaction, prompt)

        @self.tree.command(
            name="reset_system_prompt",
            description="Reset AI system prompt to default (Admin only)",
            guild=GUILD_ID_OBJECT,
        )
        @exception_handler
        async def reset_system_prompt(interaction: discord.Interaction):
            """Reset the AI system prompt to default."""
            await self.handle_reset_system_prompt(interaction)

    async def handle_generate_image(
        self,
        interaction: discord.Interaction,
        prompt: str,
        negative_prompt: Optional[str] = None,
    ):
        """Generate an image using AI."""
        await interaction.response.defer()

        try:
            # Generate the image using the AI service
            file_path, image_info, is_nsfw = await self.llm_service.gen_image(
                prompt=prompt, negative_prompt=negative_prompt
            )

            # If successful, send the image
            file = discord.File(file_path, filename="generated_image.png")
            
            # Spoiler the image if it's NSFW
            if is_nsfw:
                file.filename = "SPOILER_generated_image.png"

            embed = discord.Embed(
                title="Generated Image",
                description=f"**Prompt:** {prompt}",
                color=discord.Color.green(),
            )
            embed.set_image(url="attachment://generated_image.png")

            if negative_prompt:
                embed.add_field(
                    name="Negative Prompt", value=negative_prompt, inline=False
                )

            # Add image information to the embed
            image_info_text = (
                f"Steps: {image_info.steps}, "
                f"CFG: {image_info.cfg_scale}, "
                f"Size: {image_info.width}x{image_info.height}, "
                f"Seed: {image_info.seed}"
            )
            embed.add_field(name="Image Info", value=image_info_text, inline=False)

            if is_nsfw:
                embed.add_field(name="⚠️ NSFW Content", value="Warning: Potentially NSFW! Click at your own risk", inline=False)
                file.spoiler = True

            await interaction.followup.send(embed=embed, file=file)

        except Exception as e:
            logging.error(f"Error in generate_image: {e}")
            await interaction.followup.send(f"Error generating image: {str(e)}")

    async def handle_set_system_prompt(
        self, interaction: discord.Interaction, prompt: str
    ):
        """Set the AI system prompt."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need administrator permissions to use this command.",
                ephemeral=True,
            )
            return

        try:
            # Update the system prompt in the LLM service
            self.llm_service.set_system_prompt(prompt)

            embed = discord.Embed(
                title="System Prompt Updated",
                description=f"New prompt: {prompt[:500]}{'...' if len(prompt) > 500 else ''}",
                color=discord.Color.blue(),
            )
            await interaction.response.send_message(embed=embed)
            logging.info(f"System prompt updated by {interaction.user}")

        except Exception as e:
            logging.error(f"Error setting system prompt: {e}")
            await interaction.response.send_message(
                f"Error updating system prompt: {str(e)}", ephemeral=True
            )

    async def handle_reset_system_prompt(self, interaction: discord.Interaction):
        """Reset the AI system prompt to default."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need administrator permissions to use this command.",
                ephemeral=True,
            )
            return

        try:
            # Reset to default system prompt
            self.llm_service.reset_system_prompt()

            embed = discord.Embed(
                title="System Prompt Reset",
                description="System prompt has been reset to default.",
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=embed)
            logging.info(f"System prompt reset by {interaction.user}")

        except Exception as e:
            logging.error(f"Error resetting system prompt: {e}")
            await interaction.response.send_message(
                f"Error resetting system prompt: {str(e)}", ephemeral=True
            )
