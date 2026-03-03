import os
from typing import Any
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))
MODEL_ENGINE = os.getenv("IMAGE_MODEL_ENGINE", "gpt-4.1-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY is required. Create one at https://platform.openai.com/api-keys"
    )

client = OpenAI(api_key=OPENAI_API_KEY)


def get_image_analysis(content: list[dict[str, Any]]) -> str:
    processed_content: list[dict[str, Any]] = []

    for item in content:
        item_type = item.get("type")
        if item_type == "text":
            text = item.get("text", "")
            if text:
                processed_content.append({"type": "input_text", "text": text})
        elif item_type == "resource":
            mime_type = item.get("mime_type", "")
            image_b64 = item.get("contents", "")
            if not mime_type.startswith("image/"):
                return f"Unsupported mime type: {mime_type}"
            if not image_b64:
                return "Image content is empty."
            processed_content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{mime_type};base64,{image_b64}",
                }
            )
        elif item_type == "resource_url":
            image_url = item.get("url", "")
            if not image_url:
                return "Image URL is empty."
            processed_content.append(
                {
                    "type": "input_image",
                    "image_url": image_url,
                }
            )

    if not processed_content:
        return "Please send a text prompt and an image attachment."

    try:
        response = client.responses.create(
            model=MODEL_ENGINE,
            input=[{"role": "user", "content": processed_content}],
            max_output_tokens=MAX_TOKENS,
        )
        if response.output_text:
            return response.output_text
        return "I could not generate an analysis for this image."
    except Exception as err:
        return f"An error occurred while analyzing the image: {err}"
