"""
Webhook Service (Database-backed)

Production-grade webhook delivery system with:
- Database persistence
- Automatic retries with exponential backoff
- HMAC signature verification
- Delivery tracking
- Event filtering
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import uuid
import asyncio
import aiohttp
from loguru import logger
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import db_manager
from src.models.webhook_models import (
    Webhook, WebhookDelivery, WebhookAttempt, WebhookEvent,
    WebhookStatus, DeliveryStatus
)


class WebhookServiceV2:
    """Production webhook service with database persistence."""

    def __init__(self):
        """Initialize webhook service."""
        self.db_manager = db_manager
        self.default_timeout = 30  # seconds
        logger.info("WebhookServiceV2 initialized with database backend")

    async def register_webhook(
        self,
        user_id: str,
        url: str,
        events: List[str],
        secret: Optional[str] = None,
        organization_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> str:
        """
        Register a new webhook.

        Args:
            user_id: User ID
            url: Webhook URL
            events: List of event patterns to subscribe to
            secret: Webhook secret (generated if not provided)
            organization_id: Organization ID (for multi-tenancy)
            description: Webhook description

        Returns:
            Webhook ID
        """
        async with self.db_manager.session() as session:
            webhook_id = str(uuid.uuid4())
            webhook_secret = secret or self._generate_secret()

            webhook = Webhook(
                id=webhook_id,
                user_id=user_id,
                organization_id=organization_id,
                url=url,
                secret=webhook_secret,
                description=description,
                events=events,
                status=WebhookStatus.ACTIVE,
                is_active=True
            )

            session.add(webhook)
            await session.commit()

            logger.info(f"Registered webhook {webhook_id} for user {user_id}: {url}")
            return webhook_id

    async def update_webhook(
        self,
        webhook_id: str,
        url: Optional[str] = None,
        events: Optional[List[str]] = None,
        status: Optional[WebhookStatus] = None
    ) -> bool:
        """
        Update webhook configuration.

        Args:
            webhook_id: Webhook ID
            url: New URL
            events: New event list
            status: New status

        Returns:
            Success status
        """
        async with self.db_manager.session() as session:
            result = await session.execute(
                select(Webhook).where(Webhook.id == webhook_id)
            )
            webhook = result.scalar_one_or_none()

            if not webhook:
                logger.warning(f"Webhook {webhook_id} not found")
                return False

            if url:
                webhook.url = url
            if events is not None:
                webhook.events = events
            if status:
                webhook.status = status
                webhook.is_active = (status == WebhookStatus.ACTIVE)

            webhook.updated_at = datetime.utcnow()
            await session.commit()

            logger.info(f"Updated webhook {webhook_id}")
            return True

    async def delete_webhook(self, webhook_id: str) -> bool:
        """
        Delete a webhook.

        Args:
            webhook_id: Webhook ID

        Returns:
            Success status
        """
        async with self.db_manager.session() as session:
            result = await session.execute(
                select(Webhook).where(Webhook.id == webhook_id)
            )
            webhook = result.scalar_one_or_none()

            if not webhook:
                logger.warning(f"Webhook {webhook_id} not found")
                return False

            await session.delete(webhook)
            await session.commit()

            logger.info(f"Deleted webhook {webhook_id}")
            return True

    async def trigger_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None
    ):
        """
        Trigger webhook event.

        Args:
            event_type: Event type (e.g., "analysis.completed")
            payload: Event payload
            user_id: User ID (for filtering)
            organization_id: Organization ID (for filtering)
        """
        async with self.db_manager.session() as session:
            # Find matching webhooks
            query = select(Webhook).where(
                and_(
                    Webhook.is_active == True,
                    Webhook.status == WebhookStatus.ACTIVE
                )
            )

            # Filter by user/org
            if organization_id:
                query = query.where(Webhook.organization_id == organization_id)
            elif user_id:
                query = query.where(Webhook.user_id == user_id)

            result = await session.execute(query)
            webhooks = result.scalars().all()

            # Filter by event subscription
            matching_webhooks = [
                w for w in webhooks
                if self._matches_event_filter(event_type, w.events)
            ]

            logger.info(f"Triggering {event_type} for {len(matching_webhooks)} webhooks")

            # Create delivery records
            event_id = str(uuid.uuid4())
            for webhook in matching_webhooks:
                delivery = WebhookDelivery(
                    id=str(uuid.uuid4()),
                    webhook_id=webhook.id,
                    event_type=event_type,
                    event_id=event_id,
                    payload=payload,
                    status=DeliveryStatus.PENDING,
                    attempts=0
                )
                session.add(delivery)

            await session.commit()

            # Schedule deliveries (async, non-blocking)
            for webhook in matching_webhooks:
                asyncio.create_task(self._deliver_webhook(webhook.id, event_id))

    def _matches_event_filter(self, event_type: str, subscribed_events: List[str]) -> bool:
        """Check if event matches subscription filter."""
        if not subscribed_events:
            return True  # Subscribe to all events

        for pattern in subscribed_events:
            # Support wildcards like "analysis.*"
            if pattern.endswith(".*"):
                prefix = pattern[:-2]
                if event_type.startswith(prefix):
                    return True
            elif pattern == "*":
                return True
            elif pattern == event_type:
                return True

        return False

    async def _deliver_webhook(self, webhook_id: str, event_id: str):
        """
        Deliver webhook (with retries).

        Args:
            webhook_id: Webhook ID
            event_id: Event ID
        """
        async with self.db_manager.session() as session:
            # Get webhook
            webhook_result = await session.execute(
                select(Webhook).where(Webhook.id == webhook_id)
            )
            webhook = webhook_result.scalar_one_or_none()

            if not webhook:
                logger.error(f"Webhook {webhook_id} not found for delivery")
                return

            # Get delivery
            delivery_result = await session.execute(
                select(WebhookDelivery).where(
                    and_(
                        WebhookDelivery.webhook_id == webhook_id,
                        WebhookDelivery.event_id == event_id
                    )
                )
            )
            delivery = delivery_result.scalar_one_or_none()

            if not delivery:
                logger.error(f"Delivery not found for webhook {webhook_id}, event {event_id}")
                return

            # Prepare payload
            webhook_payload = {
                "event_type": delivery.event_type,
                "event_id": delivery.event_id,
                "timestamp": datetime.utcnow().isoformat(),
                "data": delivery.payload
            }

            # Generate signature
            signature = self._generate_signature(webhook_payload, webhook.secret)

            # Attempt delivery with retries
            max_attempts = webhook.max_retries + 1
            for attempt_num in range(1, max_attempts + 1):
                delivery.attempts = attempt_num
                delivery.status = DeliveryStatus.RETRYING if attempt_num > 1 else DeliveryStatus.PENDING

                attempt = WebhookAttempt(
                    id=str(uuid.uuid4()),
                    delivery_id=delivery.id,
                    attempt_number=attempt_num,
                    started_at=datetime.utcnow(),
                    request_url=webhook.url
                )
                session.add(attempt)
                await session.commit()

                # Make HTTP request
                success, status_code, response_body, error = await self._make_http_request(
                    url=webhook.url,
                    payload=webhook_payload,
                    signature=signature,
                    timeout=self.default_timeout
                )

                # Update attempt
                attempt.completed_at = datetime.utcnow()
                attempt.duration_ms = int((attempt.completed_at - attempt.started_at).total_seconds() * 1000)
                attempt.response_status_code = status_code
                attempt.response_body = response_body[:10000] if response_body else None  # Limit size
                attempt.success = success
                attempt.error_message = error

                if success:
                    delivery.status = DeliveryStatus.SUCCESS
                    delivery.delivered_at = datetime.utcnow()
                    delivery.response_status_code = status_code
                    delivery.response_body = response_body[:10000] if response_body else None

                    webhook.successful_deliveries += 1
                    webhook.last_success_at = datetime.utcnow()

                    await session.commit()
                    logger.info(f"Webhook {webhook_id} delivered successfully on attempt {attempt_num}")
                    return

                # Failed, check if we should retry
                if attempt_num < max_attempts:
                    delay = webhook.retry_delay_seconds * (2 ** (attempt_num - 1))  # Exponential backoff
                    delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
                    await session.commit()

                    logger.warning(f"Webhook {webhook_id} delivery failed (attempt {attempt_num}), retrying in {delay}s")
                    await asyncio.sleep(delay)
                else:
                    # All attempts failed
                    delivery.status = DeliveryStatus.FAILED
                    delivery.error_message = error

                    webhook.failed_deliveries += 1
                    webhook.last_failure_at = datetime.utcnow()

                    await session.commit()
                    logger.error(f"Webhook {webhook_id} delivery failed after {max_attempts} attempts")

    async def _make_http_request(
        self,
        url: str,
        payload: Dict,
        signature: str,
        timeout: int
    ) -> tuple[bool, Optional[int], Optional[str], Optional[str]]:
        """
        Make HTTP request to webhook URL.

        Returns:
            Tuple of (success, status_code, response_body, error_message)
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
                "User-Agent": "Circuit.AI-Webhooks/1.0"
            }

            async with aiohttp.ClientSession() as http_session:
                async with http_session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    status_code = response.status
                    response_body = await response.text()

                    success = 200 <= status_code < 300
                    return success, status_code, response_body, None

        except asyncio.TimeoutError:
            return False, None, None, "Request timeout"
        except aiohttp.ClientError as e:
            return False, None, None, f"HTTP error: {str(e)}"
        except Exception as e:
            return False, None, None, f"Unexpected error: {str(e)}"

    def _generate_signature(self, payload: Dict, secret: str) -> str:
        """
        Generate HMAC signature for payload.

        Args:
            payload: Payload dict
            secret: Webhook secret

        Returns:
            HMAC signature (hex)
        """
        payload_str = json.dumps(payload, sort_keys=True)
        return hmac.new(
            secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()

    def _generate_secret(self) -> str:
        """Generate random webhook secret."""
        return hashlib.sha256(uuid.uuid4().bytes).hexdigest()

    async def get_webhook_stats(self, webhook_id: str) -> Dict[str, Any]:
        """
        Get webhook delivery statistics.

        Args:
            webhook_id: Webhook ID

        Returns:
            Statistics dict
        """
        async with self.db_manager.session() as session:
            result = await session.execute(
                select(Webhook).where(Webhook.id == webhook_id)
            )
            webhook = result.scalar_one_or_none()

            if not webhook:
                return {}

            # Get recent deliveries
            deliveries_result = await session.execute(
                select(WebhookDelivery)
                .where(WebhookDelivery.webhook_id == webhook_id)
                .order_by(desc(WebhookDelivery.created_at))
                .limit(100)
            )
            deliveries = deliveries_result.scalars().all()

            success_count = sum(1 for d in deliveries if d.status == DeliveryStatus.SUCCESS)
            failed_count = sum(1 for d in deliveries if d.status == DeliveryStatus.FAILED)

            return {
                "webhook_id": webhook.id,
                "url": webhook.url,
                "status": webhook.status.value,
                "total_deliveries": webhook.total_deliveries,
                "successful_deliveries": webhook.successful_deliveries,
                "failed_deliveries": webhook.failed_deliveries,
                "success_rate": (webhook.successful_deliveries / webhook.total_deliveries * 100)
                    if webhook.total_deliveries > 0 else 0.0,
                "last_delivery_at": webhook.last_delivery_at.isoformat() if webhook.last_delivery_at else None,
                "last_success_at": webhook.last_success_at.isoformat() if webhook.last_success_at else None,
                "last_failure_at": webhook.last_failure_at.isoformat() if webhook.last_failure_at else None,
                "recent_deliveries": {
                    "success": success_count,
                    "failed": failed_count
                }
            }

    async def get_delivery_history(
        self,
        webhook_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get webhook delivery history.

        Args:
            webhook_id: Webhook ID
            limit: Maximum number of deliveries to return

        Returns:
            List of delivery records
        """
        async with self.db_manager.session() as session:
            result = await session.execute(
                select(WebhookDelivery)
                .where(WebhookDelivery.webhook_id == webhook_id)
                .order_by(desc(WebhookDelivery.created_at))
                .limit(limit)
            )
            deliveries = result.scalars().all()

            return [
                {
                    "id": d.id,
                    "event_type": d.event_type,
                    "status": d.status.value,
                    "attempts": d.attempts,
                    "created_at": d.created_at.isoformat(),
                    "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
                    "response_status_code": d.response_status_code,
                    "error_message": d.error_message
                }
                for d in deliveries
            ]


# Singleton instance
webhook_service_v2 = WebhookServiceV2()
