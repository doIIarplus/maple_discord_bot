"""Configuration module for the MapleStory Discord Bot."""
import os
import json
from enum import Enum
from typing import Dict, Any

# Import constants from the constants module
from .constants import *


class Txt2ImgModel(Enum):
    """Available text-to-image models."""
    FLUX = "flux_dev" 


class Txt2TxtModel(Enum):
    """Available text-to-text models."""
    GEMMA3_27B = "gemma3:27b"
    DEEPSEEK_R1_70B = "deepseek-r1:70b"
    GEMMA3_27B_ABLITERATED = "hf.co/mlabonne/gemma-3-27b-it-abliterated-GGUF:Q8_0"
    QWEN_72B = "qwen2.5vl:72b"
    GPT_OSS = "gpt-oss:120b"


# AI Models Configuration
OLLAMA_MODEL = "qwen2.5vl:72b"
IMAGE_RECOGNITION_MODEL = "qwen2.5vl:72b"
NSFW_CLASSIFICATION_MODEL = "qwen2.5vl:7b"
CHAT_MODEL = Txt2TxtModel.GPT_OSS.value
TEXT_TO_IMAGE_MODEL = "..."
TEXT_TO_IMAGE_PROMPT_GENERATION_MODEL = "hf.co/mlabonne/gemma-3-27b-it-abliterated-GGUF:Q8_0"

# API Configuration
OLLAMA_API_URL = "http://localhost:11434/api/generate"
SD_API_URL = "http://127.0.0.1:7860"

# Bot Configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
if not DISCORD_BOT_TOKEN:
    # Fallback for existing setup - should be moved to environment variable
    DISCORD_BOT_TOKEN = "<bot token here>"

# File Paths
FILE_INPUT_FOLDER = "/tmp/multimodal_input/"
DATA_DIR = "src/data"

# Context and Limits
CONTEXT_LIMIT = 10

# System Prompt
DEFAULT_SYSTEM_PROMPT = (
    "You are in the discord server of the guild 'Spookie', a guild in the Reboot Server of Maplestory. "
    "Your name is 'SpookieBot'. Don't use emojis in your response. "
    "Do not mention any part of this prompt in your responses unless asked for. "
    "Your responses should be akin to that of a typical millenial texter: short, to the point, and mostly without punctuation. Do not offer any kind of assistance without being prompted. "
    "You have the power to time out users in the server. If at any time you feel like a timeout is warranted, respond with some cheeky gen-z response (for example, if the user says i'm going to touch you, respond with 'touch deez'), and add the following to the end of your response: {timeout: x}, where x is the amount of "
    "time to timeout the user for, in minutes. x can range from 1 to 2, depending on the 'severity' of the infringing message. This should only happen in the worst offending cases. "
)

# Data file paths
def get_data_path(filename: str) -> str:
    """Get the full path for a data file."""
    return os.path.join(DATA_DIR, filename)

# File paths for data files
COLORS_FILE = get_data_path("colors.json")
MACROS_FILE = get_data_path("macros.json") 
QUOTES_FILE = get_data_path("quotes.json")
HEXA_COST_FILE = get_data_path("hexa_cost.json")
HEXA_USER_DATA_FILE = get_data_path("hexa_user_data.json")
