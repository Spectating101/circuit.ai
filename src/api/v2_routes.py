"""
API v2 Routes

New routes for:
- Analytics & reporting
- Webhooks management
- Admin dashboard
- A/B testing
- Feature flags
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from pydantic import BaseModel, Field
from loguru import logger

from src.analytics.analytics_service_v2 import analytics_service_v2
from src.webhooks.webhook_service_v2 import webhook_service_v2
from src.admin.dashboard_service_v2 import admin_dashboard_service_v2


# ===== Pydantic Models =====

class WebhookCreate(BaseModel):
    """Webhook creation request."""
    url: str = Field(..., description="Webhook URL")
    events: List[str] = Field(..., description="Event patterns to subscribe to")
    description: Optional[str] = Field(None, description="Webhook description")


class WebhookUpdate(BaseModel):
    """Webhook update request."""
    url: Optional[str] = Field(None, description="New webhook URL")
    events: Optional[List[str]] = Field(None, description="New event patterns")
    status: Optional[str] = Field(None, description="Webhook status")


class EventTrack(BaseModel):
    """Event tracking request."""
    event_name: str = Field(..., description="Event name")
    properties: Optional[Dict[str, Any]] = Field(default={}, description="Event properties")


class FunnelAnalysisRequest(BaseModel):
    """Funnel analysis request."""
    funnel_steps: List[str] = Field(..., description="List of event names in funnel order")


class ReportExportRequest(BaseModel):
    """Report export request."""
    report_type: str = Field(..., description="Report type (events/sessions/revenue)")
    format: str = Field(default="csv", description="Export format (csv/excel/json)")
    start_date: Optional[datetime] = Field(None, description="Start date")
    end_date: Optional[datetime] = Field(None, description="End date")


class FeatureFlagUpdate(BaseModel):
    """Feature flag update request."""
    enabled: bool = Field(..., description="Whether flag is enabled")


# ===== Routers =====

analytics_router = APIRouter(prefix="/api/v2/analytics", tags=["Analytics"])
webhooks_router = APIRouter(prefix="/api/v2/webhooks", tags=["Webhooks"])
admin_router = APIRouter(prefix="/api/v2/admin", tags=["Admin"])


# ===== Analytics Routes =====

@analytics_router.post("/track")
async def track_event(
    event: EventTrack,
    user_id: str = Query(..., description="User ID")
):
    """
    Track an analytics event.

    Example:
        POST /api/v2/analytics/track?user_id=user123
        {
            "event_name": "feature.used",
            "properties": {"feature": "bom_generation"}
        }
    """
    try:
        await analytics_service_v2.track_event(
            user_id=user_id,
            event_name=event.event_name,
            properties=event.properties
        )

        return {"success": True, "message": "Event tracked"}

    except Exception as e:
        logger.error(f"Error tracking event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error tracking event: {str(e)}"
        )


@analytics_router.get("/user/{user_id}/behavior")
async def get_user_behavior(user_id: str):
    """
    Get user behavior metrics.

    Returns:
        User behavior metrics including session count, analyses, churn risk, etc.
    """
    try:
        behavior = await analytics_service_v2.get_user_behavior(user_id)
        return behavior.__dict__

    except Exception as e:
        logger.error(f"Error fetching user behavior: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching user behavior: {str(e)}"
        )


@analytics_router.get("/user/{user_id}/churn-prediction")
async def predict_churn(user_id: str):
    """
    Predict user churn probability.

    Returns:
        Churn prediction with risk level and recommendations.
    """
    try:
        prediction = await analytics_service_v2.predict_churn(user_id)
        return prediction

    except Exception as e:
        logger.error(f"Error predicting churn: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error predicting churn: {str(e)}"
        )


@analytics_router.get("/revenue")
async def get_revenue_analytics(period: str = Query(default="month", regex="^(day|week|month|year)$")):
    """
    Get revenue analytics.

    Args:
        period: Analysis period (day/week/month/year)

    Returns:
        Revenue metrics including MRR, ARR, churn, etc.
    """
    try:
        revenue = await analytics_service_v2.get_revenue_analytics(period)
        return revenue.__dict__

    except Exception as e:
        logger.error(f"Error fetching revenue analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching revenue analytics: {str(e)}"
        )


@analytics_router.get("/features/usage")
async def get_feature_usage():
    """
    Get feature usage statistics.

    Returns:
        List of features with usage metrics.
    """
    try:
        features = await analytics_service_v2.get_feature_usage()
        return [f.__dict__ for f in features]

    except Exception as e:
        logger.error(f"Error fetching feature usage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching feature usage: {str(e)}"
        )


@analytics_router.post("/funnel/analyze")
async def analyze_funnel(request: FunnelAnalysisRequest):
    """
    Analyze conversion funnel.

    Example:
        POST /api/v2/analytics/funnel/analyze
        {
            "funnel_steps": ["user.signup", "analysis.started", "subscription.created"]
        }
    """
    try:
        funnel_data = await analytics_service_v2.generate_funnel_analysis(
            request.funnel_steps
        )
        return funnel_data

    except Exception as e:
        logger.error(f"Error analyzing funnel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing funnel: {str(e)}"
        )


@analytics_router.get("/user/{user_id}/ltv")
async def get_user_ltv(user_id: str):
    """
    Calculate customer lifetime value.

    Returns:
        LTV calculation with predictions.
    """
    try:
        ltv = await analytics_service_v2.calculate_ltv(user_id)
        return ltv

    except Exception as e:
        logger.error(f"Error calculating LTV: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating LTV: {str(e)}"
        )


@analytics_router.get("/realtime/stats")
async def get_realtime_stats():
    """
    Get real-time system statistics.

    Returns:
        Real-time metrics (active users, requests, revenue, etc.)
    """
    try:
        stats = await analytics_service_v2.get_realtime_stats()
        return stats

    except Exception as e:
        logger.error(f"Error fetching realtime stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching realtime stats: {str(e)}"
        )


# ===== Webhook Routes =====

@webhooks_router.post("")
async def create_webhook(
    webhook: WebhookCreate,
    user_id: str = Query(..., description="User ID")
):
    """
    Register a new webhook.

    Example:
        POST /api/v2/webhooks?user_id=user123
        {
            "url": "https://example.com/webhook",
            "events": ["analysis.completed", "bom.generated"],
            "description": "My webhook"
        }
    """
    try:
        webhook_id = await webhook_service_v2.register_webhook(
            user_id=user_id,
            url=webhook.url,
            events=webhook.events,
            description=webhook.description
        )

        return {"webhook_id": webhook_id, "message": "Webhook registered successfully"}

    except Exception as e:
        logger.error(f"Error creating webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating webhook: {str(e)}"
        )


@webhooks_router.put("/{webhook_id}")
async def update_webhook(webhook_id: str, update: WebhookUpdate):
    """
    Update webhook configuration.

    Example:
        PUT /api/v2/webhooks/webhook123
        {
            "events": ["analysis.*"],
            "status": "active"
        }
    """
    try:
        from src.models.webhook_models import WebhookStatus

        status_enum = None
        if update.status:
            status_enum = WebhookStatus(update.status)

        success = await webhook_service_v2.update_webhook(
            webhook_id=webhook_id,
            url=update.url,
            events=update.events,
            status=status_enum
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )

        return {"success": True, "message": "Webhook updated"}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status value: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error updating webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating webhook: {str(e)}"
        )


@webhooks_router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str):
    """
    Delete a webhook.
    """
    try:
        success = await webhook_service_v2.delete_webhook(webhook_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )

        return {"success": True, "message": "Webhook deleted"}

    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting webhook: {str(e)}"
        )


@webhooks_router.get("/{webhook_id}/stats")
async def get_webhook_stats(webhook_id: str):
    """
    Get webhook delivery statistics.

    Returns:
        Delivery stats, success rate, recent deliveries, etc.
    """
    try:
        stats = await webhook_service_v2.get_webhook_stats(webhook_id)

        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )

        return stats

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching webhook stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching webhook stats: {str(e)}"
        )


@webhooks_router.get("/{webhook_id}/deliveries")
async def get_webhook_deliveries(
    webhook_id: str,
    limit: int = Query(default=50, ge=1, le=200)
):
    """
    Get webhook delivery history.

    Args:
        webhook_id: Webhook ID
        limit: Maximum number of deliveries to return

    Returns:
        List of delivery records
    """
    try:
        deliveries = await webhook_service_v2.get_delivery_history(webhook_id, limit)
        return deliveries

    except Exception as e:
        logger.error(f"Error fetching delivery history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching delivery history: {str(e)}"
        )


# ===== Admin Routes =====

@admin_router.get("/overview")
async def get_overview_metrics():
    """
    Get comprehensive admin dashboard overview.

    Returns:
        All metrics (users, revenue, system, analyses)
    """
    try:
        metrics = await admin_dashboard_service_v2.get_overview_metrics()
        return metrics

    except Exception as e:
        logger.error(f"Error fetching overview metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching overview metrics: {str(e)}"
        )


@admin_router.get("/users/metrics")
async def get_user_metrics():
    """Get user-related metrics."""
    try:
        metrics = await admin_dashboard_service_v2.get_user_metrics()
        return metrics.__dict__

    except Exception as e:
        logger.error(f"Error fetching user metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching user metrics: {str(e)}"
        )


@admin_router.get("/revenue/metrics")
async def get_revenue_metrics():
    """Get revenue-related metrics."""
    try:
        metrics = await admin_dashboard_service_v2.get_revenue_metrics()
        return metrics.__dict__

    except Exception as e:
        logger.error(f"Error fetching revenue metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching revenue metrics: {str(e)}"
        )


@admin_router.get("/system/metrics")
async def get_system_metrics():
    """Get system health metrics."""
    try:
        metrics = await admin_dashboard_service_v2.get_system_metrics()
        return metrics.__dict__

    except Exception as e:
        logger.error(f"Error fetching system metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching system metrics: {str(e)}"
        )


@admin_router.get("/analyses/metrics")
async def get_analysis_metrics():
    """Get analysis-related metrics."""
    try:
        metrics = await admin_dashboard_service_v2.get_analysis_metrics()
        return metrics.__dict__

    except Exception as e:
        logger.error(f"Error fetching analysis metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching analysis metrics: {str(e)}"
        )


@admin_router.get("/feature-flags")
async def get_feature_flags():
    """Get all feature flags."""
    try:
        flags = await admin_dashboard_service_v2.get_feature_flags()
        return flags

    except Exception as e:
        logger.error(f"Error fetching feature flags: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching feature flags: {str(e)}"
        )


@admin_router.put("/feature-flags/{flag_key}")
async def update_feature_flag(flag_key: str, update: FeatureFlagUpdate):
    """
    Update feature flag status.

    Example:
        PUT /api/v2/admin/feature-flags/new_dashboard
        {
            "enabled": true
        }
    """
    try:
        success = await admin_dashboard_service_v2.update_feature_flag(
            flag_key, update.enabled
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feature flag not found"
            )

        return {"success": True, "message": f"Feature flag {flag_key} updated"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating feature flag: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating feature flag: {str(e)}"
        )


@admin_router.get("/experiments")
async def get_ab_tests():
    """Get all A/B tests."""
    try:
        experiments = await admin_dashboard_service_v2.get_ab_tests()
        return experiments

    except Exception as e:
        logger.error(f"Error fetching experiments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching experiments: {str(e)}"
        )


@admin_router.get("/alerts")
async def get_active_alerts():
    """Get active system alerts."""
    try:
        alerts = await admin_dashboard_service_v2.get_active_alerts()
        return alerts

    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching alerts: {str(e)}"
        )


@admin_router.get("/activity")
async def get_recent_activity(limit: int = Query(default=100, ge=1, le=500)):
    """
    Get recent admin activity.

    Args:
        limit: Maximum number of activities to return
    """
    try:
        activities = await admin_dashboard_service_v2.get_recent_activity(limit)
        return activities

    except Exception as e:
        logger.error(f"Error fetching activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching activity: {str(e)}"
        )


# Combine all routers
def get_v2_routers() -> List[APIRouter]:
    """
    Get all v2 API routers.

    Returns:
        List of routers to include in main app

    Example:
        from fastapi import FastAPI
        from src.api.v2_routes import get_v2_routers

        app = FastAPI()
        for router in get_v2_routers():
            app.include_router(router)
    """
    return [analytics_router, webhooks_router, admin_router]
