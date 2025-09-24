"""Discord utility functions."""

import functools
import logging
import traceback
from typing import Callable, Any
import discord


def exception_handler(func: Callable) -> Callable:
    """Decorator to handle exceptions in Discord command functions."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {e}")
            traceback.print_exc()

            # Try to send an error message if we have an interaction
            for arg in args:
                if isinstance(arg, discord.Interaction):
                    try:
                        await arg.response.send_message(
                            f"An error occurred: {str(e)}", ephemeral=True
                        )
                    except:
                        pass
                    break

    return wrapper


async def send_long_message(
    channel: discord.TextChannel, content: str, max_length: int = 2000
):
    """
    Send a long message by splitting it into multiple messages if needed.

    Args:
        channel: Discord channel to send to
        content: Message content
        max_length: Maximum length per message
    """
    from utils.text_utils import split_by_newlines

    chunks = split_by_newlines(content, max_length)
    for chunk in chunks:
        await channel.send(chunk)
