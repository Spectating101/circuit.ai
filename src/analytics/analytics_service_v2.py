"""
Advanced Analytics & Reporting Service (Database-backed)

Comprehensive analytics with real database persistence for:
- User behavior tracking
- Feature usage
- Revenue analysis
- Predictive analytics
- Custom reports
- Data export
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import pandas as pd
import numpy as np
from loguru import logger
from sqlalchemy import select, func, and_, or_, desc, text
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import csv
import io

from src.database.connection import db_manager
from src.models.analytics_models import (
    Event, UserSession, FeatureUsageStat, UserBehaviorMetric,
    CohortAnalysis, UserLTV, RevenueMetric, ActivityLog
)


@dataclass
class UserBehaviorMetrics:
    """User behavior analytics."""
    user_id: str
    session_count: int
    total_analyses: int
    avg_analyses_per_session: float
    total_time_spent: float  # minutes
    last_active: datetime
    favorite_features: List[str]
    churn_risk_score: float  # 0-1


@dataclass
class RevenueAnalytics:
    """Revenue analytics."""
    period: str  # "day", "week", "month"
    total_revenue: float
    mrr: float
    arr: float
    new_revenue: float
    expansion_revenue: float
    contraction_revenue: float
    churn_revenue: float
    net_revenue_retention: float


@dataclass
class FeatureUsage:
    """Feature usage statistics."""
    feature_name: str
    total_uses: int
    unique_users: int
    avg_uses_per_user: float
    adoption_rate: float  # percentage
    growth_rate: float  # month-over-month


class AnalyticsServiceV2:
    """Advanced analytics service with database persistence."""

    def __init__(self):
        """Initialize analytics service."""
        self.db_manager = db_manager
        logger.info("AnalyticsServiceV2 initialized with database backend")

    async def track_event(
        self,
        user_id: str,
        event_name: str,
        session_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        page_url: Optional[str] = None,
        referrer: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """
        Track analytics event to database.

        Args:
            user_id: User ID
            event_name: Event name
            session_id: Session ID
            properties: Event properties
            page_url: Page URL
            referrer: Referrer URL
            user_agent: User agent string
            ip_address: IP address
        """
        async with self.db_manager.session() as session:
            event = Event(
                id=str(uuid.uuid4()),
                user_id=user_id,
                session_id=session_id or str(uuid.uuid4()),
                event_name=event_name,
                properties=properties or {},
                page_url=page_url,
                referrer=referrer,
                user_agent=user_agent,
                ip_address=ip_address,
                timestamp=datetime.utcnow()
            )

            session.add(event)
            await session.commit()

            logger.debug(f"Tracked event: {event_name} for user {user_id}")

            # Update session tracking
            await self._update_session_tracking(session, user_id, session_id or str(uuid.uuid4()))

    async def _update_session_tracking(self, session: AsyncSession, user_id: str, session_id: str):
        """Update session tracking metrics."""
        # Get or create session
        result = await session.execute(
            select(UserSession).where(UserSession.id == session_id)
        )
        user_session = result.scalar_one_or_none()

        if user_session:
            user_session.events_count += 1
            user_session.session_end = datetime.utcnow()
            user_session.duration_seconds = int(
                (user_session.session_end - user_session.session_start).total_seconds()
            )
        else:
            user_session = UserSession(
                id=session_id,
                user_id=user_id,
                session_start=datetime.utcnow(),
                events_count=1
            )
            session.add(user_session)

        await session.commit()

    async def get_user_behavior(self, user_id: str) -> UserBehaviorMetrics:
        """
        Get user behavior metrics from database.

        Args:
            user_id: User ID

        Returns:
            UserBehaviorMetrics
        """
        async with self.db_manager.session() as session:
            # Check if we have pre-computed metrics
            result = await session.execute(
                select(UserBehaviorMetric).where(UserBehaviorMetric.user_id == user_id)
            )
            metric = result.scalar_one_or_none()

            if metric:
                return UserBehaviorMetrics(
                    user_id=metric.user_id,
                    session_count=metric.session_count,
                    total_analyses=metric.total_analyses,
                    avg_analyses_per_session=metric.avg_analyses_per_session,
                    total_time_spent=metric.total_time_spent_minutes,
                    last_active=metric.last_active,
                    favorite_features=metric.favorite_features,
                    churn_risk_score=metric.churn_risk_score
                )

            # Compute on-the-fly if not pre-computed
            return await self._compute_user_behavior(session, user_id)

    async def _compute_user_behavior(self, session: AsyncSession, user_id: str) -> UserBehaviorMetrics:
        """Compute user behavior metrics from raw data."""
        # Session count
        result = await session.execute(
            select(func.count(UserSession.id)).where(UserSession.user_id == user_id)
        )
        session_count = result.scalar() or 0

        # Total analyses (count events with name "analysis.completed")
        result = await session.execute(
            select(func.count(Event.id)).where(
                and_(Event.user_id == user_id, Event.event_name == "analysis.completed")
            )
        )
        total_analyses = result.scalar() or 0

        # Average analyses per session
        avg_analyses_per_session = total_analyses / session_count if session_count > 0 else 0.0

        # Total time spent
        result = await session.execute(
            select(func.sum(UserSession.duration_seconds)).where(UserSession.user_id == user_id)
        )
        total_seconds = result.scalar() or 0
        total_time_spent = total_seconds / 60.0  # Convert to minutes

        # Last active
        result = await session.execute(
            select(func.max(Event.timestamp)).where(Event.user_id == user_id)
        )
        last_active = result.scalar() or datetime.utcnow()

        # Favorite features (top 3 most used)
        result = await session.execute(
            select(Event.event_name, func.count(Event.id).label('count'))
            .where(Event.user_id == user_id)
            .group_by(Event.event_name)
            .order_by(desc('count'))
            .limit(3)
        )
        favorite_features = [row[0] for row in result.all()]

        # Churn risk score (simple heuristic)
        days_since_active = (datetime.utcnow() - last_active).days
        churn_risk_score = min(1.0, days_since_active / 60.0)  # 60 days = 100% risk

        return UserBehaviorMetrics(
            user_id=user_id,
            session_count=session_count,
            total_analyses=total_analyses,
            avg_analyses_per_session=avg_analyses_per_session,
            total_time_spent=total_time_spent,
            last_active=last_active,
            favorite_features=favorite_features,
            churn_risk_score=churn_risk_score
        )

    async def predict_churn(self, user_id: str) -> Dict[str, Any]:
        """
        Predict user churn probability.

        Args:
            user_id: User ID

        Returns:
            Churn prediction data
        """
        behavior = await self.get_user_behavior(user_id)

        # Enhanced churn prediction with multiple factors
        days_since_last_active = (datetime.utcnow() - behavior.last_active).days
        usage_trend = behavior.avg_analyses_per_session

        churn_probability = 0.0

        # Inactivity factor
        if days_since_last_active > 30:
            churn_probability += 0.5
        elif days_since_last_active > 14:
            churn_probability += 0.3
        elif days_since_last_active > 7:
            churn_probability += 0.1

        # Usage trend factor
        if usage_trend < 0.5:
            churn_probability += 0.3
        elif usage_trend < 1.0:
            churn_probability += 0.2

        # Session frequency factor
        if behavior.session_count < 5:
            churn_probability += 0.2

        churn_probability = min(1.0, churn_probability)

        return {
            "user_id": user_id,
            "churn_probability": churn_probability,
            "risk_level": "high" if churn_probability > 0.7 else "medium" if churn_probability > 0.4 else "low",
            "recommendations": self._get_retention_recommendations(churn_probability),
            "factors": {
                "days_inactive": days_since_last_active,
                "usage_trend": usage_trend,
                "session_count": behavior.session_count
            }
        }

    def _get_retention_recommendations(self, churn_prob: float) -> List[str]:
        """Get recommendations to improve retention."""
        recommendations = []

        if churn_prob > 0.7:
            recommendations.extend([
                "Send personalized re-engagement email",
                "Offer special discount or promotion",
                "Schedule customer success call",
                "Provide free consultation on advanced features"
            ])
        elif churn_prob > 0.4:
            recommendations.extend([
                "Send feature update notification",
                "Provide usage tips and tutorials",
                "Ask for feedback",
                "Highlight value received"
            ])
        else:
            recommendations.extend([
                "Continue regular communication",
                "Promote premium features",
                "Encourage referrals"
            ])

        return recommendations

    async def get_revenue_analytics(self, period: str = "month") -> RevenueAnalytics:
        """
        Get revenue analytics from database.

        Args:
            period: Analysis period (day/week/month/year)

        Returns:
            RevenueAnalytics
        """
        async with self.db_manager.session() as session:
            # Get latest revenue metric for the period
            result = await session.execute(
                select(RevenueMetric)
                .where(RevenueMetric.period_type == period)
                .order_by(desc(RevenueMetric.period_start))
                .limit(1)
            )
            metric = result.scalar_one_or_none()

            if metric:
                return RevenueAnalytics(
                    period=metric.period_type,
                    total_revenue=metric.total_revenue,
                    mrr=metric.mrr,
                    arr=metric.arr,
                    new_revenue=metric.new_revenue,
                    expansion_revenue=metric.expansion_revenue,
                    contraction_revenue=metric.contraction_revenue,
                    churn_revenue=metric.churn_revenue,
                    net_revenue_retention=metric.net_revenue_retention
                )

            # Return zeros if no data
            return RevenueAnalytics(
                period=period,
                total_revenue=0.0,
                mrr=0.0,
                arr=0.0,
                new_revenue=0.0,
                expansion_revenue=0.0,
                contraction_revenue=0.0,
                churn_revenue=0.0,
                net_revenue_retention=0.0
            )

    async def get_feature_usage(self) -> List[FeatureUsage]:
        """
        Get feature usage statistics from database.

        Returns:
            List of FeatureUsage
        """
        async with self.db_manager.session() as session:
            # Get latest stats for each feature
            result = await session.execute(
                select(FeatureUsageStat)
                .where(FeatureUsageStat.date >= datetime.utcnow() - timedelta(days=30))
                .order_by(desc(FeatureUsageStat.date))
            )
            stats = result.scalars().all()

            # Group by feature and aggregate
            feature_map = {}
            for stat in stats:
                if stat.feature_name not in feature_map:
                    feature_map[stat.feature_name] = stat

            features = []
            for feature_name, stat in feature_map.items():
                features.append(FeatureUsage(
                    feature_name=stat.feature_name,
                    total_uses=stat.total_uses,
                    unique_users=stat.unique_users,
                    avg_uses_per_user=stat.avg_uses_per_user,
                    adoption_rate=(stat.unique_users / stat.total_users * 100) if stat.total_users > 0 else 0.0,
                    growth_rate=0.0  # TODO: Calculate month-over-month growth
                ))

            return features

    async def generate_funnel_analysis(
        self,
        funnel_steps: List[str]
    ) -> Dict[str, Any]:
        """
        Analyze conversion funnel.

        Args:
            funnel_steps: List of event names in funnel order

        Returns:
            Funnel analysis data
        """
        async with self.db_manager.session() as session:
            funnel_data = []
            total_users = None

            for i, step in enumerate(funnel_steps):
                # Count unique users who completed this step
                result = await session.execute(
                    select(func.count(func.distinct(Event.user_id)))
                    .where(Event.event_name == step)
                )
                users_at_step = result.scalar() or 0

                if total_users is None:
                    total_users = users_at_step

                conversion = (users_at_step / total_users * 100) if total_users > 0 else 0.0

                funnel_data.append({
                    "step": step,
                    "users": users_at_step,
                    "conversion": conversion
                })

            # Find biggest drop-off
            bottleneck = None
            max_drop = 0.0
            for i in range(len(funnel_data) - 1):
                drop = funnel_data[i]["conversion"] - funnel_data[i + 1]["conversion"]
                if drop > max_drop:
                    max_drop = drop
                    bottleneck = funnel_data[i + 1]["step"]

            overall_conversion = funnel_data[-1]["conversion"] if funnel_data else 0.0

            return {
                "funnel": funnel_data,
                "overall_conversion": overall_conversion,
                "bottleneck": bottleneck
            }

    async def calculate_ltv(self, user_id: str) -> Dict[str, Any]:
        """
        Calculate customer lifetime value.

        Args:
            user_id: User ID

        Returns:
            LTV calculation
        """
        async with self.db_manager.session() as session:
            # Check pre-computed LTV
            result = await session.execute(
                select(UserLTV).where(UserLTV.user_id == user_id)
            )
            ltv_record = result.scalar_one_or_none()

            if ltv_record:
                return {
                    "user_id": ltv_record.user_id,
                    "ltv": ltv_record.ltv,
                    "avg_monthly_spend": ltv_record.avg_monthly_spend,
                    "predicted_lifetime_months": ltv_record.predicted_lifetime_months,
                    "confidence": ltv_record.confidence
                }

            # Compute LTV if not cached
            # TODO: Query subscription history and calculate
            return {
                "user_id": user_id,
                "ltv": 0.0,
                "avg_monthly_spend": 0.0,
                "predicted_lifetime_months": 0.0,
                "confidence": 0.0
            }

    async def export_report(
        self,
        report_type: str,
        format: str = "csv",
        date_range: Optional[Dict[str, datetime]] = None
    ) -> bytes:
        """
        Export analytics report.

        Args:
            report_type: Type of report (events, sessions, revenue)
            format: Export format (csv, excel, json)
            date_range: Date range for report

        Returns:
            Report file bytes
        """
        async with self.db_manager.session() as session:
            if report_type == "events":
                return await self._export_events(session, format, date_range)
            elif report_type == "sessions":
                return await self._export_sessions(session, format, date_range)
            elif report_type == "revenue":
                return await self._export_revenue(session, format, date_range)
            else:
                return b""

    async def _export_events(
        self,
        session: AsyncSession,
        format: str,
        date_range: Optional[Dict[str, datetime]]
    ) -> bytes:
        """Export events data."""
        query = select(Event)

        if date_range:
            query = query.where(
                and_(
                    Event.timestamp >= date_range.get("start", datetime.utcnow() - timedelta(days=30)),
                    Event.timestamp <= date_range.get("end", datetime.utcnow())
                )
            )

        result = await session.execute(query.limit(10000))  # Limit for performance
        events = result.scalars().all()

        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Timestamp", "User ID", "Event Name", "Session ID"])

            for event in events:
                writer.writerow([
                    event.timestamp.isoformat(),
                    event.user_id,
                    event.event_name,
                    event.session_id
                ])

            return output.getvalue().encode()

        return b""

    async def _export_sessions(
        self,
        session: AsyncSession,
        format: str,
        date_range: Optional[Dict[str, datetime]]
    ) -> bytes:
        """Export sessions data."""
        # Similar to _export_events
        return b""

    async def _export_revenue(
        self,
        session: AsyncSession,
        format: str,
        date_range: Optional[Dict[str, datetime]]
    ) -> bytes:
        """Export revenue data."""
        # Similar to _export_events
        return b""

    async def get_realtime_stats(self) -> Dict[str, Any]:
        """
        Get real-time statistics from database.

        Returns:
            Real-time stats
        """
        async with self.db_manager.session() as session:
            # Active users (last 15 minutes)
            cutoff = datetime.utcnow() - timedelta(minutes=15)
            result = await session.execute(
                select(func.count(func.distinct(Event.user_id)))
                .where(Event.timestamp >= cutoff)
            )
            active_users = result.scalar() or 0

            # Events last hour
            cutoff_hour = datetime.utcnow() - timedelta(hours=1)
            result = await session.execute(
                select(func.count(Event.id))
                .where(
                    and_(
                        Event.timestamp >= cutoff_hour,
                        Event.event_name == "analysis.completed"
                    )
                )
            )
            analyses_last_hour = result.scalar() or 0

            return {
                "active_users": active_users,
                "analyses_last_hour": analyses_last_hour,
                "revenue_today": 0.0,  # TODO: Query from billing
                "api_requests_per_second": 0.0,  # TODO: Query from metrics
                "avg_response_time_ms": 0,  # TODO: Query from metrics
                "error_rate": 0.0  # TODO: Query from metrics
            }


# Singleton instance
analytics_service_v2 = AnalyticsServiceV2()
