"""
Usage-Based Metered Billing with Stripe

Tracks and bills for:
- API calls
- Analysis jobs
- Component detections
- AI recommendations
- Storage usage
- Bandwidth
- Collaboration minutes
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import stripe
from loguru import logger
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class MeterType(Enum):
    """Metered resource types."""
    API_CALLS = "api_calls"
    ANALYSES = "analyses"
    COMPONENTS_DETECTED = "components_detected"
    AI_RECOMMENDATIONS = "ai_recommendations"
    STORAGE_GB = "storage_gb"
    BANDWIDTH_GB = "bandwidth_gb"
    COLLABORATION_MINUTES = "collaboration_minutes"
    PLUGIN_EXECUTIONS = "plugin_executions"
    WEBHOOKS_SENT = "webhooks_sent"


@dataclass
class UsageRecord:
    """Usage record for metered billing."""
    user_id: str
    meter_type: MeterType
    quantity: float
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PricingTier:
    """Pricing tier for graduated pricing."""
    up_to: Optional[int]  # None = unlimited
    unit_price: float
    flat_fee: float


class UsageMetricsDB(Base):
    """Database model for usage metrics."""
    __tablename__ = 'usage_metrics'

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    organization_id = Column(String(36), index=True)
    meter_type = Column(String(50), nullable=False)
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float)
    total_cost = Column(Float)
    timestamp = Column(DateTime, nullable=False, index=True)
    billing_period_start = Column(DateTime, nullable=False, index=True)
    billing_period_end = Column(DateTime, nullable=False)
    invoiced = Column(Boolean, default=False)
    invoice_id = Column(String(255))
    metadata = Column(String)  # JSON


class MeteredBillingService:
    """Metered billing service with Stripe integration."""

    def __init__(self, stripe_api_key: str):
        """
        Initialize metered billing service.

        Args:
            stripe_api_key: Stripe secret key
        """
        stripe.api_key = stripe_api_key
        self.pricing = self._initialize_pricing()
        logger.info("MeteredBillingService initialized")

    def _initialize_pricing(self) -> Dict[MeterType, List[PricingTier]]:
        """
        Initialize pricing tiers for each meter type.

        Returns:
            Pricing configuration
        """
        return {
            MeterType.API_CALLS: [
                PricingTier(up_to=10000, unit_price=0.0, flat_fee=0.0),  # Free tier
                PricingTier(up_to=100000, unit_price=0.001, flat_fee=0.0),  # $1 per 1000
                PricingTier(up_to=None, unit_price=0.0005, flat_fee=0.0)  # $0.50 per 1000
            ],
            MeterType.ANALYSES: [
                PricingTier(up_to=10, unit_price=0.0, flat_fee=0.0),  # Free tier
                PricingTier(up_to=100, unit_price=0.50, flat_fee=0.0),
                PricingTier(up_to=None, unit_price=0.30, flat_fee=0.0)
            ],
            MeterType.COMPONENTS_DETECTED: [
                PricingTier(up_to=1000, unit_price=0.0, flat_fee=0.0),
                PricingTier(up_to=None, unit_price=0.001, flat_fee=0.0)
            ],
            MeterType.AI_RECOMMENDATIONS: [
                PricingTier(up_to=None, unit_price=0.10, flat_fee=0.0)  # $0.10 each
            ],
            MeterType.STORAGE_GB: [
                PricingTier(up_to=5, unit_price=0.0, flat_fee=0.0),  # 5GB free
                PricingTier(up_to=None, unit_price=0.10, flat_fee=0.0)  # $0.10/GB/month
            ],
            MeterType.BANDWIDTH_GB: [
                PricingTier(up_to=50, unit_price=0.0, flat_fee=0.0),  # 50GB free
                PricingTier(up_to=None, unit_price=0.05, flat_fee=0.0)
            ],
            MeterType.COLLABORATION_MINUTES: [
                PricingTier(up_to=100, unit_price=0.0, flat_fee=0.0),  # 100 min free
                PricingTier(up_to=None, unit_price=0.01, flat_fee=0.0)  # $0.01/minute
            ],
            MeterType.PLUGIN_EXECUTIONS: [
                PricingTier(up_to=100, unit_price=0.0, flat_fee=0.0),
                PricingTier(up_to=None, unit_price=0.05, flat_fee=0.0)
            ],
            MeterType.WEBHOOKS_SENT: [
                PricingTier(up_to=1000, unit_price=0.0, flat_fee=0.0),
                PricingTier(up_to=None, unit_price=0.001, flat_fee=0.0)
            ]
        }

    async def record_usage(
        self,
        user_id: str,
        meter_type: MeterType,
        quantity: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record usage event.

        Args:
            user_id: User ID
            meter_type: Type of usage
            quantity: Amount used
            metadata: Additional metadata
        """
        record = UsageRecord(
            user_id=user_id,
            meter_type=meter_type,
            quantity=quantity,
            timestamp=datetime.utcnow(),
            metadata=metadata
        )

        # Store in database
        await self._store_usage_record(record)

        # Report to Stripe (for real-time metering)
        await self._report_to_stripe(record)

        logger.debug(f"Recorded usage: {user_id} - {meter_type.value} x{quantity}")

    async def _store_usage_record(self, record: UsageRecord):
        """Store usage record in database."""
        # TODO: Implement database storage
        pass

    async def _report_to_stripe(self, record: UsageRecord):
        """
        Report usage to Stripe for real-time metering.

        Args:
            record: Usage record
        """
        try:
            # Get user's Stripe customer ID
            # TODO: Fetch from database
            stripe_customer_id = f"cus_{record.user_id}"

            # Create usage record in Stripe
            stripe.billing.MeterEvent.create(
                event_name=record.meter_type.value,
                payload={
                    "stripe_customer_id": stripe_customer_id,
                    "value": str(int(record.quantity))
                },
                timestamp=int(record.timestamp.timestamp())
            )

            logger.debug(f"Reported to Stripe: {record.meter_type.value}")

        except stripe.error.StripeError as e:
            logger.error(f"Stripe metering error: {e}")

    async def calculate_cost(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[MeterType, float]:
        """
        Calculate cost for billing period.

        Args:
            user_id: User ID
            start_date: Period start
            end_date: Period end

        Returns:
            Cost breakdown by meter type
        """
        # Get usage for period
        usage_by_type = await self._get_usage_summary(user_id, start_date, end_date)

        costs = {}

        for meter_type, total_quantity in usage_by_type.items():
            cost = self._calculate_graduated_cost(meter_type, total_quantity)
            costs[meter_type] = cost

        return costs

    def _calculate_graduated_cost(
        self,
        meter_type: MeterType,
        quantity: float
    ) -> float:
        """
        Calculate cost using graduated pricing tiers.

        Args:
            meter_type: Meter type
            quantity: Total quantity

        Returns:
            Total cost
        """
        tiers = self.pricing.get(meter_type, [])
        if not tiers:
            return 0.0

        total_cost = 0.0
        remaining = quantity

        for tier in tiers:
            if remaining <= 0:
                break

            # How much in this tier?
            if tier.up_to is None:
                # Unlimited tier
                tier_quantity = remaining
            else:
                # Check if we've already passed this tier's threshold
                if quantity > tier.up_to:
                    tier_quantity = tier.up_to
                    # Account for previous tier
                    if tiers.index(tier) > 0:
                        prev_tier = tiers[tiers.index(tier) - 1]
                        if prev_tier.up_to:
                            tier_quantity -= prev_tier.up_to
                else:
                    tier_quantity = min(remaining, tier.up_to)

            # Calculate cost for this tier
            tier_cost = tier.flat_fee + (tier_quantity * tier.unit_price)
            total_cost += tier_cost

            remaining -= tier_quantity

        return total_cost

    async def _get_usage_summary(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[MeterType, float]:
        """Get usage summary for period."""
        # TODO: Query database
        # Placeholder: return empty usage
        return {meter_type: 0.0 for meter_type in MeterType}

    async def create_invoice(
        self,
        user_id: str,
        billing_period_start: datetime,
        billing_period_end: datetime
    ) -> str:
        """
        Create invoice for billing period.

        Args:
            user_id: User ID
            billing_period_start: Period start
            billing_period_end: Period end

        Returns:
            Invoice ID
        """
        # Calculate costs
        costs = await self.calculate_cost(user_id, billing_period_start, billing_period_end)

        total_amount = sum(costs.values())

        if total_amount == 0:
            logger.info(f"No charges for user {user_id} in period")
            return None

        # Get Stripe customer
        # TODO: Fetch from database
        stripe_customer_id = f"cus_{user_id}"

        # Create invoice items
        for meter_type, cost in costs.items():
            if cost > 0:
                stripe.InvoiceItem.create(
                    customer=stripe_customer_id,
                    amount=int(cost * 100),  # Convert to cents
                    currency="usd",
                    description=f"{meter_type.value} usage",
                    metadata={
                        "billing_period_start": billing_period_start.isoformat(),
                        "billing_period_end": billing_period_end.isoformat()
                    }
                )

        # Create invoice
        invoice = stripe.Invoice.create(
            customer=stripe_customer_id,
            auto_advance=True,  # Auto-finalize
            metadata={
                "billing_type": "metered_usage",
                "period_start": billing_period_start.isoformat(),
                "period_end": billing_period_end.isoformat()
            }
        )

        logger.info(f"Created invoice {invoice.id} for ${total_amount:.2f}")

        return invoice.id

    async def get_usage_forecast(
        self,
        user_id: str,
        days_to_forecast: int = 30
    ) -> Dict[str, Any]:
        """
        Forecast usage and cost for next period.

        Args:
            user_id: User ID
            days_to_forecast: Days to forecast

        Returns:
            Forecast data
        """
        # Get historical usage (last 30 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)

        historical_usage = await self._get_usage_summary(user_id, start_date, end_date)

        # Calculate daily average
        daily_avg = {
            meter_type: quantity / 30.0
            for meter_type, quantity in historical_usage.items()
        }

        # Forecast
        forecast_usage = {
            meter_type: avg * days_to_forecast
            for meter_type, avg in daily_avg.items()
        }

        # Calculate forecast cost
        forecast_costs = {}
        for meter_type, quantity in forecast_usage.items():
            cost = self._calculate_graduated_cost(meter_type, quantity)
            forecast_costs[meter_type] = cost

        total_forecast = sum(forecast_costs.values())

        return {
            "forecast_period_days": days_to_forecast,
            "forecast_usage": {k.value: v for k, v in forecast_usage.items()},
            "forecast_costs": {k.value: v for k, v in forecast_costs.items()},
            "total_forecast_cost": total_forecast,
            "based_on_days": 30
        }

    async def set_spending_limit(
        self,
        user_id: str,
        limit_usd: float,
        alert_threshold: float = 0.8
    ):
        """
        Set spending limit with alerts.

        Args:
            user_id: User ID
            limit_usd: Spending limit in USD
            alert_threshold: Alert when reaching this % of limit
        """
        # TODO: Store in database
        logger.info(f"Set spending limit for {user_id}: ${limit_usd} (alert at {alert_threshold*100}%)")

    async def check_spending_limit(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Check if user is approaching or over spending limit.

        Args:
            user_id: User ID

        Returns:
            Limit status
        """
        # Get current month usage
        now = datetime.utcnow()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        costs = await self.calculate_cost(user_id, start_of_month, now)
        current_spend = sum(costs.values())

        # Get limit (TODO: from database)
        spending_limit = 100.0  # Placeholder
        alert_threshold = 0.8

        percentage_used = (current_spend / spending_limit) if spending_limit > 0 else 0

        return {
            "current_spend": current_spend,
            "spending_limit": spending_limit,
            "percentage_used": percentage_used,
            "alert_threshold": alert_threshold,
            "should_alert": percentage_used >= alert_threshold,
            "limit_exceeded": current_spend >= spending_limit
        }


class UsageMiddleware:
    """Middleware to track API usage automatically."""

    def __init__(self, billing_service: MeteredBillingService):
        """Initialize middleware."""
        self.billing_service = billing_service

    async def track_api_call(
        self,
        user_id: str,
        endpoint: str,
        method: str
    ):
        """Track API call."""
        await self.billing_service.record_usage(
            user_id=user_id,
            meter_type=MeterType.API_CALLS,
            quantity=1.0,
            metadata={"endpoint": endpoint, "method": method}
        )

    async def track_analysis(
        self,
        user_id: str,
        analysis_id: str,
        component_count: int
    ):
        """Track analysis job."""
        # Track analysis
        await self.billing_service.record_usage(
            user_id=user_id,
            meter_type=MeterType.ANALYSES,
            quantity=1.0,
            metadata={"analysis_id": analysis_id}
        )

        # Track components detected
        await self.billing_service.record_usage(
            user_id=user_id,
            meter_type=MeterType.COMPONENTS_DETECTED,
            quantity=float(component_count),
            metadata={"analysis_id": analysis_id}
        )

    async def track_storage(
        self,
        user_id: str,
        storage_gb: float
    ):
        """Track storage usage."""
        await self.billing_service.record_usage(
            user_id=user_id,
            meter_type=MeterType.STORAGE_GB,
            quantity=storage_gb
        )


# Singleton instance
metered_billing = MeteredBillingService(stripe_api_key="sk_test_placeholder")
usage_middleware = UsageMiddleware(metered_billing)
