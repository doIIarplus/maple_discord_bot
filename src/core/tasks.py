"""Background tasks module for the MapleStory Discord Bot.

This module contains all scheduled background tasks including:
- GPQ reminder scheduling
- Recruitment reminders
- Ping monitoring and notifications
- Thread health monitoring and restart
"""

import asyncio
import logging
import statistics
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Union, cast
import multiprocessing as mp

import discord
from discord.ext import tasks

from core.constants import REMINDER_CHANNEL_ID
from utils.ping_utils import CHANNEL_TO_IP, DEFAULT_PORT, Packet, PingCheckingThread
from integrations.db import get_database

from utils.time_utils import (
    get_current_datetime,
    get_seconds_until_reminder,
    get_string_for_week,
)
from utils import batch_list, clean_sheet_value, sum_cell_scores

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages all background tasks for the Discord bot."""

    def __init__(self, client: discord.Client):
        """Initialize the task manager with a Discord client.

        Args:
            client: The Discord client instance
        """
        self.client = client
        self.logger = logging.getLogger(__name__)

        # Task safety mechanism
        self.last_reminder_trigger: Optional[datetime] = None
        self.SAFETY_TIME_SECONDS = 60 * 60 * 1  # 1 hour safety buffer

        # Ping monitoring state
        self.ping_checking_threads: List[PingCheckingThread] = []
        self.channel_ping_history: Dict[int, deque] = {}
        self.channel_ping_averages: Dict[int, Tuple[float, float]] = {}
        self.queue: Optional[mp.Queue] = None

        # Initialize ping history for each channel
        for channel in CHANNEL_TO_IP.keys():
            self.channel_ping_history[channel] = deque(
                [], 150
            )  # 5 minutes, 2 seconds per tick

    def initialize_ping_monitoring(self, queue: mp.Queue) -> None:
        """Initialize ping monitoring threads.

        Args:
            queue: Multiprocessing queue for thread communication
        """
        self.queue = queue
        self.logger.info("Setting up ping checking threads")

        for channel, ip_addr in CHANNEL_TO_IP.items():
            channel_thread = PingCheckingThread(
                result_queue=queue, channel=channel, ip_addr=ip_addr, port=DEFAULT_PORT
            )
            channel_thread.start()
            self.ping_checking_threads.append(channel_thread)

        self.logger.info("Ping checking threads initialized")

    def start_all_tasks(self) -> None:
        """Start all background tasks."""
        try:
            self.send_reminder_task.start()
            self.logger.info("Started GPQ reminder task")
        except RuntimeError:
            self.logger.warning("GPQ reminder task already running")

        try:
            self.check_threads_and_restart.start()
            self.logger.info("Started thread monitoring task")
        except RuntimeError:
            self.logger.warning("Thread monitoring task already running")

        try:
            self.send_recruit_reminder.start()
            self.logger.info("Started recruitment reminder task")
        except RuntimeError:
            self.logger.warning("Recruitment reminder task already running")

        try:
            self.check_ping_and_notify.start()
            self.logger.info("Started ping monitoring task")
        except RuntimeError:
            self.logger.warning("Ping monitoring task already running")

    def stop_all_tasks(self) -> None:
        """Stop all background tasks."""
        tasks_to_stop = [
            self.send_reminder_task,
            self.check_threads_and_restart,
            self.send_recruit_reminder,
            self.check_ping_and_notify,
        ]

        for task in tasks_to_stop:
            if task.is_running():
                task.cancel()
                self.logger.info(f"Stopped task: {task}")

    def restart_recruit_reminder(self) -> None:
        """Restart the recruitment reminder task."""
        if self.send_recruit_reminder.is_running():
            self.send_recruit_reminder.cancel()
        self.send_recruit_reminder.start()
        self.logger.info("Restarted recruitment reminder task")

    @tasks.loop(count=None)
    async def send_reminder_task(self) -> None:
        """Main GPQ reminder task with safety mechanisms."""
        # Safety check to prevent too frequent reminders
        if (
            self.last_reminder_trigger is not None
            and (
                datetime.now(timezone.utc) - self.last_reminder_trigger
            ).total_seconds()
            < self.SAFETY_TIME_SECONDS
        ):
            self.logger.info("Error: Reminder safety triggered.")
            await asyncio.sleep(self.SAFETY_TIME_SECONDS)
            return

        seconds_to_sleep = get_seconds_until_reminder()
        self.logger.info(f"Sleeping {seconds_to_sleep} seconds until reminder")
        await asyncio.sleep(seconds_to_sleep)

        self.last_reminder_trigger = datetime.now(timezone.utc)

        try:
            channel = cast(
                discord.TextChannel, self.client.get_channel(REMINDER_CHANNEL_ID)
            )
            if channel is None:
                self.logger.error("Error: Cannot find reminder channel")
                return

            await self._send_reminder(channel, mention=True)
        except Exception as e:
            self.logger.error(f"Error in send_reminder_task: {e}")

    @tasks.loop(count=1)
    async def send_recruit_reminder(self) -> None:
        """Send recruitment reminder after 7 hours."""
        seconds_to_sleep = 7 * 60 * 60  # 7 hours
        self.logger.info(
            f"Sleeping {seconds_to_sleep} seconds until recruitment reminder"
        )
        await asyncio.sleep(seconds_to_sleep)

        try:
            channel_id = 1238503401189277830
            channel = self.client.get_channel(channel_id)
            if channel:
                await channel.send("<@&1228053292941316312>")
                self.logger.info("Sent recruitment reminder")
            else:
                self.logger.error("Could not find recruitment channel")
        except Exception as e:
            self.logger.error(f"Error in send_recruit_reminder: {e}")

    @tasks.loop(minutes=5)
    async def check_ping_and_notify(self) -> None:
        """Monitor ping and notify if thresholds are exceeded."""
        if self.queue is None:
            return

        try:
            # Process all pending ping packets
            while self.queue.qsize() != 0:
                packet = self.queue.get()
                self.channel_ping_history[packet.channel].append(packet)

            # Calculate averages and standard deviations for each channel
            for channel in CHANNEL_TO_IP.keys():
                pings = [packet.ping for packet in self.channel_ping_history[channel]]

                if len(pings) != 0:
                    channel_avg = round(statistics.mean(pings), 2)
                    channel_std_dev = round(statistics.stdev(pings), 2)
                    self.channel_ping_averages[channel] = (channel_avg, channel_std_dev)

            # Check for high ping or standard deviation
            highest_avg_ping = sorted(
                self.channel_ping_averages.items(), key=lambda x: x[1][0], reverse=True
            )
            highest_std_dev = sorted(
                self.channel_ping_averages.items(), key=lambda x: x[1][1], reverse=True
            )

            high_ping, high_std_dev = (False, False)

            for ping in highest_avg_ping:
                if ping[1][0] > 200:  # 200ms threshold
                    high_ping = True
                    break

            for ping in highest_std_dev:
                if ping[1][1] > 100:  # 100ms std dev threshold
                    high_std_dev = True
                    break

            # Notify if thresholds are exceeded
            if high_ping or high_std_dev:
                try:
                    null_user = await self.client.fetch_user(118567805678256128)
                    await null_user.send(
                        "Ping or Std dev is above threshold! Use the ping command to check which channel has high std dev"
                    )
                    self.logger.warning(
                        "High ping or std dev detected, notification sent"
                    )
                except Exception as e:
                    self.logger.error(f"Failed to send ping notification: {e}")

        except Exception as e:
            self.logger.error(f"Error in check_ping_and_notify: {e}")

    @tasks.loop(minutes=10)
    async def check_threads_and_restart(self) -> None:
        """Monitor ping checking threads and restart dead ones."""
        if self.queue is None:
            return

        try:
            dead_thread_channels = []

            # Identify dead threads
            for thread in self.ping_checking_threads:
                if not thread.is_alive():
                    self.logger.error(f"Thread for channel {thread._channel} is dead")
                    dead_thread_channels.append(thread._channel)
                    thread._handled = True

            # Remove dead threads from the list
            self.ping_checking_threads = [
                t for t in self.ping_checking_threads if not t._handled
            ]

            # Restart threads for dead channels
            for channel in dead_thread_channels:
                self.logger.info(f"Spinning up new thread for channel {channel}")
                channel_thread = PingCheckingThread(
                    result_queue=self.queue,
                    channel=channel,
                    ip_addr=CHANNEL_TO_IP[channel],
                    port=DEFAULT_PORT,
                )
                channel_thread.start()
                self.ping_checking_threads.append(channel_thread)

        except Exception as e:
            self.logger.error(f"Error in check_threads_and_restart: {e}")

    async def _send_reminder(
        self, target: Union[discord.TextChannel, discord.Webhook], mention: bool
    ) -> None:
        """Send GPQ reminder to the specified target.

        Args:
            target: The channel or webhook to send the reminder to
            mention: Whether to mention users in the reminder
        """
        try:
            db = get_database()

            current_date = get_current_datetime()
            current_week = get_string_for_week(current_date, True)

            self.logger.info(f"Current week: {current_week}")

            # Get all players and their scores for current week for the main guild
            from .constants import GUILD_ID

            server_id = str(GUILD_ID)

            # Get all players and their scores for current week for this server
            server_players_with_scores = db.get_scores_for_week(server_id, current_week)

            # Find users who haven't done GPQ this week
            missing_users = set()

            for player, score in server_players_with_scores:
                # If player has no score or score is 0/None, they haven't done GPQ
                if score is None or score == 0:
                    if player.discord_id:
                        missing_users.add(player.discord_id)

            if len(missing_users) == 0:
                await target.send("Everyone has done GPQ this week?!")
                return

            # Format user mentions
            if mention:
                users_as_mentions = [f"<@{x}>" for x in missing_users]
            else:
                users_as_mentions = [f"{x}" for x in missing_users]

            # Batch users to avoid message length limits
            batches = batch_list(users_as_mentions, 50)

            last_week_score = sum_cell_scores(last_week_cells)

            # Send reminder messages
            for batch in batches:
                message = f"GPQ deadline is in 10 minutes!\n{', '.join(batch)}"
                await target.send(message)

            # Send additional context about last week's performance
            await target.send(f"Last week's total GPQ score: {last_week_score}")

            self.logger.info(f"Sent GPQ reminder to {len(missing_users)} users")

        except Exception as e:
            self.logger.error(f"Error sending reminder: {e}")
            raise
