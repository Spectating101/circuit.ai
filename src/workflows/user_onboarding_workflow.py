"""
User Onboarding and Subscription Workflow

Complete user lifecycle from registration through subscription activation.

Features:
- User registration and verification
- Email verification workflow
- Trial period management
- Subscription activation
- Initial setup and preferences
- Welcome email sequence
- Usage quota initialization
- Feature access configuration
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import uuid
from loguru import logger

from .pcb_analysis_workflow import (
    Workflow, WorkflowEngine, WorkflowStatus, WorkflowStep
)


class OnboardingStage(Enum):
    """User onboarding stages."""
    REGISTRATION = "registration"
    EMAIL_VERIFICATION = "email_verification"
    PROFILE_SETUP = "profile_setup"
    TRIAL_ACTIVATION = "trial_activation"
    SUBSCRIPTION_SELECTION = "subscription_selection"
    PAYMENT_SETUP = "payment_setup"
    ONBOARDING_COMPLETE = "onboarding_complete"


@dataclass
class UserOnboardingData:
    """User onboarding data."""
    user_id: str
    email: str
    name: Optional[str]
    company: Optional[str]
    subscription_tier: str
    trial_enabled: bool
    verification_token: Optional[str]
    onboarding_stage: OnboardingStage


class UserOnboardingWorkflow:
    """Complete user onboarding workflow."""

    def __init__(self):
        """Initialize user onboarding workflow."""
        self.engine = WorkflowEngine()
        self.workflow = self._build_workflow()

        logger.info("UserOnboardingWorkflow initialized")

    def _build_workflow(self) -> Workflow:
        """Build user onboarding workflow."""
        workflow = Workflow(
            workflow_id="user_onboarding_v1",
            name="User Onboarding Pipeline",
            description="Complete user registration and onboarding"
        )

        # Step 1: Create user account
        workflow.add_step(
            step_id="create_account",
            name="Create User Account",
            description="Create user account in database",
            handler=self._create_account,
            depends_on=[]
        )

        # Step 2: Generate verification token
        workflow.add_step(
            step_id="generate_verification",
            name="Generate Verification Token",
            description="Create email verification token",
            handler=self._generate_verification,
            depends_on=["create_account"]
        )

        # Step 3: Send verification email
        workflow.add_step(
            step_id="send_verification_email",
            name="Send Verification Email",
            description="Send email verification link",
            handler=self._send_verification_email,
            depends_on=["generate_verification"]
        )

        # Step 4: Initialize user quota
        workflow.add_step(
            step_id="initialize_quota",
            name="Initialize Usage Quota",
            description="Set up usage limits and quotas",
            handler=self._initialize_quota,
            depends_on=["create_account"]
        )

        # Step 5: Create Stripe customer (parallel with email)
        workflow.add_step(
            step_id="create_stripe_customer",
            name="Create Stripe Customer",
            description="Register user in Stripe",
            handler=self._create_stripe_customer,
            depends_on=["create_account"],
            optional=True  # Non-blocking if Stripe fails
        )

        # Step 6: Set up trial subscription
        workflow.add_step(
            step_id="activate_trial",
            name="Activate Trial Period",
            description="Enable trial features and limits",
            handler=self._activate_trial,
            depends_on=["initialize_quota", "create_stripe_customer"]
        )

        # Step 7: Configure feature access
        workflow.add_step(
            step_id="configure_features",
            name="Configure Feature Access",
            description="Set feature flags and permissions",
            handler=self._configure_features,
            depends_on=["activate_trial"]
        )

        # Step 8: Send welcome email
        workflow.add_step(
            step_id="send_welcome_email",
            name="Send Welcome Email",
            description="Send onboarding welcome email",
            handler=self._send_welcome_email,
            depends_on=["configure_features"],
            optional=True
        )

        # Step 9: Create initial dashboard
        workflow.add_step(
            step_id="setup_dashboard",
            name="Setup User Dashboard",
            description="Initialize dashboard with default widgets",
            handler=self._setup_dashboard,
            depends_on=["configure_features"]
        )

        # Step 10: Log onboarding metrics
        workflow.add_step(
            step_id="log_metrics",
            name="Log Onboarding Metrics",
            description="Record onboarding analytics",
            handler=self._log_metrics,
            depends_on=["setup_dashboard"],
            optional=True
        )

        return workflow

    async def onboard_user(
        self,
        email: str,
        password: str,
        name: Optional[str] = None,
        company: Optional[str] = None,
        subscription_tier: str = "free",
        enable_trial: bool = True
    ) -> str:
        """
        Start user onboarding workflow.

        Args:
            email: User email
            password: User password (will be hashed)
            name: User name
            company: Company name
            subscription_tier: Initial subscription tier
            enable_trial: Enable trial period

        Returns:
            Execution ID
        """
        input_data = {
            'email': email,
            'password': password,
            'name': name,
            'company': company,
            'subscription_tier': subscription_tier,
            'enable_trial': enable_trial,
            'user_id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat()
        }

        execution_id = await self.engine.execute_workflow(
            self.workflow,
            input_data,
            user_id=input_data['user_id']
        )

        return execution_id

    def get_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get onboarding status."""
        return self.engine.get_execution_status(execution_id)

    # Step handlers
    async def _create_account(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create user account."""
        import hashlib

        input_data = context['input']

        # Hash password (in production, use proper bcrypt/argon2)
        password_hash = hashlib.sha256(input_data['password'].encode()).hexdigest()

        # Create user record
        user = {
            'user_id': input_data['user_id'],
            'email': input_data['email'],
            'password_hash': password_hash,
            'name': input_data.get('name'),
            'company': input_data.get('company'),
            'subscription_tier': input_data['subscription_tier'],
            'created_at': datetime.utcnow().isoformat(),
            'email_verified': False,
            'is_active': True
        }

        # Would save to database
        logger.info(f"Created user account: {user['user_id']}")

        return {
            'user': user,
            'user_id': user['user_id']
        }

    async def _generate_verification(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate email verification token."""
        user = context['create_account']['user']

        verification_token = str(uuid.uuid4())
        verification_expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()

        # Would store in database/cache
        return {
            'verification_token': verification_token,
            'verification_expires': verification_expires,
            'verification_url': f"https://circuit.ai/verify?token={verification_token}"
        }

    async def _send_verification_email(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Send verification email."""
        user = context['create_account']['user']
        verification = context['generate_verification']

        # Would use email service (SendGrid, AWS SES, etc.)
        email_data = {
            'to': user['email'],
            'subject': 'Verify your Circuit.AI account',
            'template': 'verification_email',
            'data': {
                'name': user.get('name', 'User'),
                'verification_url': verification['verification_url']
            }
        }

        logger.info(f"Sent verification email to {user['email']}")

        return {
            'email_sent': True,
            'email_id': str(uuid.uuid4())
        }

    async def _initialize_quota(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize user quota."""
        user = context['create_account']['user']
        tier = user['subscription_tier']

        # Set quota based on tier
        quotas = {
            'free': {
                'analyses_per_month': 10,
                'api_calls_per_day': 100,
                'storage_mb': 100
            },
            'pro': {
                'analyses_per_month': 500,
                'api_calls_per_day': 10000,
                'storage_mb': 10000
            },
            'enterprise': {
                'analyses_per_month': -1,  # Unlimited
                'api_calls_per_day': -1,
                'storage_mb': 100000
            }
        }

        user_quota = quotas.get(tier, quotas['free'])

        # Initialize counters
        usage = {
            'analyses_used': 0,
            'api_calls_today': 0,
            'storage_used_mb': 0,
            'period_start': datetime.utcnow().isoformat(),
            'period_end': (datetime.utcnow() + timedelta(days=30)).isoformat()
        }

        logger.info(f"Initialized quota for user {user['user_id']}: {user_quota}")

        return {
            'quota': user_quota,
            'usage': usage
        }

    async def _create_stripe_customer(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create Stripe customer."""
        user = context['create_account']['user']

        # Would call Stripe API
        stripe_customer = {
            'stripe_customer_id': f"cus_{uuid.uuid4().hex[:24]}",
            'email': user['email'],
            'name': user.get('name'),
            'created_at': datetime.utcnow().isoformat()
        }

        logger.info(f"Created Stripe customer: {stripe_customer['stripe_customer_id']}")

        return stripe_customer

    async def _activate_trial(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Activate trial period."""
        input_data = context['input']

        if not input_data['enable_trial']:
            return {'trial_active': False}

        trial_end = datetime.utcnow() + timedelta(days=14)

        trial_data = {
            'trial_active': True,
            'trial_start': datetime.utcnow().isoformat(),
            'trial_end': trial_end.isoformat(),
            'trial_tier': 'pro',  # Give Pro features during trial
            'trial_days_remaining': 14
        }

        logger.info(f"Activated 14-day trial")

        return trial_data

    async def _configure_features(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Configure feature access."""
        user = context['create_account']['user']
        trial = context['activate_trial']

        # Determine features based on tier/trial
        if trial.get('trial_active'):
            tier = 'pro'
        else:
            tier = user['subscription_tier']

        features = {
            'free': [
                'basic_analysis',
                'bom_generation',
                'component_detection'
            ],
            'pro': [
                'basic_analysis',
                'advanced_analysis',
                'bom_generation',
                'component_detection',
                '3d_visualization',
                'batch_processing',
                'api_access',
                'priority_support'
            ],
            'enterprise': [
                'basic_analysis',
                'advanced_analysis',
                'bom_generation',
                'component_detection',
                '3d_visualization',
                'batch_processing',
                'api_access',
                'priority_support',
                'custom_training',
                'white_label',
                'dedicated_support',
                'sla_guarantee'
            ]
        }

        enabled_features = features.get(tier, features['free'])

        feature_flags = {
            feature: True for feature in enabled_features
        }

        logger.info(f"Configured {len(enabled_features)} features for tier: {tier}")

        return {
            'feature_flags': feature_flags,
            'tier': tier
        }

    async def _send_welcome_email(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Send welcome email."""
        user = context['create_account']['user']

        # Would send welcome email with getting started guide
        logger.info(f"Sent welcome email to {user['email']}")

        return {'welcome_email_sent': True}

    async def _setup_dashboard(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Setup user dashboard."""
        user = context['create_account']['user']

        # Create default dashboard configuration
        dashboard = {
            'widgets': [
                {'type': 'quick_start', 'position': 0},
                {'type': 'recent_analyses', 'position': 1},
                {'type': 'usage_stats', 'position': 2},
                {'type': 'feature_highlights', 'position': 3}
            ],
            'theme': 'light',
            'layout': 'default'
        }

        logger.info(f"Setup dashboard for user {user['user_id']}")

        return {'dashboard': dashboard}

    async def _log_metrics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Log onboarding metrics."""
        user = context['create_account']['user']

        # Would send to analytics service
        metrics = {
            'event': 'user_onboarding_complete',
            'user_id': user['user_id'],
            'subscription_tier': user['subscription_tier'],
            'timestamp': datetime.utcnow().isoformat()
        }

        logger.info(f"Logged onboarding metrics for {user['user_id']}")

        return {'metrics_logged': True}


# Singleton instance
user_onboarding_workflow = UserOnboardingWorkflow()
