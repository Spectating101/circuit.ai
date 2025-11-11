"""
Messaging Platform Integrations

Integrates with:
- Slack
- Discord
- Microsoft Teams
- Telegram

Features:
- Analysis notifications
- Interactive bot commands
- File uploads
- Threaded discussions
- Slash commands
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import aiohttp
import asyncio
from loguru import logger
import hmac
import hashlib
import json
from enum import Enum


class PlatformType(Enum):
    """Messaging platform types."""
    SLACK = "slack"
    DISCORD = "discord"
    TEAMS = "teams"
    TELEGRAM = "telegram"


@dataclass
class MessageAttachment:
    """Message attachment."""
    title: str
    text: str
    color: str  # Hex color
    fields: List[Dict[str, Any]]
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None


class SlackIntegration:
    """Slack integration."""

    def __init__(self, bot_token: str, signing_secret: str):
        """
        Initialize Slack integration.

        Args:
            bot_token: Slack bot token
            signing_secret: Slack signing secret for webhook verification
        """
        self.bot_token = bot_token
        self.signing_secret = signing_secret
        self.api_base = "https://slack.com/api"
        logger.info("SlackIntegration initialized")

    async def send_message(
        self,
        channel: str,
        text: str,
        attachments: Optional[List[MessageAttachment]] = None,
        thread_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send message to Slack channel.

        Args:
            channel: Channel ID or name
            text: Message text
            attachments: Message attachments
            thread_ts: Thread timestamp for replies

        Returns:
            Slack API response
        """
        payload = {
            "channel": channel,
            "text": text
        }

        if attachments:
            payload["attachments"] = [
                {
                    "title": att.title,
                    "text": att.text,
                    "color": att.color,
                    "fields": att.fields,
                    "image_url": att.image_url,
                    "thumb_url": att.thumbnail_url
                }
                for att in attachments
            ]

        if thread_ts:
            payload["thread_ts"] = thread_ts

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_base}/chat.postMessage",
                headers={"Authorization": f"Bearer {self.bot_token}"},
                json=payload
            ) as response:
                result = await response.json()

                if not result.get("ok"):
                    logger.error(f"Slack API error: {result.get('error')}")

                return result

    async def upload_file(
        self,
        channel: str,
        file_content: bytes,
        filename: str,
        title: Optional[str] = None,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload file to Slack channel.

        Args:
            channel: Channel ID
            file_content: File bytes
            filename: Filename
            title: File title
            comment: Initial comment

        Returns:
            Slack API response
        """
        data = aiohttp.FormData()
        data.add_field("channels", channel)
        data.add_field("filename", filename)
        data.add_field("file", file_content, filename=filename)

        if title:
            data.add_field("title", title)
        if comment:
            data.add_field("initial_comment", comment)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_base}/files.upload",
                headers={"Authorization": f"Bearer {self.bot_token}"},
                data=data
            ) as response:
                return await response.json()

    async def notify_analysis_complete(
        self,
        channel: str,
        pcb_name: str,
        analysis_id: str,
        component_count: int,
        processing_time: float,
        result_url: str,
        image_url: Optional[str] = None
    ):
        """
        Send analysis completion notification.

        Args:
            channel: Slack channel
            pcb_name: PCB name
            analysis_id: Analysis ID
            component_count: Number of components detected
            processing_time: Processing time in seconds
            result_url: URL to results
            image_url: PCB image URL
        """
        attachment = MessageAttachment(
            title=f"✅ Analysis Complete: {pcb_name}",
            text=f"PCB analysis finished successfully!",
            color="#36a64f",  # Green
            fields=[
                {"title": "Components Detected", "value": str(component_count), "short": True},
                {"title": "Processing Time", "value": f"{processing_time:.2f}s", "short": True},
                {"title": "Analysis ID", "value": analysis_id, "short": False},
                {"title": "View Results", "value": f"<{result_url}|Open Dashboard>", "short": False}
            ],
            image_url=image_url
        )

        await self.send_message(
            channel=channel,
            text=f"Analysis complete for {pcb_name}",
            attachments=[attachment]
        )

    async def create_interactive_message(
        self,
        channel: str,
        text: str,
        actions: List[Dict[str, Any]]
    ):
        """
        Create interactive message with buttons.

        Args:
            channel: Channel ID
            text: Message text
            actions: List of button actions
        """
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text}
            },
            {
                "type": "actions",
                "elements": actions
            }
        ]

        payload = {
            "channel": channel,
            "blocks": blocks
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_base}/chat.postMessage",
                headers={"Authorization": f"Bearer {self.bot_token}"},
                json=payload
            ) as response:
                return await response.json()

    def verify_webhook_signature(
        self,
        timestamp: str,
        signature: str,
        body: bytes
    ) -> bool:
        """
        Verify Slack webhook signature.

        Args:
            timestamp: Request timestamp
            signature: Request signature
            body: Request body

        Returns:
            True if valid
        """
        sig_basestring = f"v0:{timestamp}:{body.decode()}"
        my_signature = 'v0=' + hmac.new(
            self.signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(my_signature, signature)


class DiscordIntegration:
    """Discord integration."""

    def __init__(self, webhook_url: str, bot_token: Optional[str] = None):
        """
        Initialize Discord integration.

        Args:
            webhook_url: Discord webhook URL
            bot_token: Discord bot token (for advanced features)
        """
        self.webhook_url = webhook_url
        self.bot_token = bot_token
        logger.info("DiscordIntegration initialized")

    async def send_message(
        self,
        content: str,
        embed: Optional[Dict[str, Any]] = None,
        username: Optional[str] = None,
        avatar_url: Optional[str] = None
    ):
        """
        Send message via Discord webhook.

        Args:
            content: Message content
            embed: Rich embed
            username: Override username
            avatar_url: Override avatar
        """
        payload = {"content": content}

        if embed:
            payload["embeds"] = [embed]
        if username:
            payload["username"] = username
        if avatar_url:
            payload["avatar_url"] = avatar_url

        async with aiohttp.ClientSession() as session:
            async with session.post(self.webhook_url, json=payload) as response:
                if response.status != 204:
                    logger.error(f"Discord webhook error: {response.status}")

    async def notify_analysis_complete(
        self,
        pcb_name: str,
        analysis_id: str,
        component_count: int,
        processing_time: float,
        result_url: str,
        image_url: Optional[str] = None
    ):
        """Send analysis completion notification to Discord."""
        embed = {
            "title": f"✅ Analysis Complete: {pcb_name}",
            "description": "PCB analysis finished successfully!",
            "color": 0x36a64f,  # Green
            "fields": [
                {"name": "Components Detected", "value": str(component_count), "inline": True},
                {"name": "Processing Time", "value": f"{processing_time:.2f}s", "inline": True},
                {"name": "Analysis ID", "value": analysis_id, "inline": False}
            ],
            "url": result_url,
            "thumbnail": {"url": image_url} if image_url else None,
            "footer": {"text": "Circuit.AI PCB Analysis"},
            "timestamp": "2025-11-11T12:00:00.000Z"
        }

        await self.send_message(
            content=f"Analysis complete for **{pcb_name}**",
            embed=embed,
            username="Circuit.AI Bot"
        )


class TeamsIntegration:
    """Microsoft Teams integration."""

    def __init__(self, webhook_url: str):
        """
        Initialize Teams integration.

        Args:
            webhook_url: Teams incoming webhook URL
        """
        self.webhook_url = webhook_url
        logger.info("TeamsIntegration initialized")

    async def send_message(
        self,
        title: str,
        text: str,
        facts: Optional[List[Dict[str, str]]] = None,
        actions: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Send Adaptive Card to Teams.

        Args:
            title: Card title
            text: Card text
            facts: List of facts (name/value pairs)
            actions: List of actions/buttons
        """
        card = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": title,
            "themeColor": "0078D7",
            "title": title,
            "text": text
        }

        if facts:
            card["sections"] = [{
                "facts": facts
            }]

        if actions:
            card["potentialAction"] = actions

        async with aiohttp.ClientSession() as session:
            async with session.post(self.webhook_url, json=card) as response:
                if response.status != 200:
                    logger.error(f"Teams webhook error: {response.status}")

    async def notify_analysis_complete(
        self,
        pcb_name: str,
        analysis_id: str,
        component_count: int,
        processing_time: float,
        result_url: str
    ):
        """Send analysis completion notification to Teams."""
        facts = [
            {"name": "PCB Name", "value": pcb_name},
            {"name": "Components Detected", "value": str(component_count)},
            {"name": "Processing Time", "value": f"{processing_time:.2f}s"},
            {"name": "Analysis ID", "value": analysis_id}
        ]

        actions = [
            {
                "@type": "OpenUri",
                "name": "View Results",
                "targets": [
                    {"os": "default", "uri": result_url}
                ]
            }
        ]

        await self.send_message(
            title=f"✅ Analysis Complete: {pcb_name}",
            text="PCB analysis finished successfully! Click below to view results.",
            facts=facts,
            actions=actions
        )


class TelegramIntegration:
    """Telegram integration."""

    def __init__(self, bot_token: str):
        """
        Initialize Telegram integration.

        Args:
            bot_token: Telegram bot token
        """
        self.bot_token = bot_token
        self.api_base = f"https://api.telegram.org/bot{bot_token}"
        logger.info("TelegramIntegration initialized")

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False
    ):
        """
        Send message to Telegram chat.

        Args:
            chat_id: Chat ID
            text: Message text
            parse_mode: Parse mode (HTML/Markdown)
            disable_notification: Disable notification
        """
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_base}/sendMessage",
                json=payload
            ) as response:
                return await response.json()

    async def send_photo(
        self,
        chat_id: str,
        photo_url: str,
        caption: Optional[str] = None
    ):
        """
        Send photo to Telegram chat.

        Args:
            chat_id: Chat ID
            photo_url: Photo URL
            caption: Photo caption
        """
        payload = {
            "chat_id": chat_id,
            "photo": photo_url
        }

        if caption:
            payload["caption"] = caption

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_base}/sendPhoto",
                json=payload
            ) as response:
                return await response.json()

    async def notify_analysis_complete(
        self,
        chat_id: str,
        pcb_name: str,
        analysis_id: str,
        component_count: int,
        processing_time: float,
        result_url: str,
        image_url: Optional[str] = None
    ):
        """Send analysis completion notification to Telegram."""
        message = f"""
<b>✅ Analysis Complete: {pcb_name}</b>

📊 <b>Components Detected:</b> {component_count}
⏱ <b>Processing Time:</b> {processing_time:.2f}s
🔑 <b>Analysis ID:</b> <code>{analysis_id}</code>

<a href="{result_url}">View Full Results →</a>
        """.strip()

        if image_url:
            await self.send_photo(chat_id, image_url, caption=message)
        else:
            await self.send_message(chat_id, message)


class MessagingPlatformManager:
    """Manages all messaging platform integrations."""

    def __init__(self):
        """Initialize messaging platform manager."""
        self.integrations: Dict[PlatformType, Any] = {}
        logger.info("MessagingPlatformManager initialized")

    def register_slack(self, bot_token: str, signing_secret: str):
        """Register Slack integration."""
        self.integrations[PlatformType.SLACK] = SlackIntegration(
            bot_token, signing_secret
        )
        logger.info("Slack integration registered")

    def register_discord(self, webhook_url: str):
        """Register Discord integration."""
        self.integrations[PlatformType.DISCORD] = DiscordIntegration(webhook_url)
        logger.info("Discord integration registered")

    def register_teams(self, webhook_url: str):
        """Register Teams integration."""
        self.integrations[PlatformType.TEAMS] = TeamsIntegration(webhook_url)
        logger.info("Teams integration registered")

    def register_telegram(self, bot_token: str):
        """Register Telegram integration."""
        self.integrations[PlatformType.TELEGRAM] = TelegramIntegration(bot_token)
        logger.info("Telegram integration registered")

    async def broadcast_analysis_complete(
        self,
        platforms: List[PlatformType],
        pcb_name: str,
        analysis_id: str,
        component_count: int,
        processing_time: float,
        result_url: str,
        image_url: Optional[str] = None,
        **platform_specific: Dict[str, Any]
    ):
        """
        Broadcast analysis completion to multiple platforms.

        Args:
            platforms: Platforms to notify
            pcb_name: PCB name
            analysis_id: Analysis ID
            component_count: Component count
            processing_time: Processing time
            result_url: Result URL
            image_url: Image URL
            platform_specific: Platform-specific parameters (e.g., slack_channel, telegram_chat_id)
        """
        tasks = []

        for platform in platforms:
            integration = self.integrations.get(platform)

            if not integration:
                logger.warning(f"{platform.value} integration not configured")
                continue

            if platform == PlatformType.SLACK:
                channel = platform_specific.get('slack_channel', '#general')
                tasks.append(integration.notify_analysis_complete(
                    channel=channel,
                    pcb_name=pcb_name,
                    analysis_id=analysis_id,
                    component_count=component_count,
                    processing_time=processing_time,
                    result_url=result_url,
                    image_url=image_url
                ))

            elif platform == PlatformType.DISCORD:
                tasks.append(integration.notify_analysis_complete(
                    pcb_name=pcb_name,
                    analysis_id=analysis_id,
                    component_count=component_count,
                    processing_time=processing_time,
                    result_url=result_url,
                    image_url=image_url
                ))

            elif platform == PlatformType.TEAMS:
                tasks.append(integration.notify_analysis_complete(
                    pcb_name=pcb_name,
                    analysis_id=analysis_id,
                    component_count=component_count,
                    processing_time=processing_time,
                    result_url=result_url
                ))

            elif platform == PlatformType.TELEGRAM:
                chat_id = platform_specific.get('telegram_chat_id')
                if chat_id:
                    tasks.append(integration.notify_analysis_complete(
                        chat_id=chat_id,
                        pcb_name=pcb_name,
                        analysis_id=analysis_id,
                        component_count=component_count,
                        processing_time=processing_time,
                        result_url=result_url,
                        image_url=image_url
                    ))

        # Execute all notifications in parallel
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(f"Broadcast complete to {len(tasks)} platforms")


# Singleton instance
messaging_manager = MessagingPlatformManager()
