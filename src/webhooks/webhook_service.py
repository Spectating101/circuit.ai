"""
Webhook System

Allow users to receive real-time notifications:
- Analysis complete
- BOM generated
- Payment events
- User events
- System events

Features:
- Retry with exponential backoff
- Signature verification
- Event filtering
- Delivery logs
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import asyncio
import aiohttp
import hashlib
import hmac
import json
from loguru import logger
from enum import Enum


class WebhookEvent(Enum):
    """Webhook event types."""
    ANALYSIS_STARTED = "analysis.started"
    ANALYSIS_COMPLETED = "analysis.completed"
    ANALYSIS_FAILED = "analysis.failed"

    BOM_GENERATED = "bom.generated"

    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"

    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_UPDATED = "subscription.updated"
    SUBSCRIPTION_CANCELED = "subscription.canceled"

    PAYMENT_SUCCEEDED = "payment.succeeded"
    PAYMENT_FAILED = "payment.failed"


@dataclass
class WebhookEndpoint:
    """Webhook endpoint configuration."""
    id: str
    organization_id: str
    url: str
    secret: str
    enabled: bool = True
    events: List[WebhookEvent] = None
    created_at: datetime = None

    # Delivery settings
    max_retries: int = 3
    retry_delay: int = 60  # seconds
    timeout: int = 30  # seconds


@dataclass
class WebhookDelivery:
    """Webhook delivery attempt."""
    id: str
    endpoint_id: str
    event_type: WebhookEvent
    payload: Dict[str, Any]
    attempt_number: int
    status: str  # "pending", "success", "failed"
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime = None


class WebhookService:
    """Service for managing and delivering webhooks."""

    def __init__(self):
        """Initialize webhook service."""
        self.delivery_queue = asyncio.Queue()
        logger.info("WebhookService initialized")

    async def create_endpoint(self,
                             organization_id: str,
                             url: str,
                             events: List[WebhookEvent],
                             secret: Optional[str] = None) -> WebhookEndpoint:
        """
        Create webhook endpoint.

        Args:
            organization_id: Organization ID
            url: Webhook URL
            events: List of events to subscribe to
            secret: Optional webhook secret

        Returns:
            WebhookEndpoint
        """
        if not secret:
            import secrets as sec
            secret = sec.token_urlsafe(32)

        endpoint = WebhookEndpoint(
            id=f"whep_{self._generate_id()}",
            organization_id=organization_id,
            url=url,
            secret=secret,
            events=events,
            created_at=datetime.now()
        )

        # TODO: Save to database

        logger.info(f"Created webhook endpoint: {endpoint.id} for {url}")
        return endpoint

    async def update_endpoint(self,
                             endpoint_id: str,
                             updates: Dict[str, Any]) -> WebhookEndpoint:
        """
        Update webhook endpoint.

        Args:
            endpoint_id: Endpoint ID
            updates: Fields to update

        Returns:
            Updated WebhookEndpoint
        """
        # TODO: Update in database
        logger.info(f"Updated webhook endpoint: {endpoint_id}")
        return None

    async def delete_endpoint(self, endpoint_id: str) -> bool:
        """
        Delete webhook endpoint.

        Args:
            endpoint_id: Endpoint ID

        Returns:
            Success status
        """
        # TODO: Delete from database
        logger.info(f"Deleted webhook endpoint: {endpoint_id}")
        return True

    async def trigger_event(self,
                           organization_id: str,
                           event_type: WebhookEvent,
                           payload: Dict[str, Any]):
        """
        Trigger webhook event for organization.

        Args:
            organization_id: Organization ID
            event_type: Event type
            payload: Event payload
        """
        # Get all endpoints for organization subscribed to this event
        endpoints = await self._get_endpoints_for_event(organization_id, event_type)

        logger.info(f"Triggering {event_type.value} for {len(endpoints)} endpoints")

        # Queue deliveries
        for endpoint in endpoints:
            delivery = WebhookDelivery(
                id=f"whdl_{self._generate_id()}",
                endpoint_id=endpoint.id,
                event_type=event_type,
                payload=payload,
                attempt_number=1,
                status="pending",
                created_at=datetime.now()
            )

            # Add to delivery queue
            await self.delivery_queue.put((endpoint, delivery))

    async def _get_endpoints_for_event(self,
                                       organization_id: str,
                                       event_type: WebhookEvent) -> List[WebhookEndpoint]:
        """Get webhook endpoints subscribed to event."""
        # TODO: Query from database
        return []

    async def deliver_webhook(self,
                             endpoint: WebhookEndpoint,
                             delivery: WebhookDelivery) -> WebhookDelivery:
        """
        Deliver webhook to endpoint.

        Args:
            endpoint: Webhook endpoint
            delivery: Delivery record

        Returns:
            Updated WebhookDelivery
        """
        # Prepare payload
        webhook_payload = {
            "id": delivery.id,
            "type": delivery.event_type.value,
            "created": int(delivery.created_at.timestamp()),
            "data": delivery.payload
        }

        # Generate signature
        signature = self._generate_signature(
            webhook_payload,
            endpoint.secret
        )

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-ID": delivery.id,
            "X-Webhook-Timestamp": str(int(delivery.created_at.timestamp())),
            "User-Agent": "CircuitAI-Webhooks/1.0"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint.url,
                    json=webhook_payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=endpoint.timeout)
                ) as response:
                    delivery.response_code = response.status
                    delivery.response_body = await response.text()

                    if 200 <= response.status < 300:
                        delivery.status = "success"
                        delivery.delivered_at = datetime.now()
                        logger.info(f"Webhook delivered successfully: {delivery.id}")
                    else:
                        delivery.status = "failed"
                        delivery.error_message = f"HTTP {response.status}"
                        logger.warning(f"Webhook delivery failed: {delivery.id} - HTTP {response.status}")

        except asyncio.TimeoutError:
            delivery.status = "failed"
            delivery.error_message = "Request timeout"
            logger.error(f"Webhook delivery timeout: {delivery.id}")

        except Exception as e:
            delivery.status = "failed"
            delivery.error_message = str(e)
            logger.error(f"Webhook delivery error: {delivery.id} - {e}")

        # TODO: Save delivery to database

        # Retry if failed
        if delivery.status == "failed" and delivery.attempt_number < endpoint.max_retries:
            await self._schedule_retry(endpoint, delivery)

        return delivery

    async def _schedule_retry(self,
                              endpoint: WebhookEndpoint,
                              delivery: WebhookDelivery):
        """
        Schedule webhook retry with exponential backoff.

        Args:
            endpoint: Webhook endpoint
            delivery: Delivery record
        """
        delay = endpoint.retry_delay * (2 ** (delivery.attempt_number - 1))

        logger.info(f"Scheduling retry for {delivery.id} in {delay}s (attempt {delivery.attempt_number + 1})")

        await asyncio.sleep(delay)

        # Create new delivery attempt
        retry_delivery = WebhookDelivery(
            id=delivery.id,
            endpoint_id=delivery.endpoint_id,
            event_type=delivery.event_type,
            payload=delivery.payload,
            attempt_number=delivery.attempt_number + 1,
            status="pending",
            created_at=datetime.now()
        )

        await self.delivery_queue.put((endpoint, retry_delivery))

    def _generate_signature(self, payload: Dict[str, Any], secret: str) -> str:
        """
        Generate webhook signature for verification.

        Args:
            payload: Webhook payload
            secret: Webhook secret

        Returns:
            HMAC signature
        """
        payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()

        return signature

    def verify_signature(self,
                        payload: Dict[str, Any],
                        signature: str,
                        secret: str) -> bool:
        """
        Verify webhook signature.

        Args:
            payload: Webhook payload
            signature: Provided signature
            secret: Webhook secret

        Returns:
            True if valid
        """
        expected_signature = self._generate_signature(payload, secret)
        return hmac.compare_digest(signature, expected_signature)

    async def get_delivery_logs(self,
                                endpoint_id: str,
                                limit: int = 100) -> List[WebhookDelivery]:
        """
        Get delivery logs for endpoint.

        Args:
            endpoint_id: Endpoint ID
            limit: Max number of logs

        Returns:
            List of WebhookDelivery records
        """
        # TODO: Query from database
        return []

    async def start_delivery_worker(self):
        """Start background worker for webhook delivery."""
        logger.info("Starting webhook delivery worker")

        while True:
            try:
                endpoint, delivery = await self.delivery_queue.get()
                await self.deliver_webhook(endpoint, delivery)
                self.delivery_queue.task_done()

            except Exception as e:
                logger.error(f"Webhook delivery worker error: {e}")
                await asyncio.sleep(1)

    def _generate_id(self) -> str:
        """Generate unique ID."""
        import secrets
        return secrets.token_urlsafe(16)


# Singleton instance
webhook_service = WebhookService()
