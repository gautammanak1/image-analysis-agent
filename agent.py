from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    MetadataContent,
    ResourceContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from image_analysis import get_image_analysis

agent = Agent(
    name="image-analysis-agent",
    seed="image-analysis-agent",
    port=8000,
    mailbox=True,
    handle_messages_concurrently=True,
)
chat_proto = Protocol(spec=chat_protocol_spec)


def create_text_chat(text: str) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=text)],
    )


def create_metadata_chat(metadata: dict[str, str]) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[MetadataContent(type="metadata", metadata=metadata)],
    )


def extract_image_url(item: ResourceContent) -> str | None:
    resources = item.resource if isinstance(item.resource, list) else [item.resource]
    for resource in resources:
        uri = getattr(resource, "uri", None)
        if isinstance(uri, str):
            parsed = urlparse(uri)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                return uri

        metadata = getattr(resource, "metadata", None) or {}
        if isinstance(metadata, dict):
            for key in ("url", "uri", "source", "image_url"):
                candidate = metadata.get(key)
                if isinstance(candidate, str):
                    parsed = urlparse(candidate)
                    if parsed.scheme in {"http", "https"} and parsed.netloc:
                        return candidate
    return None


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    ctx.logger.info("Got a message from %s", sender)

    await ctx.send(
        sender,
        ChatAcknowledgement(
            acknowledged_msg_id=msg.msg_id,
            timestamp=datetime.now(timezone.utc),
        ),
    )

    prompt_content: list[dict[str, str]] = []

    for item in msg.content:
        if isinstance(item, StartSessionContent):
            ctx.logger.info("Got a start session message from %s", sender)
            await ctx.send(sender, create_metadata_chat({"attachments": "true"}))
        elif isinstance(item, TextContent):
            ctx.logger.info("Got text content from %s: %s", sender, item.text)
            prompt_content.append({"type": "text", "text": item.text})
        elif isinstance(item, ResourceContent):
            ctx.logger.info("Got resource content from %s", sender)
            image_url = extract_image_url(item)
            if not image_url:
                await ctx.send(
                    sender,
                    create_text_chat(
                        "Attachment URL not found. Please re-upload the image and try again."
                    ),
                )
                return
            ctx.logger.info("Using image URL=%s", image_url)
            prompt_content.append({"type": "resource_url", "url": image_url})

    if not prompt_content:
        await ctx.send(
            sender, create_text_chat("Please send a question and attach an image.")
        )
        return

    try:
        response = get_image_analysis(prompt_content)
        await ctx.send(sender, create_text_chat(response))
    except Exception as err:
        ctx.logger.error("Image analysis error: %s", err)
        await ctx.send(
            sender,
            create_text_chat("Sorry, I couldn't analyze the image. Please try again later."),
        )


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(
        "Got an acknowledgement from %s for %s", sender, msg.acknowledged_msg_id
    )


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
