"""Hexa calculator commands module for the MapleStory Discord Bot."""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

import discord
from discord import app_commands

from core.config import HEXA_COST_FILE, HEXA_USER_DATA_FILE
from core.constants import GUILD_ID
from services.data_service import DataService
from utils.discord_utils import exception_handler

logger = logging.getLogger(__name__)

# Hexa core cost data structure
HEXA_COSTS = {
    # Level: [origin_fragments, sol_erdas, sol_erda_energy]
    1: [35, 75, 0],
    2: [40, 90, 0],
    3: [50, 110, 0],
    4: [65, 135, 0],
    5: [85, 165, 0],
    6: [110, 200, 0],
    7: [145, 245, 0],
    8: [190, 300, 0],
    9: [250, 370, 0],
    10: [330, 455, 0],
    11: [435, 560, 25],
    12: [570, 690, 35],
    13: [750, 850, 50],
    14: [980, 1050, 65],
    15: [1285, 1300, 85],
    16: [1685, 1610, 110],
    17: [2205, 1990, 145],
    18: [2890, 2460, 190],
    19: [3780, 3040, 250],
    20: [4950, 3760, 330],
    21: [6480, 4640, 435],
    22: [8490, 5740, 570],
    23: [11115, 7100, 750],
    24: [14545, 8780, 980],
    25: [19045, 10850, 1285],
    26: [24945, 13410, 1685],
    27: [32665, 16580, 2205],
    28: [42795, 20490, 2890],
    29: [56055, 25320, 3780],
    30: [73375, 31300, 4950],
}

# Skill types for hexa cores
SKILL_TYPES = {
    "origin": "Origin",
    "mastery": "Mastery",
    "enhance": "Enhancement",
    "common": "Common",
}


class HexaCalcModal(discord.ui.Modal):
    """Modal for hexa core calculation input."""

    def __init__(self, user_id: int):
        super().__init__(title="Hexa Core Calculator")
        self.user_id = user_id

        # Character name input
        self.character_name = discord.ui.TextInput(
            label="Character Name",
            placeholder="Enter your character name",
            max_length=20,
            required=True,
        )
        self.add_item(self.character_name)

        # Current levels input
        self.current_levels = discord.ui.TextInput(
            label="Current Levels",
            placeholder="e.g., Origin: 15, Mastery1: 10, Mastery2: 8",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True,
        )
        self.add_item(self.current_levels)

        # Target levels input
        self.target_levels = discord.ui.TextInput(
            label="Target Levels",
            placeholder="e.g., Origin: 30, Mastery1: 25, Mastery2: 20",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True,
        )
        self.add_item(self.target_levels)

        # Current resources input
        self.current_resources = discord.ui.TextInput(
            label="Current Resources (Optional)",
            placeholder="Origin Fragments: 1000, Sol Erdas: 2000, Sol Erda Energy: 500",
            style=discord.TextStyle.paragraph,
            max_length=300,
            required=False,
        )
        self.add_item(self.current_resources)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        try:
            # Parse current and target levels
            current = self._parse_levels(self.current_levels.value)
            target = self._parse_levels(self.target_levels.value)

            # Parse current resources
            resources = (
                self._parse_resources(self.current_resources.value)
                if self.current_resources.value
                else {}
            )

            # Calculate cost differences
            cost_data = self._calculate_costs(current, target)

            # Save user data
            self._save_user_data(
                str(self.user_id), self.character_name.value, current, target, resources
            )

            # Create response embed
            embed = self._create_cost_embed(
                self.character_name.value, current, target, cost_data, resources
            )

            await interaction.response.send_message(embed=embed, ephemeral=False)

        except Exception as e:
            logger.error(f"Error in hexa calculation: {e}")
            await interaction.response.send_message(
                f"❌ Error processing your request: {str(e)}", ephemeral=True
            )

    def _parse_levels(self, levels_text: str) -> Dict[str, int]:
        """Parse level input text into a dictionary."""
        levels = {}

        # Split by commas and parse each entry
        entries = [entry.strip() for entry in levels_text.split(",")]

        for entry in entries:
            if ":" in entry:
                skill, level_str = entry.split(":", 1)
                try:
                    level = int(level_str.strip())
                    if 1 <= level <= 30:
                        levels[skill.strip().lower()] = level
                except ValueError:
                    continue

        return levels

    def _parse_resources(self, resources_text: str) -> Dict[str, int]:
        """Parse current resources text into a dictionary."""
        resources = {}

        # Split by commas and parse each entry
        entries = [entry.strip() for entry in resources_text.split(",")]

        for entry in entries:
            if ":" in entry:
                resource, amount_str = entry.split(":", 1)
                try:
                    amount = int(amount_str.strip())
                    resource_key = resource.strip().lower().replace(" ", "_")
                    resources[resource_key] = amount
                except ValueError:
                    continue

        return resources

    def _calculate_costs(
        self, current: Dict[str, int], target: Dict[str, int]
    ) -> Dict[str, List[int]]:
        """Calculate the cost difference for upgrading cores."""
        total_costs = [0, 0, 0]  # [origin_fragments, sol_erdas, sol_erda_energy]
        skill_costs = {}

        # Calculate cost for each skill
        for skill_name in target:
            current_level = current.get(skill_name, 1)
            target_level = target[skill_name]

            if target_level > current_level:
                skill_cost = [0, 0, 0]

                # Sum up costs from current level to target level
                for level in range(current_level + 1, target_level + 1):
                    if level in HEXA_COSTS:
                        costs = HEXA_COSTS[level]
                        skill_cost[0] += costs[0]  # origin_fragments
                        skill_cost[1] += costs[1]  # sol_erdas
                        skill_cost[2] += costs[2]  # sol_erda_energy

                skill_costs[skill_name] = skill_cost
                total_costs[0] += skill_cost[0]
                total_costs[1] += skill_cost[1]
                total_costs[2] += skill_cost[2]

        skill_costs["total"] = total_costs
        return skill_costs

    def _save_user_data(
        self,
        user_id: str,
        character_name: str,
        current: Dict[str, int],
        target: Dict[str, int],
        resources: Dict[str, int],
    ):
        """Save user hexa data."""
        user_data = DataService.get_hexa_user_data()

        if user_id not in user_data:
            user_data[user_id] = {}

        user_data[user_id][character_name] = {
            "current_levels": current,
            "target_levels": target,
            "current_resources": resources,
            "last_updated": datetime.now().isoformat(),
        }

        DataService.save_hexa_user_data(user_data)

    def _create_cost_embed(
        self,
        character_name: str,
        current: Dict[str, int],
        target: Dict[str, int],
        cost_data: Dict[str, List[int]],
        resources: Dict[str, int],
    ) -> discord.Embed:
        """Create an embed showing the cost calculation results."""
        embed = discord.Embed(
            title=f"🔮 Hexa Core Calculator - {character_name}",
            color=0x00FF88,
            timestamp=datetime.now(),
        )

        # Add skill progression field
        progression_text = ""
        for skill_name in target:
            current_level = current.get(skill_name, 1)
            target_level = target[skill_name]
            progression_text += (
                f"**{skill_name.title()}**: {current_level} → {target_level}\n"
            )

        embed.add_field(
            name="📊 Level Progression",
            value=progression_text or "No progressions specified",
            inline=False,
        )

        # Add total costs
        if "total" in cost_data:
            total_costs = cost_data["total"]
            costs_text = (
                f"**Origin Fragments**: {total_costs[0]:,}\n"
                f"**Sol Erdas**: {total_costs[1]:,}\n"
                f"**Sol Erda Energy**: {total_costs[2]:,}"
            )
            embed.add_field(name="💰 Total Costs", value=costs_text, inline=True)

        # Add current resources and remaining needed
        if resources:
            remaining_text = ""
            if "total" in cost_data:
                total_costs = cost_data["total"]

                # Calculate remaining needed
                fragments_needed = max(
                    0, total_costs[0] - resources.get("origin_fragments", 0)
                )
                erdas_needed = max(0, total_costs[1] - resources.get("sol_erdas", 0))
                energy_needed = max(
                    0, total_costs[2] - resources.get("sol_erda_energy", 0)
                )

                remaining_text = (
                    f"**Origin Fragments**: {fragments_needed:,}\n"
                    f"**Sol Erdas**: {erdas_needed:,}\n"
                    f"**Sol Erda Energy**: {energy_needed:,}"
                )

            embed.add_field(
                name="📋 Still Needed",
                value=remaining_text or "All resources available!",
                inline=True,
            )

        # Add individual skill costs
        skill_costs_text = ""
        for skill_name, costs in cost_data.items():
            if skill_name != "total":
                skill_costs_text += (
                    f"**{skill_name.title()}**:\n"
                    f"  OF: {costs[0]:,} | SE: {costs[1]:,} | SEE: {costs[2]:,}\n"
                )

        if skill_costs_text:
            embed.add_field(
                name="🎯 Individual Skill Costs", value=skill_costs_text, inline=False
            )

        embed.set_footer(
            text="Data saved automatically • Use /hexa_load to reload saved data"
        )
        return embed


class HexaCommands:
    """Container for hexa core calculator commands."""

    def __init__(self, client: discord.Client, tree: app_commands.CommandTree):
        self.client = client
        self.tree = tree
        self._register_commands()

    def _register_commands(self):
        """Register all hexa commands with the command tree."""

        @self.tree.command(
            name="hexa_calc", description="Calculate hexa core upgrade costs"
        )
        @exception_handler
        async def hexa_calc(interaction: discord.Interaction):
            """Open hexa core calculator modal."""
            await self.handle_hexa_calc(interaction)

        @self.tree.command(
            name="hexa_load", description="Load saved hexa data for a character"
        )
        @app_commands.describe(character_name="Name of the character to load data for")
        @exception_handler
        async def hexa_load(interaction: discord.Interaction, character_name: str):
            """Load saved hexa data for a character."""
            await self.handle_hexa_load(interaction, character_name)

        @self.tree.command(
            name="hexa_list", description="List all your saved hexa characters"
        )
        @exception_handler
        async def hexa_list(interaction: discord.Interaction):
            """List all saved hexa characters for the user."""
            await self.handle_hexa_list(interaction)

    async def handle_hexa_calc(self, interaction: discord.Interaction):
        """Open hexa core calculator modal."""
        modal = HexaCalcModal(interaction.user.id)
        await interaction.response.send_modal(modal)

    async def handle_hexa_load(
        self, interaction: discord.Interaction, character_name: str
    ):
        """Load saved hexa data for a character."""
        user_id = str(interaction.user.id)
        user_data = DataService.get_hexa_user_data()

        if user_id not in user_data:
            await interaction.response.send_message(
                "❌ No saved hexa data found for your account.", ephemeral=True
            )
            return

        # Find character (case-insensitive)
        character_data = None
        actual_name = None
        for name, data in user_data[user_id].items():
            if name.lower() == character_name.lower():
                character_data = data
                actual_name = name
                break

        if not character_data:
            available_chars = ", ".join(user_data[user_id].keys())
            await interaction.response.send_message(
                f"❌ No data found for character '{character_name}'.\n"
                f"Available characters: {available_chars}",
                ephemeral=True,
            )
            return

        # Create embed with saved data
        embed = discord.Embed(
            title=f"💾 Saved Hexa Data - {actual_name}",
            color=0x0099FF,
            timestamp=datetime.fromisoformat(
                character_data.get("last_updated", datetime.now().isoformat())
            ),
        )

        # Current levels
        current_levels = character_data.get("current_levels", {})
        if current_levels:
            levels_text = "\n".join(
                [
                    f"**{skill.title()}**: {level}"
                    for skill, level in current_levels.items()
                ]
            )
            embed.add_field(name="📊 Current Levels", value=levels_text, inline=True)

        # Target levels
        target_levels = character_data.get("target_levels", {})
        if target_levels:
            targets_text = "\n".join(
                [
                    f"**{skill.title()}**: {level}"
                    for skill, level in target_levels.items()
                ]
            )
            embed.add_field(name="🎯 Target Levels", value=targets_text, inline=True)

        # Current resources
        resources = character_data.get("current_resources", {})
        if resources:
            resources_text = ""
            for resource, amount in resources.items():
                resource_name = resource.replace("_", " ").title()
                resources_text += f"**{resource_name}**: {amount:,}\n"
            embed.add_field(
                name="💰 Current Resources", value=resources_text, inline=False
            )

        # Calculate and show costs if we have both current and target levels
        if current_levels and target_levels:
            modal = HexaCalcModal(interaction.user.id)
            cost_data = modal._calculate_costs(current_levels, target_levels)

            if "total" in cost_data:
                total_costs = cost_data["total"]
                costs_text = (
                    f"**Origin Fragments**: {total_costs[0]:,}\n"
                    f"**Sol Erdas**: {total_costs[1]:,}\n"
                    f"**Sol Erda Energy**: {total_costs[2]:,}"
                )
                embed.add_field(
                    name="💎 Total Upgrade Costs", value=costs_text, inline=False
                )

        embed.set_footer(text=f"Last updated")

        await interaction.response.send_message(embed=embed)

    async def handle_hexa_list(self, interaction: discord.Interaction):
        """List all saved hexa characters for the user."""
        user_id = str(interaction.user.id)
        user_data = DataService.get_hexa_user_data()

        if user_id not in user_data or not user_data[user_id]:
            await interaction.response.send_message(
                "❌ No saved hexa characters found. Use `/hexa_calc` to create some data first!",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="📋 Your Saved Hexa Characters",
            color=0x9932CC,
            timestamp=datetime.now(),
        )

        for character_name, data in user_data[user_id].items():
            # Get summary of character data
            current_levels = data.get("current_levels", {})
            target_levels = data.get("target_levels", {})
            last_updated = data.get("last_updated", "Unknown")

            # Format the last updated time
            try:
                update_time = datetime.fromisoformat(last_updated)
                time_str = update_time.strftime("%Y-%m-%d %H:%M")
            except:
                time_str = "Unknown"

            # Create summary text
            summary_text = f"**Last Updated**: {time_str}\n"

            if current_levels:
                levels_summary = ", ".join(
                    [
                        f"{skill.title()}: {level}"
                        for skill, level in list(current_levels.items())[:3]
                    ]
                )
                if len(current_levels) > 3:
                    levels_summary += f" (+{len(current_levels) - 3} more)"
                summary_text += f"**Current Levels**: {levels_summary}\n"

            if target_levels:
                targets_summary = ", ".join(
                    [
                        f"{skill.title()}: {level}"
                        for skill, level in list(target_levels.items())[:3]
                    ]
                )
                if len(target_levels) > 3:
                    targets_summary += f" (+{len(target_levels) - 3} more)"
                summary_text += f"**Target Levels**: {targets_summary}"

            embed.add_field(
                name=f"🔮 {character_name}", value=summary_text, inline=False
            )

        embed.set_footer(text=f"Use /hexa_load <character_name> to view detailed data")

        await interaction.response.send_message(embed=embed)

    async def handle_hexa_costs(
        self,
        interaction: discord.Interaction,
        start_level: int = 1,
        end_level: int = 30,
    ):
        """Show hexa core cost table for a range of levels."""
        if not (1 <= start_level <= 30) or not (1 <= end_level <= 30):
            await interaction.response.send_message(
                "❌ Level must be between 1 and 30.", ephemeral=True
            )
            return

        if start_level > end_level:
            await interaction.response.send_message(
                "❌ Start level must be less than or equal to end level.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"💎 Hexa Core Costs (Levels {start_level}-{end_level})",
            color=0xFF6B35,
            timestamp=datetime.now(),
        )

        costs_text = "```\nLvl | Origin Frags | Sol Erdas | Sol Energy\n"
        costs_text += "----+-------------+----------+-----------\n"

        total_fragments = 0
        total_erdas = 0
        total_energy = 0

        for level in range(start_level, min(end_level + 1, 31)):
            if level in HEXA_COSTS:
                costs = HEXA_COSTS[level]
                total_fragments += costs[0]
                total_erdas += costs[1]
                total_energy += costs[2]

                costs_text += (
                    f"{level:3d} | {costs[0]:11,} | {costs[1]:8,} | {costs[2]:9,}\n"
                )

        costs_text += "----+-------------+----------+-----------\n"
        costs_text += (
            f"Tot | {total_fragments:11,} | {total_erdas:8,} | {total_energy:9,}\n```"
        )

        embed.add_field(name="📊 Cost Breakdown", value=costs_text, inline=False)

        # Add summary
        summary_text = (
            f"**Total Origin Fragments**: {total_fragments:,}\n"
            f"**Total Sol Erdas**: {total_erdas:,}\n"
            f"**Total Sol Erda Energy**: {total_energy:,}"
        )
        embed.add_field(name="💰 Summary", value=summary_text, inline=False)

        embed.set_footer(text="Costs are cumulative from your specified starting level")

        await interaction.response.send_message(embed=embed)
