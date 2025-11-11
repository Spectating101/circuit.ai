"""
Auto-Scaling Configuration and Management

Features:
- Horizontal Pod Autoscaler (HPA) configuration
- Custom metrics-based scaling
- Predictive scaling
- Cost optimization
- Load prediction
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import numpy as np
from loguru import logger


class ScalingMetric(Enum):
    """Scaling metrics."""
    CPU_UTILIZATION = "cpu"
    MEMORY_UTILIZATION = "memory"
    REQUEST_RATE = "requests_per_second"
    QUEUE_DEPTH = "queue_depth"
    RESPONSE_TIME = "response_time_p95"
    CUSTOM = "custom"


@dataclass
class ScalingPolicy:
    """Auto-scaling policy configuration."""
    metric: ScalingMetric
    target_value: float
    min_replicas: int
    max_replicas: int
    scale_up_cooldown_seconds: int = 60
    scale_down_cooldown_seconds: int = 300
    scale_up_step: int = 2
    scale_down_step: int = 1


@dataclass
class ScalingEvent:
    """Scaling event record."""
    timestamp: datetime
    previous_replicas: int
    new_replicas: int
    reason: str
    metric_value: float
    decision: str  # scale_up, scale_down, no_change


class PredictiveScaler:
    """Predictive auto-scaling based on historical patterns."""

    def __init__(self):
        """Initialize predictive scaler."""
        self.historical_data: List[Dict[str, Any]] = []
        logger.info("PredictiveScaler initialized")

    def add_metric_data(
        self,
        timestamp: datetime,
        metric_name: str,
        value: float
    ):
        """
        Add metric data point.

        Args:
            timestamp: Data timestamp
            metric_name: Metric name
            value: Metric value
        """
        self.historical_data.append({
            "timestamp": timestamp,
            "metric": metric_name,
            "value": value
        })

        # Keep only last 7 days
        cutoff = datetime.utcnow() - timedelta(days=7)
        self.historical_data = [
            d for d in self.historical_data
            if d["timestamp"] > cutoff
        ]

    def predict_load(
        self,
        metric_name: str,
        minutes_ahead: int = 15
    ) -> float:
        """
        Predict future load.

        Args:
            metric_name: Metric to predict
            minutes_ahead: Prediction horizon

        Returns:
            Predicted value
        """
        # Filter data for this metric
        metric_data = [
            d for d in self.historical_data
            if d["metric"] == metric_name
        ]

        if len(metric_data) < 10:
            # Not enough data for prediction
            return 0.0

        # Extract values and timestamps
        values = np.array([d["value"] for d in metric_data])
        timestamps = np.array([d["timestamp"].timestamp() for d in metric_data])

        # Simple linear regression
        X = timestamps.reshape(-1, 1)
        y = values

        # Calculate slope and intercept
        X_mean = X.mean()
        y_mean = y.mean()

        numerator = ((X - X_mean) * (y - y_mean)).sum()
        denominator = ((X - X_mean) ** 2).sum()

        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator

        intercept = y_mean - slope * X_mean

        # Predict future value
        future_timestamp = datetime.utcnow() + timedelta(minutes=minutes_ahead)
        future_ts = future_timestamp.timestamp()

        predicted = slope * future_ts + intercept

        # Add seasonal component (hour of day pattern)
        hour = future_timestamp.hour

        # Peak hours adjustment (9 AM - 5 PM)
        if 9 <= hour <= 17:
            predicted *= 1.5  # 50% higher during business hours
        elif hour < 6 or hour > 22:
            predicted *= 0.5  # 50% lower during night

        return max(0, predicted)

    def recommend_scaling_action(
        self,
        current_replicas: int,
        policy: ScalingPolicy,
        current_metric_value: float,
        predicted_metric_value: float
    ) -> Dict[str, Any]:
        """
        Recommend scaling action based on current and predicted metrics.

        Args:
            current_replicas: Current replica count
            policy: Scaling policy
            current_metric_value: Current metric value
            predicted_metric_value: Predicted future value

        Returns:
            Scaling recommendation
        """
        # Use predicted value for proactive scaling
        metric_value = max(current_metric_value, predicted_metric_value)

        utilization = metric_value / policy.target_value

        # Scaling thresholds
        scale_up_threshold = 0.8  # Scale up at 80% of target
        scale_down_threshold = 0.5  # Scale down below 50% of target

        if utilization > scale_up_threshold:
            # Need more capacity
            new_replicas = min(
                current_replicas + policy.scale_up_step,
                policy.max_replicas
            )

            return {
                "action": "scale_up",
                "current_replicas": current_replicas,
                "recommended_replicas": new_replicas,
                "reason": f"Utilization {utilization:.1%} exceeds threshold",
                "metric_value": metric_value,
                "predicted_value": predicted_metric_value,
                "is_predictive": predicted_metric_value > current_metric_value
            }

        elif utilization < scale_down_threshold and current_replicas > policy.min_replicas:
            # Can reduce capacity
            new_replicas = max(
                current_replicas - policy.scale_down_step,
                policy.min_replicas
            )

            return {
                "action": "scale_down",
                "current_replicas": current_replicas,
                "recommended_replicas": new_replicas,
                "reason": f"Utilization {utilization:.1%} below threshold",
                "metric_value": metric_value
            }

        else:
            return {
                "action": "no_change",
                "current_replicas": current_replicas,
                "recommended_replicas": current_replicas,
                "reason": f"Utilization {utilization:.1%} within acceptable range",
                "metric_value": metric_value
            }


class ScalingController:
    """Scaling controller and decision engine."""

    def __init__(self):
        """Initialize scaling controller."""
        self.policies: Dict[str, ScalingPolicy] = {}
        self.scaler = PredictiveScaler()
        self.scaling_history: List[ScalingEvent] = []
        self.last_scale_up: Optional[datetime] = None
        self.last_scale_down: Optional[datetime] = None
        logger.info("ScalingController initialized")

    def register_policy(self, service_name: str, policy: ScalingPolicy):
        """
        Register scaling policy for service.

        Args:
            service_name: Service name
            policy: Scaling policy
        """
        self.policies[service_name] = policy
        logger.info(f"Registered scaling policy for {service_name}")

    async def evaluate_scaling(
        self,
        service_name: str,
        current_replicas: int,
        metrics: Dict[str, float]
    ) -> Optional[int]:
        """
        Evaluate and return recommended replica count.

        Args:
            service_name: Service name
            current_replicas: Current replica count
            metrics: Current metric values

        Returns:
            Recommended replica count or None if no change
        """
        policy = self.policies.get(service_name)
        if not policy:
            logger.warning(f"No scaling policy for {service_name}")
            return None

        metric_value = metrics.get(policy.metric.value, 0)

        # Add to historical data
        self.scaler.add_metric_data(
            datetime.utcnow(),
            policy.metric.value,
            metric_value
        )

        # Get prediction
        predicted_value = self.scaler.predict_load(policy.metric.value)

        # Get recommendation
        recommendation = self.scaler.recommend_scaling_action(
            current_replicas,
            policy,
            metric_value,
            predicted_value
        )

        action = recommendation["action"]

        # Check cooldown periods
        if action == "scale_up":
            if self.last_scale_up:
                time_since = (datetime.utcnow() - self.last_scale_up).total_seconds()
                if time_since < policy.scale_up_cooldown_seconds:
                    logger.info(f"Scale up in cooldown ({time_since:.0f}s < {policy.scale_up_cooldown_seconds}s)")
                    return None

        elif action == "scale_down":
            if self.last_scale_down:
                time_since = (datetime.utcnow() - self.last_scale_down).total_seconds()
                if time_since < policy.scale_down_cooldown_seconds:
                    logger.info(f"Scale down in cooldown ({time_since:.0f}s < {policy.scale_down_cooldown_seconds}s)")
                    return None

        # Record scaling event
        if action != "no_change":
            event = ScalingEvent(
                timestamp=datetime.utcnow(),
                previous_replicas=current_replicas,
                new_replicas=recommendation["recommended_replicas"],
                reason=recommendation["reason"],
                metric_value=metric_value,
                decision=action
            )

            self.scaling_history.append(event)

            # Update last scaling timestamp
            if action == "scale_up":
                self.last_scale_up = datetime.utcnow()
            else:
                self.last_scale_down = datetime.utcnow()

            logger.info(f"Scaling {service_name}: {action} from {current_replicas} to {recommendation['recommended_replicas']}")

            return recommendation["recommended_replicas"]

        return None

    def get_scaling_history(
        self,
        service_name: str,
        hours: int = 24
    ) -> List[ScalingEvent]:
        """
        Get scaling history.

        Args:
            service_name: Service name
            hours: Hours of history

        Returns:
            Scaling events
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        return [
            event for event in self.scaling_history
            if event.timestamp > cutoff
        ]

    def get_cost_estimate(
        self,
        service_name: str,
        replica_count: int,
        hours: int = 720  # 30 days
    ) -> float:
        """
        Estimate cost for replica count.

        Args:
            service_name: Service name
            replica_count: Number of replicas
            hours: Hours to estimate

        Returns:
            Estimated cost in USD
        """
        # Cost per replica per hour (example: $0.05/hour for small instance)
        cost_per_replica_hour = 0.05

        total_cost = replica_count * hours * cost_per_replica_hour

        return total_cost

    def optimize_for_cost(
        self,
        service_name: str,
        performance_target: float,
        budget_usd: float
    ) -> Dict[str, Any]:
        """
        Optimize scaling for cost while meeting performance target.

        Args:
            service_name: Service name
            performance_target: Performance target (e.g., 95th percentile response time)
            budget_usd: Monthly budget

        Returns:
            Optimization recommendation
        """
        policy = self.policies.get(service_name)
        if not policy:
            return {}

        # Calculate max replicas within budget
        monthly_hours = 720
        cost_per_replica_month = 0.05 * monthly_hours

        max_affordable_replicas = int(budget_usd / cost_per_replica_month)

        # Recommend replica count
        recommended = max(
            policy.min_replicas,
            min(max_affordable_replicas, policy.max_replicas)
        )

        estimated_cost = self.get_cost_estimate(service_name, recommended)

        return {
            "service": service_name,
            "recommended_replicas": recommended,
            "estimated_monthly_cost": estimated_cost,
            "budget": budget_usd,
            "under_budget": estimated_cost <= budget_usd,
            "savings": max(0, budget_usd - estimated_cost)
        }


# Default scaling policies
DEFAULT_POLICIES = {
    "api": ScalingPolicy(
        metric=ScalingMetric.CPU_UTILIZATION,
        target_value=70.0,  # 70% CPU
        min_replicas=2,
        max_replicas=20,
        scale_up_cooldown_seconds=60,
        scale_down_cooldown_seconds=300
    ),
    "ml-service": ScalingPolicy(
        metric=ScalingMetric.QUEUE_DEPTH,
        target_value=100.0,  # 100 jobs in queue
        min_replicas=1,
        max_replicas=10,
        scale_up_cooldown_seconds=30,  # Scale up faster
        scale_down_cooldown_seconds=600  # Scale down slower
    ),
    "websocket": ScalingPolicy(
        metric=ScalingMetric.REQUEST_RATE,
        target_value=1000.0,  # 1000 req/sec per replica
        min_replicas=2,
        max_replicas=15
    )
}


# Singleton instance
scaling_controller = ScalingController()

# Register default policies
for service, policy in DEFAULT_POLICIES.items():
    scaling_controller.register_policy(service, policy)
