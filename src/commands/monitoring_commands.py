"""Monitoring and ping utilities for the MapleStory Discord Bot."""

import asyncio
import os
import statistics
import uuid
from collections import deque
from typing import Dict, List, Tuple, Optional
import multiprocessing as mp

import discord
from discord import app_commands
from discord.ext import tasks
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import logging

from core.config import DEFAULT_SYSTEM_PROMPT
from core.constants import GUILD_ID
from utils.ping_utils import DEFAULT_PORT, CHANNEL_TO_IP, Packet, PingCheckingThread

# Configure logging
logger = logging.getLogger(__name__)

# Global monitoring state
queue: Optional[mp.Queue] = None
ping_checking_threads: List[PingCheckingThread] = []
channel_ping_history: Dict[int, deque] = {}
channel_ping_averages: Dict[int, Tuple[float, float]] = {}


class MonitoringCommands:
    """Commands for monitoring MapleStory server latency and network performance."""

    def __init__(self, client: discord.Client, tree: app_commands.CommandTree):
        self.client = client
        self.tree = tree
        self._setup_commands()

    def _setup_commands(self) -> None:
        """Set up the monitoring slash commands."""

        @self.tree.command(
            name="ping",
            description="Lists out channel latency info over the last 5 minutes",
        )
        async def ping_command(interaction: discord.Interaction):
            """Display channel latency information for MapleStory servers."""
            await self.handle_ping_command(interaction)

        @self.tree.command(
            name="ping_graph",
            description="Displays a graph of a channel ping over time",
        )
        @app_commands.describe(channel="Maplestory channel")
        async def ping_graph_command(interaction: discord.Interaction, channel: int):
            """Display a graph showing ping history for a specific MapleStory channel."""
            await self.handle_ping_graph_command(interaction, channel)

    async def handle_ping_command(self, interaction: discord.Interaction) -> None:
        """
        Display channel latency information for MapleStory servers.

        Shows:
        - Channels with highest average ping
        - Channels with highest standard deviation (most unstable)
        - Channels with lowest average pings
        - Channels with lowest standard deviations (most stable)

        Args:
            interaction: Discord interaction object
        """
        await interaction.response.defer()
        global queue

        # Process any pending ping data
        while queue and queue.qsize() != 0:
            packet = queue.get()
            channel_ping_history[packet.channel].append(packet)

        # Calculate ping statistics for each channel
        for channel in CHANNEL_TO_IP.keys():
            pings = [
                packet.ping
                for packet in channel_ping_history[channel]
                if packet.success
            ]

            if len(pings) != 0:
                channel_avg = round(statistics.mean(pings), 2)
                channel_std_dev = round(statistics.stdev(pings), 2)
                channel_ping_averages[channel] = (channel_avg, channel_std_dev)

        embed = discord.Embed(
            title="Maplestory Channel Latency",
        )

        # Sort channels by different metrics
        highest_avg_ping = sorted(
            channel_ping_averages.items(), key=lambda x: x[1][0], reverse=True
        )
        highest_std_dev = sorted(
            channel_ping_averages.items(), key=lambda x: x[1][1], reverse=True
        )

        # Highest ping section
        embed.add_field(
            name="================Channels with highest average ping================",
            value="",
            inline=False,
        )
        embed.add_field(
            name="Channel",
            value="\n".join([str(item[0]) for item in highest_avg_ping[:5]]),
            inline=True,
        )
        embed.add_field(
            name="Ping (5 Min. Avg)",
            value="\n".join([str(item[1][0]) for item in highest_avg_ping[:5]]),
            inline=True,
        )
        embed.add_field(
            name="Standard Deviation",
            value="\n".join([str(item[1][1]) for item in highest_avg_ping[:5]]),
            inline=True,
        )

        # Highest standard deviation section
        embed.add_field(
            name="=============Channels with highest standard deviation=============",
            value="",
            inline=False,
        )
        embed.add_field(
            name="Channel",
            value="\n".join([str(item[0]) for item in highest_std_dev[:5]]),
            inline=True,
        )
        embed.add_field(
            name="Ping (5 Min. Avg)",
            value="\n".join([str(item[1][0]) for item in highest_std_dev[:5]]),
            inline=True,
        )
        embed.add_field(
            name="Standard Deviation",
            value="\n".join([str(item[1][1]) for item in highest_std_dev[:5]]),
            inline=True,
        )

        # Lowest ping section
        embed.add_field(
            name="================Channels with lowest average pings================",
            value="",
            inline=False,
        )
        embed.add_field(
            name="Channel",
            value="\n".join([str(item[0]) for item in highest_avg_ping[::-1][:5]]),
            inline=True,
        )
        embed.add_field(
            name="Ping (5 Min. Avg)",
            value="\n".join([str(item[1][0]) for item in highest_avg_ping[::-1][:5]]),
            inline=True,
        )
        embed.add_field(
            name="Standard Deviation",
            value="\n".join([str(item[1][1]) for item in highest_avg_ping[::-1][:5]]),
            inline=True,
        )

        # Lowest standard deviation section
        embed.add_field(
            name="=============Channels with lowest standard deviations=============",
            value="",
            inline=False,
        )
        embed.add_field(
            name="Channel",
            value="\n".join([str(item[0]) for item in highest_std_dev[::-1][:5]]),
            inline=True,
        )
        embed.add_field(
            name="Ping (5 Min. Avg)",
            value="\n".join([str(item[1][0]) for item in highest_std_dev[::-1][:5]]),
            inline=True,
        )
        embed.add_field(
            name="Standard Deviation",
            value="\n".join([str(item[1][1]) for item in highest_std_dev[::-1][:5]]),
            inline=True,
        )

        embed.set_footer(
            text="Note: The higher the standard deviation, the more `unstable` a channel is. Ping in unstable channels are more likely to spike up and down randomly."
        )

        await interaction.followup.send(embed=embed)

    async def handle_ping_graph_command(
        self, interaction: discord.Interaction, channel: int
    ) -> None:
        """
        Display a graph showing ping history for a specific MapleStory channel.

        Args:
            interaction: Discord interaction object
            channel: Channel number to display graph for (1-40)
        """
        await interaction.response.defer()
        global queue

        print(f"adding {queue.qsize() if queue else 0} items to list")

        # Process any pending ping data
        while queue and queue.qsize() != 0:
            packet = queue.get()
            channel_ping_history[packet.channel].append(packet)

        # Extract ping data for the requested channel
        channel_pings = [
            packet.ping
            for packet in channel_ping_history.get(channel, [])
            if packet.success
        ]
        channel_times = [
            packet.time
            for packet in channel_ping_history.get(channel, [])
            if packet.success
        ]

        if not channel_pings:
            await interaction.followup.send(
                f"No ping data available for channel {channel}"
            )
            return

        # Create the graph
        plt.close()
        plt.style.use(
            os.path.join(os.path.dirname(__file__), "..", "styles", "spooky.mplstyle")
        )
        _, ax = plt.subplots(1, 1)
        ax.plot(channel_times, channel_pings, color="#46FFD1", linewidth=1)
        ax.tick_params(axis="x", rotation=90)
        ax.xaxis.set_major_locator(mdates.SecondLocator(interval=15))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%M:%S"))
        plt.subplots_adjust(bottom=0.01, left=0.09, right=0.99, top=0.99)
        plt.yticks(fontsize=15)
        plt.xticks([])

        # Save and send the graph
        file_location = os.path.join("/tmp", str(uuid.uuid4()) + ".png")
        plt.savefig(file_location)
        embed = discord.Embed(
            title=f"Channel {channel} Latency History (Last 5 Minutes)"
        )
        file = discord.File(file_location, filename="graph.png")
        embed.set_image(url="attachment://graph.png")
        await interaction.followup.send(embed=embed, file=file)

        # Clean up temporary file
        os.remove(file_location)

    def initialize_monitoring(self):
        """Initialize monitoring system."""
        initialize_monitoring()

    def cleanup_monitoring(self):
        """Clean up monitoring resources."""
        cleanup_monitoring()


async def check_ping_and_notify(client: discord.Client) -> None:
    """
    Background task to check ping data and notify when thresholds are exceeded.

    Monitors ping averages and standard deviations, sending notifications
    when values exceed configured thresholds.

    Args:
        client: Discord client instance
    """
    global queue

    if not queue:
        return

    # Process any pending ping data
    while queue.qsize() != 0:
        packet = queue.get()
        channel_ping_history[packet.channel].append(packet)

    # Calculate statistics for each channel
    for channel in CHANNEL_TO_IP.keys():
        pings = [
            packet.ping for packet in channel_ping_history[channel] if packet.success
        ]

        if len(pings) != 0:
            channel_avg = round(statistics.mean(pings), 2)
            channel_std_dev = round(statistics.stdev(pings), 2)
            channel_ping_averages[channel] = (channel_avg, channel_std_dev)

    # Sort channels by metrics to find problematic ones
    highest_avg_ping = sorted(
        channel_ping_averages.items(), key=lambda x: x[1][0], reverse=True
    )
    highest_std_dev = sorted(
        channel_ping_averages.items(), key=lambda x: x[1][1], reverse=True
    )

    # Check if any channels exceed thresholds
    high_ping, high_std_dev = (False, False)

    for ping in highest_avg_ping:
        if ping[1][0] > 200:  # 200ms threshold for high ping
            high_ping = True
            break

    for ping in highest_std_dev:
        if ping[1][1] > 100:  # 100ms threshold for high standard deviation
            high_std_dev = True
            break

    # Send notification if thresholds are exceeded
    if high_ping or high_std_dev:
        try:
            null_user = await client.fetch_user(118567805678256128)
            await null_user.send(
                "Ping or Std dev is above threshold! use the ping command to check which channel has high std dev"
            )
        except Exception as e:
            logger.error(f"Failed to send ping notification: {e}")


@tasks.loop(minutes=10)
async def check_threads_and_restart() -> None:
    """
    Periodic task to check if ping monitoring threads are alive and restart dead ones.

    This task runs every 10 minutes to ensure continuous monitoring of all channels.
    """
    global ping_checking_threads, queue

    if not queue:
        return

    dead_thread_channels = []
    for thread in ping_checking_threads:
        if not thread.is_alive():
            logger.error(f"Thread for channel {thread._channel} is dead")
            dead_thread_channels.append(thread._channel)
            thread._handled = True

    # Remove dead threads from the list
    ping_checking_threads = [t for t in ping_checking_threads if not t._handled]

    # Restart threads for dead channels
    for channel in dead_thread_channels:
        logger.info(f"Spinning up new thread for channel {channel}")
        channel_thread = PingCheckingThread(
            result_queue=queue,
            channel=channel,
            ip_addr=CHANNEL_TO_IP[channel],
            port=DEFAULT_PORT,
        )
        channel_thread.start()
        ping_checking_threads.append(channel_thread)


def initialize_monitoring() -> None:
    """
    Initialize the monitoring system by setting up threads and data structures.

    This should be called during bot startup to begin monitoring all channels.
    """
    global queue, ping_checking_threads, channel_ping_history

    logger.info("Initializing ping monitoring system...")

    # Create multiprocessing queue for thread communication
    m = mp.Manager()
    queue = m.Queue()

    # Initialize data structures
    ping_checking_threads.clear()
    channel_ping_history.clear()

    # Start monitoring threads for each channel
    logger.info("Setting up ping monitoring threads...")
    for channel, ip_addr in CHANNEL_TO_IP.items():
        channel_thread = PingCheckingThread(
            result_queue=queue, channel=channel, ip_addr=ip_addr, port=DEFAULT_PORT
        )
        channel_thread.start()
        ping_checking_threads.append(channel_thread)
        channel_ping_history[channel] = deque([], 150)  # 5 minutes, 2 seconds per tick

    logger.info(f"Started monitoring threads for {len(CHANNEL_TO_IP)} channels")

    # Start the thread restart task
    check_threads_and_restart.start()
    logger.info("Monitoring system initialized successfully")


def cleanup_monitoring() -> None:
    """
    Clean up monitoring resources when shutting down.

    Stops all threads and clears data structures.
    """
    global ping_checking_threads, queue

    logger.info("Cleaning up monitoring system...")

    # Stop the restart task
    if check_threads_and_restart.is_running():
        check_threads_and_restart.stop()

    # Mark all threads for cleanup
    for thread in ping_checking_threads:
        thread._handled = True

    # Clear global state
    ping_checking_threads.clear()
    channel_ping_history.clear()
    channel_ping_averages.clear()

    logger.info("Monitoring system cleanup completed")


# Monitoring statistics helper functions
def get_channel_statistics(channel: int) -> Optional[Tuple[float, float, int]]:
    """
    Get statistics for a specific channel.

    Args:
        channel: Channel number to get statistics for

    Returns:
        Tuple of (average_ping, std_deviation, sample_count) or None if no data
    """
    if channel not in channel_ping_history:
        return None

    pings = [packet.ping for packet in channel_ping_history[channel] if packet.success]

    if not pings:
        return None

    avg_ping = round(statistics.mean(pings), 2)
    std_dev = round(statistics.stdev(pings), 2) if len(pings) > 1 else 0.0

    return (avg_ping, std_dev, len(pings))


def get_best_channels(count: int = 5) -> List[Tuple[int, float, float]]:
    """
    Get the channels with the lowest average ping.

    Args:
        count: Number of channels to return

    Returns:
        List of tuples (channel, avg_ping, std_dev) sorted by lowest ping
    """
    if not channel_ping_averages:
        return []

    sorted_channels = sorted(channel_ping_averages.items(), key=lambda x: x[1][0])

    return [(ch, avg, std) for ch, (avg, std) in sorted_channels[:count]]


def get_most_stable_channels(count: int = 5) -> List[Tuple[int, float, float]]:
    """
    Get the channels with the lowest standard deviation (most stable).

    Args:
        count: Number of channels to return

    Returns:
        List of tuples (channel, avg_ping, std_dev) sorted by lowest std dev
    """
    if not channel_ping_averages:
        return []

    sorted_channels = sorted(channel_ping_averages.items(), key=lambda x: x[1][1])

    return [(ch, avg, std) for ch, (avg, std) in sorted_channels[:count]]
