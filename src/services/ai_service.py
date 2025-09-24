"""AI/LLM Service module for the MapleStory Discord Bot."""

import base64
import json
import os
import re
import time
import traceback
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union
from aiohttp import ClientSession
import discord

from core.config import (
    OLLAMA_API_URL,
    SD_API_URL,
    IMAGE_RECOGNITION_MODEL,
    NSFW_CLASSIFICATION_MODEL,
    CHAT_MODEL,
    TEXT_TO_IMAGE_PROMPT_GENERATION_MODEL,
    CONTEXT_LIMIT,
    FILE_INPUT_FOLDER,
    DEFAULT_SYSTEM_PROMPT,
)
from integrations.latex_utils import split_text_and_latex


@dataclass
class ImageInfo:
    """Information about generated images."""

    sampler_name: str
    steps: int
    cfg_scale: float
    width: int
    height: int
    seed: int


class LLMService:
    """Service class for handling AI/LLM operations."""

    MAX_DISCORD_MESSAGE_LENGTH = 1900  # leave room for footer

    def __init__(self):
        """Initialize the LLM service."""
        # Per-server per channel context
        self.context: Dict[str, Dict[str, List[Dict]]] = {}
        self._setup_output_directories()

    def _setup_output_directories(self) -> None:
        """Set up output directories for generated content."""
        self.out_dir = "api_out"
        self.out_dir_t2i = os.path.join(self.out_dir, "txt2img")
        self.out_dir_i2i = os.path.join(self.out_dir, "img2img")
        os.makedirs(self.out_dir_t2i, exist_ok=True)
        os.makedirs(self.out_dir_i2i, exist_ok=True)

    def pick_model(self, server: str, channel: int) -> str:
        """
        Pick the appropriate model based on context.

        Args:
            server: Server ID as string
            channel: Channel ID

        Returns:
            Model name to use
        """
        # If the last message has an image, use image recognition model
        if (
            server in self.context
            and channel in self.context[server]
            and len(self.context[server][channel]) > 0
            and self.context[server][channel][-1].get("images")
        ):
            return IMAGE_RECOGNITION_MODEL
        else:
            return CHAT_MODEL

    async def build_context(
        self,
        message: discord.Message,
        server: int,
        strip_mention: bool = False,
        files: List[str] = [],
    ) -> None:
        """
        Build conversation context from a Discord message.

        Args:
            message: Discord message object
            server: Server ID
            strip_mention: Whether to strip bot mentions from content
            files: List of file paths to process
        """
        channel = message.channel.id
        server_str = str(server)

        if server_str not in self.context:
            self.context[server_str] = {}

        if channel not in self.context[server_str]:
            self.context[server_str][channel] = []

        prompt = (
            message.content
            if not strip_mention
            else message.clean_content.replace(
                f"@{message.guild.me.display_name}", ""
            ).strip()
        )

        images = []
        if files:
            for file in files:
                try:
                    with open(file, "rb") as image_file:
                        encoded_string = base64.b64encode(image_file.read()).decode(
                            "utf-8"
                        )
                        images.append(encoded_string)
                except Exception as e:
                    print(f"Error processing file {file}: {e}")

        author = message.author.display_name
        self.context[server_str][channel].append(
            {
                "role": "user",
                "name": f"{author}",
                "content": prompt,
                "timestamp": time.time(),
                "images": images,
            }
        )

        # Keep context within limits
        if len(self.context[server_str][channel]) > CONTEXT_LIMIT:
            self.context[server_str][channel].pop(0)

    def format_prompt(self, messages: List[Dict]) -> str:
        """
        Format conversation messages into a prompt.

        Args:
            messages: List of message dictionaries

        Returns:
            Formatted prompt string
        """
        prompt = ""
        for msg in messages:
            role = "User" if msg["role"] == "user" else "Assistant"
            name = f"({msg.get('name', '')})" if msg["role"] == "user" else ""
            prompt += f"{role} {name}: {msg['content']}\n"
        prompt += "Assistant: "
        return prompt

    def process_response(
        self, text: str, limit: int = MAX_DISCORD_MESSAGE_LENGTH
    ) -> List[Union[str, Dict]]:
        """
        Process AI response text, handling LaTeX rendering and length limits.

        Args:
            text: Raw response text
            limit: Maximum message length

        Returns:
            List of processed response parts
        """
        # Remove thinking tags
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        processed_response = split_text_and_latex(text)
        print(f"Processed response: {processed_response}")
        return processed_response

    async def query_ollama(
        self, server: int, channel: int
    ) -> Union[List[Union[str, Dict]], Tuple[discord.Embed, discord.File]]:
        """
        Query the Ollama API with conversation context.

        Args:
            server: Server ID
            channel: Channel ID

        Returns:
            Either a list of response parts or a tuple of (embed, file) for images
        """
        server_str = str(server)
        messages = self.context[server_str][channel]
        prompt = self.format_prompt(messages)
        images = messages[-1].get("images", [])

        # Check if this is an image generation task
        is_img_task = await self.is_image_gen_task(messages[-1]["content"])

        if is_img_task:
            prompt = await self.generate_image_gen_prompt(messages[-1]["content"])
            file_path, image_info, is_nsfw = await self.gen_image(prompt, "")
            file = discord.File(fp=file_path, filename="generated.png")
            image_info_text = (
                f"steps: {image_info.steps}, "
                f"cfg: {image_info.cfg_scale}, "
                f"size: {image_info.width}x{image_info.height}, "
                f"seed: {image_info.seed}"
            )
            embed = discord.Embed()
            embed.set_image(url="attachment://generated.png")
            embed.set_footer(text=image_info_text)
            if is_nsfw:
                file.spoiler = True

            return (embed, file)

        # Add system prompt for regular text generation
        system_prompt = (
            f"{DEFAULT_SYSTEM_PROMPT}"
        )
        prompt = f"System: {system_prompt}\n" + prompt

        if images:
            print("Sending image for processing")

        try:
            model = self.pick_model(server_str, channel)
            print(f"Using model: {model}")

            async with ClientSession() as session:
                async with session.post(
                    OLLAMA_API_URL,
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "images": images,
                    },
                ) as resp:
                    print(f"Prompt: {prompt}")
                    data = await resp.json()
                    raw_response = data.get("response", "No response from Ollama.")
                    if raw_response == "No response from Ollama.":
                        print(f"API Response: {data}")

                    self.context[server_str][channel].append(
                        {
                            "role": "assistant",
                            "content": raw_response,
                            "timestamp": time.time(),
                        }
                    )

                    # Dump the context into a text file for debugging
                    with open("output.txt", "w") as file:
                        json.dump(self.context, file, indent=4)

                    print(f"Response: {raw_response}")
                    return self.process_response(raw_response)

        except Exception as e:
            print(f"Error querying Ollama: {e}")
            print(traceback.format_exc())
            return [f"Error communicating with Ollama: {e}"]

    async def is_image_gen_task(self, prompt: str) -> bool:
        """
        Determine if a prompt is requesting image generation.

        Args:
            prompt: User prompt to analyze

        Returns:
            True if prompt requests image generation
        """
        print(f"Checking if '{prompt}' is an image gen task")
        system_prompt = (
            "You are a classifier that classifies whether a prompt is an instruction to generate an image or not. Your response should "
            "only contain two possible outcomes: Yes and No. Yes if the prompt contains an instruction to generate an image, and No if it does not. "
            "For example, prompts containing 'create an image' or 'generate an image of', etc. will return 'Yes'. Not all prompts that contain words like "
            "'image' or 'picture' should return 'yes'. For example, prompts such as 'what is in this image' should return No"
        )

        formatted_prompt = f"System: {system_prompt}\nUser: {prompt}\nAssistant: "

        try:
            async with ClientSession() as session:
                async with session.post(
                    OLLAMA_API_URL,
                    json={
                        "model": CHAT_MODEL,
                        "prompt": formatted_prompt,
                        "stream": False,
                    },
                ) as resp:
                    data = await resp.json()
                    raw_response = data.get("response", "No response from Ollama.")
                    print(f"Image gen classification response: {raw_response}")
                    return "yes" in raw_response.lower()

        except Exception as e:
            print(f"Error in image gen classification: {e}")
            print(traceback.format_exc())
            return False

    async def generate_image_gen_prompt(self, prompt: str) -> str:
        """
        Generate a diffusion-model friendly prompt from user input.

        Args:
            prompt: User's original prompt

        Returns:
            Optimized prompt for image generation
        """
        system_prompt = (
            "You are a tool that generates prompts for image generation tasks for diffusion-based image generation models. "
            "Given the user prompt in plain text, output a diffusion model friendly prompt. Attempt to be as specific as possible, "
            "and separate tags and concepts with commas. For example, if the prompt is 'generate a photorealistic image of charlie puth', a possible prompt "
            "could be 'high definition, photorealistic, charlie puth, 1man'. It's ok to have the tags be more descriptive and akin to natural language. "
            "for example, for the above prompt, a tag could be 'picture of charlie puth' instead of 'charlie puth, photograph'. "
            "Do not include tags such as 'trending on artstation'. "
        )

        formatted_prompt = f"System: {system_prompt}\nUser: {prompt}\nAssistant: "
        print(f"Image prompt generation input: {formatted_prompt}")

        try:
            async with ClientSession() as session:
                async with session.post(
                    OLLAMA_API_URL,
                    json={
                        "model": TEXT_TO_IMAGE_PROMPT_GENERATION_MODEL,
                        "prompt": formatted_prompt,
                        "stream": False,
                    },
                ) as resp:
                    data = await resp.json()
                    raw_response = data.get("response", "No response from Ollama.")
                    print(f"Generated image prompt: {raw_response}")
                    return raw_response

        except Exception as e:
            print(f"Error generating image prompt: {e}")
            print(traceback.format_exc())
            return prompt  # Fallback to original prompt

    async def is_image_nsfw(self, image_path: str) -> bool:
        """
        Classify an image as NSFW or SFW.

        Args:
            image_path: Path to the image file

        Returns:
            True if image is classified as NSFW
        """
        images = []
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
                images.append(encoded_string)
        except Exception as e:
            print(f"Error encoding image for NSFW check: {e}")
            return False

        system_prompt = (
            "You are a classifier that classifies images as NSFW (not safe for work) or "
            "SFW (safe for work). Your response should only contain two possible outcomes: "
            "NSFW and SFW. Output NSFW if the image contains explicit or potentially sensitive material that makes it "
            "not suitable for all audiences, and SFW if it is safe for all audiences. Consider depictions of women's bare legs or legs that "
            "display a significant portion of the thighs as 'NSFW' as well."
        )

        user_prompt = "Is this image NSFW?"
        formatted_prompt = f"System: {system_prompt}\nUser: {user_prompt}\nAssistant: "

        try:
            async with ClientSession() as session:
                async with session.post(
                    OLLAMA_API_URL,
                    json={
                        "model": NSFW_CLASSIFICATION_MODEL,
                        "prompt": formatted_prompt,
                        "stream": False,
                        "images": images,
                    },
                ) as resp:
                    data = await resp.json()
                    raw_response = data.get("response", "No response from Ollama.")
                    print(f"NSFW classification response: {raw_response}")
                    return "nsfw" in raw_response.lower()

        except Exception as e:
            print(f"Error in NSFW classification: {e}")
            print(traceback.format_exc())
            return False

    @staticmethod
    def _timestamp() -> str:
        """Generate a timestamp string for file naming."""
        import datetime

        return datetime.datetime.fromtimestamp(time.time()).strftime("%Y%m%d-%H%M%S")

    @staticmethod
    def _encode_file_to_base64(path: str) -> str:
        """Encode a file to base64."""
        with open(path, "rb") as file:
            return base64.b64encode(file.read()).decode("utf-8")

    @staticmethod
    def _decode_and_save_base64(base64_str: str, save_path: str) -> None:
        """Decode base64 string and save to file."""
        with open(save_path, "wb") as file:
            file.write(base64.b64decode(base64_str))

    def _call_api(self, api_endpoint: str, **payload) -> Dict:
        """
        Make API call to Stable Diffusion API.

        Args:
            api_endpoint: API endpoint to call
            **payload: Payload data

        Returns:
            API response data
        """
        import urllib.request
        import urllib.error

        data = json.dumps(payload).encode("utf-8")
        url = f"{SD_API_URL}/{api_endpoint}"
        request = urllib.request.Request(
            url,
            headers={"Content-Type": "application/json"},
            data=data,
        )

        try:
            response = urllib.request.urlopen(request)
            return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            print(f"API call error: {e}")
            raise

    def _call_txt2img_api(self, **payload) -> Tuple[str, ImageInfo]:
        """
        Call text-to-image API and save the result.

        Args:
            **payload: Generation parameters

        Returns:
            Tuple of (file_path, image_info)
        """
        response = self._call_api("sdapi/v1/txt2img", **payload)
        info = json.loads(response.get("info", "{}"))

        image_info = ImageInfo(
            sampler_name=info.get("sampler_name", ""),
            steps=info.get("steps", 0),
            cfg_scale=info.get("cfg_scale", 0.0),
            width=info.get("width", 0),
            height=info.get("height", 0),
            seed=info.get("seed", 0),
        )

        # Save the first image
        images = response.get("images", [])
        if not images:
            raise ValueError("No images returned from API")

        save_path = os.path.join(self.out_dir_t2i, f"txt2img-{self._timestamp()}-0.png")
        self._decode_and_save_base64(images[0], save_path)

        return save_path, image_info

    async def gen_image(
        self,
        prompt: str,
        negative_prompt: Optional[str],
        seed: int = -1,
        width: int = 832,
        height: int = 1216,
        cfg_scale: float = 3.0,
        steps: int = 30,
        upscale: float = 1.0,
        allow_nsfw: bool = True,
    ) -> Tuple[str, ImageInfo, bool]:
        """
        Generate an image using Stable Diffusion.

        Args:
            prompt: Positive prompt for generation
            negative_prompt: Negative prompt
            seed: Random seed (-1 for random)
            width: Image width (capped at 1500)
            height: Image height (capped at 2000)
            cfg_scale: Classifier-free guidance scale
            steps: Number of generation steps
            upscale: Upscale factor
            allow_nsfw: Whether NSFW content is allowed

        Returns:
            Tuple of (file_path, image_info, is_nsfw)
        """
        # Clamp parameters to safe ranges
        width = min(1500, width)
        height = min(2000, height)
        steps = max(2, min(steps, 60))
        upscale = max(1.0, min(upscale, 2.0))
        cfg_scale = max(1.5, min(cfg_scale, 7.0))

        try:
            baseline_positive_prompt = ""
            baseline_negative_prompt = ""
            if not allow_nsfw:
                baseline_positive_prompt += "pg rated, safe for work, fully clothed, "

            # Remove any negative terms that appear in the positive prompt
            all_negatives = [
                item.strip() for item in baseline_negative_prompt.split(",")
            ]
            for negative in all_negatives:
                if negative and negative in prompt:
                    prompt = prompt.replace(negative, "")

            final_prompt = baseline_positive_prompt + prompt
            final_negative_prompt = baseline_negative_prompt + (negative_prompt or "")

            # API payload
            payload = {
                "prompt": final_prompt,
                "negative_prompt": final_negative_prompt,
                "seed": seed,
                "steps": steps,
                "width": width,
                "height": height,
                "cfg_scale": cfg_scale,
                "sampler_name": "Euler",
                "n_iter": 1,
                "batch_size": 1,
                "override_settings": {
                    "CLIP_stop_at_last_layers": 1,
                },
            }

            # Add upscaling if requested
            if upscale > 1.0:
                payload.update(
                    {
                        "enable_hr": True,
                        "hr_upscaler": "4x_foolhardy_Remacri",
                        "hr_scale": upscale,
                        "hr_sampler_name": "Euler",
                        "hr_second_pass_steps": steps,
                        "denoising_strength": 0.5,
                    }
                )

            # Add face enhancement
            payload["alwayson_scripts"] = {
                "ADetailer": {"args": [{"ad_model": "face_yolov8n.pt"}]}
            }

            file_path, image_info = self._call_txt2img_api(**payload)
            is_nsfw = await self.is_image_nsfw(file_path)

            return (file_path, image_info, is_nsfw)

        except Exception as e:
            print(f"Error generating image: {e}")
            traceback.print_exc()
            raise

    async def save_attachments(
        self, attachments: List[discord.Attachment]
    ) -> List[str]:
        """
        Save Discord attachments to the file input folder.

        Args:
            attachments: List of Discord attachment objects

        Returns:
            List of saved file paths
        """
        files = []
        os.makedirs(FILE_INPUT_FOLDER, exist_ok=True)

        for attachment in attachments:
            try:
                file_path = os.path.join(FILE_INPUT_FOLDER, attachment.filename)
                await attachment.save(file_path)
                files.append(file_path)
            except Exception as e:
                print(f"Error saving attachment {attachment.filename}: {e}")

        return files

    async def close(self):
        """Clean up resources when shutting down."""
        # Currently no persistent connections to close
        # This method is here for future cleanup needs
        pass
