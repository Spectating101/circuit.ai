"""
Stripe Integration for Circuit.AI

Complete billing system with:
- Subscription management
- Usage-based billing
- Invoice generation
- Payment webhooks
- Dunning management
- Customer portal
"""

import stripe
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from loguru import logger
from fastapi import HTTPException, status

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class SubscriptionTier:
    """Subscription tier definitions."""
    FREE = {
        "name": "Free",
        "price_monthly": 0,
        "analyses_per_month": 10,
        "features": ["basic_analysis", "10_analyses_month"],
        "stripe_price_id": None
    }

    PRO = {
        "name": "Pro",
        "price_monthly": 49,
        "analyses_per_month": 500,
        "features": [
            "basic_analysis",
            "advanced_analysis",
            "bom_generation",
            "3d_visualization",
            "priority_support",
            "500_analyses_month"
        ],
        "stripe_price_id": os.getenv("STRIPE_PRO_PRICE_ID")
    }

    ENTERPRISE = {
        "name": "Enterprise",
        "price_monthly": 499,
        "analyses_per_month": 10000,
        "features": [
            "basic_analysis",
            "advanced_analysis",
            "bom_generation",
            "3d_visualization",
            "schematic_generation",
            "video_analysis",
            "priority_support",
            "dedicated_support",
            "custom_training",
            "white_label",
            "unlimited_analyses"
        ],
        "stripe_price_id": os.getenv("STRIPE_ENTERPRISE_PRICE_ID")
    }


class StripeService:
    """Service for Stripe billing operations."""

    def __init__(self):
        """Initialize Stripe service."""
        self.api_key = stripe.api_key
        if not self.api_key or self.api_key.startswith("sk_test_"):
            logger.warning("⚠️ Stripe is in TEST mode or not configured!")

    async def create_customer(self,
                             email: str,
                             name: Optional[str] = None,
                             metadata: Optional[Dict[str, str]] = None) -> stripe.Customer:
        """
        Create a new Stripe customer.

        Args:
            email: Customer email
            name: Customer name
            metadata: Additional metadata

        Returns:
            Stripe Customer object
        """
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )

            logger.info(f"Created Stripe customer: {customer.id} ({email})")
            return customer

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe customer: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Payment provider error: {str(e)}"
            )

    async def create_subscription(self,
                                 customer_id: str,
                                 price_id: str,
                                 trial_days: int = 0,
                                 metadata: Optional[Dict[str, str]] = None) -> stripe.Subscription:
        """
        Create a subscription for a customer.

        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID
            trial_days: Trial period in days
            metadata: Additional metadata

        Returns:
            Stripe Subscription object
        """
        try:
            subscription_params = {
                "customer": customer_id,
                "items": [{"price": price_id}],
                "metadata": metadata or {},
                "payment_behavior": "default_incomplete",
                "payment_settings": {
                    "save_default_payment_method": "on_subscription"
                },
                "expand": ["latest_invoice.payment_intent"]
            }

            if trial_days > 0:
                subscription_params["trial_period_days"] = trial_days

            subscription = stripe.Subscription.create(**subscription_params)

            logger.info(f"Created subscription: {subscription.id} for customer {customer_id}")
            return subscription

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create subscription: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create subscription: {str(e)}"
            )

    async def cancel_subscription(self,
                                 subscription_id: str,
                                 immediately: bool = False) -> stripe.Subscription:
        """
        Cancel a subscription.

        Args:
            subscription_id: Stripe subscription ID
            immediately: Cancel immediately or at period end

        Returns:
            Updated Stripe Subscription object
        """
        try:
            if immediately:
                subscription = stripe.Subscription.delete(subscription_id)
            else:
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )

            logger.info(f"Cancelled subscription: {subscription_id} (immediate: {immediately})")
            return subscription

        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to cancel subscription: {str(e)}"
            )

    async def update_subscription(self,
                                 subscription_id: str,
                                 new_price_id: str,
                                 proration_behavior: str = "create_prorations") -> stripe.Subscription:
        """
        Update subscription to new plan.

        Args:
            subscription_id: Stripe subscription ID
            new_price_id: New price ID
            proration_behavior: How to handle prorations

        Returns:
            Updated Stripe Subscription object
        """
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)

            subscription = stripe.Subscription.modify(
                subscription_id,
                items=[{
                    "id": subscription["items"]["data"][0].id,
                    "price": new_price_id,
                }],
                proration_behavior=proration_behavior
            )

            logger.info(f"Updated subscription: {subscription_id} to price {new_price_id}")
            return subscription

        except stripe.error.StripeError as e:
            logger.error(f"Failed to update subscription: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update subscription: {str(e)}"
            )

    async def create_checkout_session(self,
                                     customer_id: str,
                                     price_id: str,
                                     success_url: str,
                                     cancel_url: str,
                                     trial_days: int = 0,
                                     metadata: Optional[Dict[str, str]] = None) -> stripe.checkout.Session:
        """
        Create Stripe Checkout session for subscription.

        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID
            success_url: Redirect URL on success
            cancel_url: Redirect URL on cancel
            trial_days: Trial period in days
            metadata: Additional metadata

        Returns:
            Stripe Checkout Session
        """
        try:
            session_params = {
                "customer": customer_id,
                "mode": "subscription",
                "line_items": [{
                    "price": price_id,
                    "quantity": 1,
                }],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": metadata or {},
                "subscription_data": {
                    "metadata": metadata or {}
                }
            }

            if trial_days > 0:
                session_params["subscription_data"]["trial_period_days"] = trial_days

            session = stripe.checkout.Session.create(**session_params)

            logger.info(f"Created checkout session: {session.id}")
            return session

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create checkout session: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create checkout session: {str(e)}"
            )

    async def create_billing_portal_session(self,
                                           customer_id: str,
                                           return_url: str) -> stripe.billing_portal.Session:
        """
        Create customer portal session for self-service billing.

        Args:
            customer_id: Stripe customer ID
            return_url: Return URL after portal session

        Returns:
            Billing Portal Session
        """
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )

            logger.info(f"Created billing portal session for customer: {customer_id}")
            return session

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create billing portal session: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create billing portal session: {str(e)}"
            )

    async def record_usage(self,
                          subscription_item_id: str,
                          quantity: int,
                          timestamp: Optional[int] = None,
                          action: str = "increment") -> stripe.UsageRecord:
        """
        Record usage for metered billing.

        Args:
            subscription_item_id: Subscription item ID
            quantity: Usage quantity
            timestamp: Usage timestamp (default: now)
            action: "increment" or "set"

        Returns:
            Usage Record
        """
        try:
            usage_record = stripe.SubscriptionItem.create_usage_record(
                subscription_item_id,
                quantity=quantity,
                timestamp=timestamp or int(datetime.now().timestamp()),
                action=action
            )

            logger.info(f"Recorded usage: {quantity} for item {subscription_item_id}")
            return usage_record

        except stripe.error.StripeError as e:
            logger.error(f"Failed to record usage: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to record usage: {str(e)}"
            )

    async def get_upcoming_invoice(self, customer_id: str) -> stripe.Invoice:
        """
        Get upcoming invoice for customer.

        Args:
            customer_id: Stripe customer ID

        Returns:
            Upcoming Invoice
        """
        try:
            invoice = stripe.Invoice.upcoming(customer=customer_id)
            return invoice

        except stripe.error.StripeError as e:
            logger.error(f"Failed to get upcoming invoice: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get upcoming invoice: {str(e)}"
            )

    async def handle_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """
        Handle Stripe webhook event.

        Args:
            payload: Raw webhook payload
            signature: Stripe signature header

        Returns:
            Event data
        """
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

        try:
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )

            logger.info(f"Received Stripe webhook: {event['type']}")

            # Handle different event types
            event_type = event["type"]
            event_data = event["data"]["object"]

            if event_type == "checkout.session.completed":
                return await self._handle_checkout_completed(event_data)
            elif event_type == "customer.subscription.created":
                return await self._handle_subscription_created(event_data)
            elif event_type == "customer.subscription.updated":
                return await self._handle_subscription_updated(event_data)
            elif event_type == "customer.subscription.deleted":
                return await self._handle_subscription_deleted(event_data)
            elif event_type == "invoice.payment_succeeded":
                return await self._handle_payment_succeeded(event_data)
            elif event_type == "invoice.payment_failed":
                return await self._handle_payment_failed(event_data)

            return {"status": "received", "type": event_type}

        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payload"
            )
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid signature"
            )

    async def _handle_checkout_completed(self, session: Dict) -> Dict[str, Any]:
        """Handle successful checkout."""
        logger.info(f"Checkout completed: {session['id']}")
        # TODO: Update database with subscription info
        return {"status": "checkout_completed"}

    async def _handle_subscription_created(self, subscription: Dict) -> Dict[str, Any]:
        """Handle subscription created."""
        logger.info(f"Subscription created: {subscription['id']}")
        # TODO: Update database
        return {"status": "subscription_created"}

    async def _handle_subscription_updated(self, subscription: Dict) -> Dict[str, Any]:
        """Handle subscription updated."""
        logger.info(f"Subscription updated: {subscription['id']}")
        # TODO: Update database
        return {"status": "subscription_updated"}

    async def _handle_subscription_deleted(self, subscription: Dict) -> Dict[str, Any]:
        """Handle subscription deleted."""
        logger.info(f"Subscription deleted: {subscription['id']}")
        # TODO: Update database
        return {"status": "subscription_deleted"}

    async def _handle_payment_succeeded(self, invoice: Dict) -> Dict[str, Any]:
        """Handle successful payment."""
        logger.info(f"Payment succeeded: {invoice['id']}")
        # TODO: Update database, send receipt email
        return {"status": "payment_succeeded"}

    async def _handle_payment_failed(self, invoice: Dict) -> Dict[str, Any]:
        """Handle failed payment."""
        logger.warning(f"Payment failed: {invoice['id']}")
        # TODO: Update database, send dunning email
        return {"status": "payment_failed"}


# Singleton instance
stripe_service = StripeService()
