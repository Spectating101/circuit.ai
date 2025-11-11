"""
Admin Dashboard Service (Database-backed)

Comprehensive admin panel with real database queries for:
- User analytics
- Revenue metrics
- System health
- Feature flags
- A/B testing
- Real-time monitoring
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio
from loguru import logger
from sqlalchemy import select, func, and_, or_, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import db_manager
from src.models.analytics_models import Event, UserSession, FeatureUsageStat, RevenueMetric, ActivityLog
from src.models.admin_models import Experiment, FeatureFlag, SystemAlert, SystemHealth, ExperimentStatus, AlertStatus
from src.models.webhook_models import Webhook, WebhookDelivery


@dataclass
class UserMetrics:
    """User-related metrics."""
    total_users: int
    active_users_today: int
    active_users_week: int
    active_users_month: int
    new_signups_today: int
    new_signups_week: int
    new_signups_month: int
    churn_rate: float
    avg_session_duration: float


@dataclass
class RevenueMetrics:
    """Revenue-related metrics."""
    mrr: float
    arr: float
    total_revenue_today: float
    total_revenue_month: float
    total_revenue_year: float
    avg_revenue_per_user: float
    paying_users: int
    conversion_rate: float
    ltv: float
    cac: float


@dataclass
class SystemMetrics:
    """System health metrics."""
    api_response_time_p50: float
    api_response_time_p95: float
    api_response_time_p99: float
    error_rate: float
    uptime_percentage: float
    total_requests_today: int
    successful_analyses: int
    failed_analyses: int
    cache_hit_rate: float
    cpu_usage: float
    memory_usage: float
    disk_usage: float


@dataclass
class AnalysisMetrics:
    """Analysis-related metrics."""
    total_analyses: int
    analyses_today: int
    analyses_week: int
    analyses_month: int
    avg_processing_time: float
    top_component_types: List[Dict[str, Any]]
    success_rate: float
    avg_components_per_analysis: float


class AdminDashboardServiceV2:
    """Service for admin dashboard data with database integration."""

    def __init__(self):
        """Initialize admin dashboard service."""
        self.db_manager = db_manager
        logger.info("AdminDashboardServiceV2 initialized with database backend")

    async def get_overview_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive overview metrics for dashboard.

        Returns:
            Dictionary of all metrics
        """
        logger.info("Fetching overview metrics from database")

        # Fetch all metrics in parallel
        user_metrics, revenue_metrics, system_metrics, analysis_metrics = await asyncio.gather(
            self.get_user_metrics(),
            self.get_revenue_metrics(),
            self.get_system_metrics(),
            self.get_analysis_metrics()
        )

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "users": user_metrics.__dict__,
            "revenue": revenue_metrics.__dict__,
            "system": system_metrics.__dict__,
            "analyses": analysis_metrics.__dict__
        }

    async def get_user_metrics(self) -> UserMetrics:
        """Get user-related metrics from database."""
        async with self.db_manager.session() as session:
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = now - timedelta(days=7)
            month_start = now - timedelta(days=30)

            # Total users (would normally query Users table, but we use events as proxy)
            total_users_result = await session.execute(
                select(func.count(func.distinct(Event.user_id)))
            )
            total_users = total_users_result.scalar() or 0

            # Active users (users with events in timeframe)
            active_today_result = await session.execute(
                select(func.count(func.distinct(Event.user_id)))
                .where(Event.timestamp >= today_start)
            )
            active_users_today = active_today_result.scalar() or 0

            active_week_result = await session.execute(
                select(func.count(func.distinct(Event.user_id)))
                .where(Event.timestamp >= week_start)
            )
            active_users_week = active_week_result.scalar() or 0

            active_month_result = await session.execute(
                select(func.count(func.distinct(Event.user_id)))
                .where(Event.timestamp >= month_start)
            )
            active_users_month = active_month_result.scalar() or 0

            # New signups (users with "user.signup" event)
            signups_today_result = await session.execute(
                select(func.count(Event.id))
                .where(
                    and_(
                        Event.event_name == "user.signup",
                        Event.timestamp >= today_start
                    )
                )
            )
            new_signups_today = signups_today_result.scalar() or 0

            signups_week_result = await session.execute(
                select(func.count(Event.id))
                .where(
                    and_(
                        Event.event_name == "user.signup",
                        Event.timestamp >= week_start
                    )
                )
            )
            new_signups_week = signups_week_result.scalar() or 0

            signups_month_result = await session.execute(
                select(func.count(Event.id))
                .where(
                    and_(
                        Event.event_name == "user.signup",
                        Event.timestamp >= month_start
                    )
                )
            )
            new_signups_month = signups_month_result.scalar() or 0

            # Churn rate (simplified calculation)
            churn_rate = 0.0
            if new_signups_month > 0:
                inactive_users = total_users - active_users_month
                churn_rate = (inactive_users / total_users * 100) if total_users > 0 else 0.0

            # Average session duration
            avg_duration_result = await session.execute(
                select(func.avg(UserSession.duration_seconds))
                .where(UserSession.session_start >= month_start)
            )
            avg_duration = avg_duration_result.scalar() or 0
            avg_session_duration = avg_duration / 60.0  # Convert to minutes

            return UserMetrics(
                total_users=total_users,
                active_users_today=active_users_today,
                active_users_week=active_users_week,
                active_users_month=active_users_month,
                new_signups_today=new_signups_today,
                new_signups_week=new_signups_week,
                new_signups_month=new_signups_month,
                churn_rate=churn_rate,
                avg_session_duration=avg_session_duration
            )

    async def get_revenue_metrics(self) -> RevenueMetrics:
        """Get revenue-related metrics from database."""
        async with self.db_manager.session() as session:
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

            # Get latest monthly revenue metric
            monthly_metric_result = await session.execute(
                select(RevenueMetric)
                .where(RevenueMetric.period_type == "month")
                .order_by(desc(RevenueMetric.period_start))
                .limit(1)
            )
            monthly_metric = monthly_metric_result.scalar_one_or_none()

            if monthly_metric:
                mrr = monthly_metric.mrr
                arr = monthly_metric.arr
                paying_users = monthly_metric.total_customers
                total_revenue_month = monthly_metric.total_revenue
            else:
                mrr = 0.0
                arr = 0.0
                paying_users = 0
                total_revenue_month = 0.0

            # Get today's revenue
            daily_metric_result = await session.execute(
                select(RevenueMetric)
                .where(
                    and_(
                        RevenueMetric.period_type == "day",
                        RevenueMetric.period_start >= today_start
                    )
                )
                .order_by(desc(RevenueMetric.period_start))
                .limit(1)
            )
            daily_metric = daily_metric_result.scalar_one_or_none()
            total_revenue_today = daily_metric.total_revenue if daily_metric else 0.0

            # Get year's revenue
            year_metrics_result = await session.execute(
                select(func.sum(RevenueMetric.total_revenue))
                .where(
                    and_(
                        RevenueMetric.period_type == "month",
                        RevenueMetric.period_start >= year_start
                    )
                )
            )
            total_revenue_year = year_metrics_result.scalar() or 0.0

            # Calculate derived metrics
            avg_revenue_per_user = (total_revenue_month / paying_users) if paying_users > 0 else 0.0

            # Conversion rate (paying users / total users)
            total_users_result = await session.execute(
                select(func.count(func.distinct(Event.user_id)))
            )
            total_users = total_users_result.scalar() or 1
            conversion_rate = (paying_users / total_users * 100) if total_users > 0 else 0.0

            # Placeholder for LTV and CAC (would need more complex calculations)
            ltv = avg_revenue_per_user * 24  # Assume 24 month lifetime
            cac = 150.0  # Placeholder

            return RevenueMetrics(
                mrr=mrr,
                arr=arr,
                total_revenue_today=total_revenue_today,
                total_revenue_month=total_revenue_month,
                total_revenue_year=total_revenue_year,
                avg_revenue_per_user=avg_revenue_per_user,
                paying_users=paying_users,
                conversion_rate=conversion_rate,
                ltv=ltv,
                cac=cac
            )

    async def get_system_metrics(self) -> SystemMetrics:
        """Get system health metrics from database."""
        async with self.db_manager.session() as session:
            # Get latest system health snapshot
            health_result = await session.execute(
                select(SystemHealth)
                .order_by(desc(SystemHealth.timestamp))
                .limit(1)
            )
            health = health_result.scalar_one_or_none()

            if health:
                return SystemMetrics(
                    api_response_time_p50=health.avg_response_time_ms / 1000.0,  # Convert to seconds
                    api_response_time_p95=health.avg_response_time_ms * 1.5 / 1000.0,  # Estimate
                    api_response_time_p99=health.avg_response_time_ms * 2.0 / 1000.0,  # Estimate
                    error_rate=health.error_rate or 0.0,
                    uptime_percentage=99.95,  # Placeholder
                    total_requests_today=int(health.request_rate * 86400) if health.request_rate else 0,
                    successful_analyses=0,  # TODO: Track separately
                    failed_analyses=0,  # TODO: Track separately
                    cache_hit_rate=85.0,  # Placeholder
                    cpu_usage=health.cpu_usage_percent or 0.0,
                    memory_usage=health.memory_usage_percent or 0.0,
                    disk_usage=health.disk_usage_percent or 0.0
                )
            else:
                # Return defaults if no health data
                return SystemMetrics(
                    api_response_time_p50=0.0,
                    api_response_time_p95=0.0,
                    api_response_time_p99=0.0,
                    error_rate=0.0,
                    uptime_percentage=100.0,
                    total_requests_today=0,
                    successful_analyses=0,
                    failed_analyses=0,
                    cache_hit_rate=0.0,
                    cpu_usage=0.0,
                    memory_usage=0.0,
                    disk_usage=0.0
                )

    async def get_analysis_metrics(self) -> AnalysisMetrics:
        """Get analysis-related metrics from database."""
        async with self.db_manager.session() as session:
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = now - timedelta(days=7)
            month_start = now - timedelta(days=30)

            # Total analyses
            total_result = await session.execute(
                select(func.count(Event.id))
                .where(Event.event_name == "analysis.completed")
            )
            total_analyses = total_result.scalar() or 0

            # Analyses today
            today_result = await session.execute(
                select(func.count(Event.id))
                .where(
                    and_(
                        Event.event_name == "analysis.completed",
                        Event.timestamp >= today_start
                    )
                )
            )
            analyses_today = today_result.scalar() or 0

            # Analyses this week
            week_result = await session.execute(
                select(func.count(Event.id))
                .where(
                    and_(
                        Event.event_name == "analysis.completed",
                        Event.timestamp >= week_start
                    )
                )
            )
            analyses_week = week_result.scalar() or 0

            # Analyses this month
            month_result = await session.execute(
                select(func.count(Event.id))
                .where(
                    and_(
                        Event.event_name == "analysis.completed",
                        Event.timestamp >= month_start
                    )
                )
            )
            analyses_month = month_result.scalar() or 0

            # Average processing time (from event properties)
            # Would need to store processing_time in properties
            avg_processing_time = 2.3  # Placeholder

            # Top component types (would need separate component detection tracking)
            top_component_types = [
                {"type": "resistor", "count": 0},
                {"type": "capacitor", "count": 0},
                {"type": "ic", "count": 0}
            ]

            # Success rate
            failed_result = await session.execute(
                select(func.count(Event.id))
                .where(Event.event_name == "analysis.failed")
            )
            failed_analyses = failed_result.scalar() or 0
            success_rate = ((total_analyses - failed_analyses) / total_analyses * 100) if total_analyses > 0 else 100.0

            return AnalysisMetrics(
                total_analyses=total_analyses,
                analyses_today=analyses_today,
                analyses_week=analyses_week,
                analyses_month=analyses_month,
                avg_processing_time=avg_processing_time,
                top_component_types=top_component_types,
                success_rate=success_rate,
                avg_components_per_analysis=25.3  # Placeholder
            )

    async def get_user_cohort_analysis(self, cohort_type: str = "month") -> List[Dict[str, Any]]:
        """
        Get user cohort analysis from database.

        Args:
            cohort_type: "day", "week", or "month"

        Returns:
            Cohort retention data
        """
        async with self.db_manager.session() as session:
            from src.models.analytics_models import CohortAnalysis

            # Query cohort analysis table
            result = await session.execute(
                select(CohortAnalysis)
                .order_by(CohortAnalysis.cohort_month, CohortAnalysis.age_months)
            )
            cohorts = result.scalars().all()

            cohort_data = []
            current_cohort = None
            retention_by_month = []

            for cohort in cohorts:
                cohort_month_str = cohort.cohort_month.strftime("%Y-%m")

                if current_cohort != cohort_month_str:
                    if current_cohort:
                        cohort_data.append({
                            "cohort": current_cohort,
                            "size": cohort.cohort_size,
                            "retention": retention_by_month
                        })
                    current_cohort = cohort_month_str
                    retention_by_month = []

                retention_by_month.append({
                    "month": cohort.age_months,
                    "retention": cohort.retention_rate,
                    "revenue": cohort.revenue
                })

            return cohort_data

    async def get_feature_flags(self) -> List[Dict[str, Any]]:
        """Get all feature flags from database."""
        async with self.db_manager.session() as session:
            result = await session.execute(
                select(FeatureFlag).order_by(FeatureFlag.created_at)
            )
            flags = result.scalars().all()

            return [
                {
                    "id": flag.id,
                    "key": flag.key,
                    "name": flag.name,
                    "enabled": flag.enabled,
                    "rollout_percentage": flag.rollout_percentage,
                    "environment": flag.environment
                }
                for flag in flags
            ]

    async def update_feature_flag(self, flag_key: str, enabled: bool) -> bool:
        """Update feature flag status."""
        async with self.db_manager.session() as session:
            result = await session.execute(
                select(FeatureFlag).where(FeatureFlag.key == flag_key)
            )
            flag = result.scalar_one_or_none()

            if not flag:
                return False

            flag.enabled = enabled
            flag.updated_at = datetime.utcnow()
            await session.commit()

            logger.info(f"Feature flag {flag_key} set to {enabled}")
            return True

    async def get_ab_tests(self) -> List[Dict[str, Any]]:
        """Get all A/B tests from database."""
        async with self.db_manager.session() as session:
            result = await session.execute(
                select(Experiment)
                .where(Experiment.status != ExperimentStatus.ARCHIVED)
                .order_by(desc(Experiment.created_at))
            )
            experiments = result.scalars().all()

            return [
                {
                    "id": exp.id,
                    "name": exp.name,
                    "status": exp.status.value,
                    "feature_key": exp.feature_key,
                    "traffic_percentage": exp.traffic_percentage,
                    "start_date": exp.start_date.isoformat() if exp.start_date else None,
                    "end_date": exp.end_date.isoformat() if exp.end_date else None
                }
                for exp in experiments
            ]

    async def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active system alerts from database."""
        async with self.db_manager.session() as session:
            result = await session.execute(
                select(SystemAlert)
                .where(SystemAlert.status == AlertStatus.FIRING)
                .order_by(desc(SystemAlert.started_at))
                .limit(50)
            )
            alerts = result.scalars().all()

            return [
                {
                    "id": alert.id,
                    "name": alert.alert_name,
                    "severity": alert.severity.value,
                    "message": alert.message,
                    "started_at": alert.started_at.isoformat(),
                    "source": alert.alert_source
                }
                for alert in alerts
            ]

    async def get_recent_activity(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent admin activity from logs."""
        async with self.db_manager.session() as session:
            result = await session.execute(
                select(ActivityLog)
                .order_by(desc(ActivityLog.timestamp))
                .limit(limit)
            )
            activities = result.scalars().all()

            return [
                {
                    "id": activity.id,
                    "user_id": activity.user_id,
                    "action": activity.action,
                    "resource_type": activity.resource_type,
                    "resource_id": activity.resource_id,
                    "timestamp": activity.timestamp.isoformat(),
                    "success": activity.success
                }
                for activity in activities
            ]


# Singleton instance
admin_dashboard_service_v2 = AdminDashboardServiceV2()
