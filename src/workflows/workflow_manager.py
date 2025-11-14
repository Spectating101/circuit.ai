"""
Central Workflow Manager

Unified interface for all Circuit.AI workflows.

Features:
- Centralized workflow orchestration
- Cross-workflow coordination
- Workflow monitoring and metrics
- Error handling and recovery
- Workflow scheduling
- Workflow history and audit
- Performance analytics
- Resource management
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import asyncio
import uuid
from loguru import logger

from .pcb_analysis_workflow import pcb_analysis_workflow, PCBAnalysisWorkflow
from .user_onboarding_workflow import user_onboarding_workflow, UserOnboardingWorkflow
from .billing_workflow import billing_workflow, SubscriptionWorkflow
from .batch_processing_workflow import batch_processing_workflow, BatchProcessingWorkflow
from .content_generation_workflow import content_generation_workflow, ContentGenerationWorkflow
from .notification_workflow import notification_workflow, NotificationWorkflow, NotificationChannel, NotificationPriority


class WorkflowType(Enum):
    """Available workflow types."""
    PCB_ANALYSIS = "pcb_analysis"
    USER_ONBOARDING = "user_onboarding"
    SUBSCRIPTION_CREATE = "subscription_create"
    SUBSCRIPTION_UPGRADE = "subscription_upgrade"
    SUBSCRIPTION_CANCEL = "subscription_cancel"
    BATCH_PROCESSING = "batch_processing"
    EDUCATIONAL_CONTENT = "educational_content"
    REPAIR_GUIDE = "repair_guide"
    TUTORIAL = "tutorial"
    NOTIFICATION = "notification"
    WEBHOOK = "webhook"


@dataclass
class WorkflowExecution:
    """Workflow execution record."""
    execution_id: str
    workflow_type: WorkflowType
    user_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]]
    error: Optional[str]


class WorkflowManager:
    """Central workflow management system."""

    def __init__(self):
        """Initialize workflow manager."""
        # Workflow instances
        self.pcb_workflow = pcb_analysis_workflow
        self.onboarding_workflow = user_onboarding_workflow
        self.billing_workflow = billing_workflow
        self.batch_workflow = batch_processing_workflow
        self.content_workflow = content_generation_workflow
        self.notification_workflow = notification_workflow

        # Execution tracking
        self.executions: Dict[str, WorkflowExecution] = {}

        # Metrics
        self.total_executions = 0
        self.successful_executions = 0
        self.failed_executions = 0

        logger.info("WorkflowManager initialized")

    # PCB Analysis Workflows
    async def analyze_pcb(
        self,
        user_id: str,
        image_path: str,
        options: Dict[str, Any] = None
    ) -> str:
        """
        Start PCB analysis workflow.

        Args:
            user_id: User ID
            image_path: Path to PCB image
            options: Analysis options

        Returns:
            Execution ID
        """
        execution_id = await self.pcb_workflow.analyze_pcb(
            image_path,
            user_id,
            options
        )

        self._track_execution(
            execution_id,
            WorkflowType.PCB_ANALYSIS,
            user_id,
            {'image_path': image_path, 'options': options}
        )

        logger.info(f"Started PCB analysis workflow: {execution_id}")

        return execution_id

    async def analyze_pcb_batch(
        self,
        user_id: str,
        image_paths: List[str],
        options: Dict[str, Any] = None
    ) -> str:
        """
        Start batch PCB analysis workflow.

        Args:
            user_id: User ID
            image_paths: List of image paths
            options: Analysis options

        Returns:
            Job ID
        """
        job_id = await self.batch_workflow.submit_batch_job(
            user_id,
            image_paths,
            options
        )

        self._track_execution(
            job_id,
            WorkflowType.BATCH_PROCESSING,
            user_id,
            {'image_paths': image_paths, 'options': options}
        )

        logger.info(f"Started batch processing workflow: {job_id}")

        return job_id

    # User Management Workflows
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
            password: User password
            name: User name
            company: Company name
            subscription_tier: Initial subscription tier
            enable_trial: Enable trial period

        Returns:
            Execution ID
        """
        execution_id = await self.onboarding_workflow.onboard_user(
            email,
            password,
            name,
            company,
            subscription_tier,
            enable_trial
        )

        self._track_execution(
            execution_id,
            WorkflowType.USER_ONBOARDING,
            "system",
            {'email': email}
        )

        logger.info(f"Started user onboarding workflow: {execution_id}")

        return execution_id

    # Billing Workflows
    async def create_subscription(
        self,
        user_id: str,
        tier: str,
        payment_method_id: str,
        billing_cycle: str = "monthly"
    ) -> str:
        """
        Start subscription creation workflow.

        Args:
            user_id: User ID
            tier: Subscription tier
            payment_method_id: Payment method
            billing_cycle: Billing cycle

        Returns:
            Execution ID
        """
        execution_id = await self.billing_workflow.create_subscription(
            user_id,
            tier,
            payment_method_id,
            billing_cycle
        )

        self._track_execution(
            execution_id,
            WorkflowType.SUBSCRIPTION_CREATE,
            user_id,
            {'tier': tier, 'billing_cycle': billing_cycle}
        )

        logger.info(f"Started subscription creation workflow: {execution_id}")

        return execution_id

    async def upgrade_subscription(
        self,
        user_id: str,
        new_tier: str
    ) -> str:
        """
        Start subscription upgrade workflow.

        Args:
            user_id: User ID
            new_tier: New subscription tier

        Returns:
            Execution ID
        """
        execution_id = await self.billing_workflow.upgrade_subscription(
            user_id,
            new_tier
        )

        self._track_execution(
            execution_id,
            WorkflowType.SUBSCRIPTION_UPGRADE,
            user_id,
            {'new_tier': new_tier}
        )

        logger.info(f"Started subscription upgrade workflow: {execution_id}")

        return execution_id

    async def cancel_subscription(
        self,
        user_id: str,
        reason: Optional[str] = None,
        immediate: bool = False
    ) -> str:
        """
        Start subscription cancellation workflow.

        Args:
            user_id: User ID
            reason: Cancellation reason
            immediate: Cancel immediately

        Returns:
            Execution ID
        """
        execution_id = await self.billing_workflow.cancel_subscription(
            user_id,
            reason,
            immediate
        )

        self._track_execution(
            execution_id,
            WorkflowType.SUBSCRIPTION_CANCEL,
            user_id,
            {'reason': reason, 'immediate': immediate}
        )

        logger.info(f"Started subscription cancellation workflow: {execution_id}")

        return execution_id

    # Content Generation Workflows
    async def generate_educational_content(
        self,
        component_data: Dict[str, Any],
        level: str = "beginner",
        language: str = "en"
    ) -> str:
        """
        Start educational content generation workflow.

        Args:
            component_data: Component information
            level: Difficulty level
            language: Content language

        Returns:
            Execution ID
        """
        execution_id = await self.content_workflow.generate_educational_content(
            component_data,
            level,
            language
        )

        self._track_execution(
            execution_id,
            WorkflowType.EDUCATIONAL_CONTENT,
            "system",
            {'level': level, 'language': language}
        )

        logger.info(f"Started educational content generation: {execution_id}")

        return execution_id

    async def generate_repair_guide(
        self,
        pcb_analysis: Dict[str, Any],
        issue_description: str
    ) -> str:
        """
        Start repair guide generation workflow.

        Args:
            pcb_analysis: PCB analysis results
            issue_description: Description of the issue

        Returns:
            Execution ID
        """
        execution_id = await self.content_workflow.generate_repair_guide(
            pcb_analysis,
            issue_description
        )

        self._track_execution(
            execution_id,
            WorkflowType.REPAIR_GUIDE,
            "system",
            {'issue': issue_description}
        )

        logger.info(f"Started repair guide generation: {execution_id}")

        return execution_id

    async def generate_tutorial(
        self,
        topic: str,
        prerequisites: List[str] = None
    ) -> str:
        """
        Start tutorial generation workflow.

        Args:
            topic: Tutorial topic
            prerequisites: Required knowledge

        Returns:
            Execution ID
        """
        execution_id = await self.content_workflow.generate_tutorial(
            topic,
            prerequisites
        )

        self._track_execution(
            execution_id,
            WorkflowType.TUTORIAL,
            "system",
            {'topic': topic}
        )

        logger.info(f"Started tutorial generation: {execution_id}")

        return execution_id

    # Notification Workflows
    async def send_notification(
        self,
        user_id: str,
        channel: NotificationChannel,
        template_id: str,
        data: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> str:
        """
        Send notification to user.

        Args:
            user_id: User ID
            channel: Notification channel
            template_id: Template to use
            data: Template data
            priority: Notification priority

        Returns:
            Execution ID
        """
        execution_id = await self.notification_workflow.send_notification(
            user_id,
            channel,
            template_id,
            data,
            priority
        )

        self._track_execution(
            execution_id,
            WorkflowType.NOTIFICATION,
            user_id,
            {'channel': channel.value, 'template_id': template_id}
        )

        logger.info(f"Started notification workflow: {execution_id}")

        return execution_id

    async def deliver_webhook(
        self,
        webhook_url: str,
        event_type: str,
        payload: Dict[str, Any],
        secret: Optional[str] = None
    ) -> str:
        """
        Deliver webhook event.

        Args:
            webhook_url: Webhook endpoint
            event_type: Event type
            payload: Event payload
            secret: Webhook secret

        Returns:
            Execution ID
        """
        execution_id = await self.notification_workflow.deliver_webhook(
            webhook_url,
            event_type,
            payload,
            secret
        )

        self._track_execution(
            execution_id,
            WorkflowType.WEBHOOK,
            "system",
            {'event_type': event_type, 'webhook_url': webhook_url}
        )

        logger.info(f"Started webhook delivery: {execution_id}")

        return execution_id

    # Status and Monitoring
    def get_workflow_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Get workflow execution status.

        Args:
            execution_id: Execution ID

        Returns:
            Status information
        """
        # Check local tracking
        if execution_id in self.executions:
            execution = self.executions[execution_id]

            # Get detailed status from appropriate workflow
            workflow_status = None

            if execution.workflow_type == WorkflowType.PCB_ANALYSIS:
                workflow_status = self.pcb_workflow.get_status(execution_id)
            elif execution.workflow_type == WorkflowType.USER_ONBOARDING:
                workflow_status = self.onboarding_workflow.get_status(execution_id)
            elif execution.workflow_type == WorkflowType.BATCH_PROCESSING:
                workflow_status = self.batch_workflow.get_batch_status(execution_id)
            # Add other workflow types as needed

            return {
                'execution_id': execution_id,
                'workflow_type': execution.workflow_type.value,
                'user_id': execution.user_id,
                'status': execution.status,
                'started_at': execution.started_at.isoformat(),
                'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
                'detailed_status': workflow_status
            }

        return None

    def get_user_workflows(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all workflows for a user.

        Args:
            user_id: User ID

        Returns:
            List of workflow executions
        """
        user_executions = [
            {
                'execution_id': exec.execution_id,
                'workflow_type': exec.workflow_type.value,
                'status': exec.status,
                'started_at': exec.started_at.isoformat(),
                'completed_at': exec.completed_at.isoformat() if exec.completed_at else None
            }
            for exec in self.executions.values()
            if exec.user_id == user_id
        ]

        return sorted(user_executions, key=lambda x: x['started_at'], reverse=True)

    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get workflow system metrics.

        Returns:
            System metrics
        """
        active_executions = sum(
            1 for exec in self.executions.values()
            if exec.status in ['pending', 'running']
        )

        return {
            'total_executions': self.total_executions,
            'successful_executions': self.successful_executions,
            'failed_executions': self.failed_executions,
            'success_rate': (
                self.successful_executions / self.total_executions * 100
                if self.total_executions > 0 else 0
            ),
            'active_executions': active_executions,
            'workflow_types': {
                wf_type.value: sum(
                    1 for exec in self.executions.values()
                    if exec.workflow_type == wf_type
                )
                for wf_type in WorkflowType
            }
        }

    def get_workflow_history(
        self,
        workflow_type: Optional[WorkflowType] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get workflow execution history.

        Args:
            workflow_type: Filter by workflow type
            limit: Maximum results

        Returns:
            List of executions
        """
        executions = self.executions.values()

        if workflow_type:
            executions = [
                exec for exec in executions
                if exec.workflow_type == workflow_type
            ]

        sorted_executions = sorted(
            executions,
            key=lambda x: x.started_at,
            reverse=True
        )[:limit]

        return [
            {
                'execution_id': exec.execution_id,
                'workflow_type': exec.workflow_type.value,
                'user_id': exec.user_id,
                'status': exec.status,
                'started_at': exec.started_at.isoformat(),
                'completed_at': exec.completed_at.isoformat() if exec.completed_at else None,
                'error': exec.error
            }
            for exec in sorted_executions
        ]

    # Private methods
    def _track_execution(
        self,
        execution_id: str,
        workflow_type: WorkflowType,
        user_id: str,
        input_data: Dict[str, Any]
    ):
        """Track workflow execution."""
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_type=workflow_type,
            user_id=user_id,
            status='pending',
            started_at=datetime.utcnow(),
            completed_at=None,
            input_data=input_data,
            output_data=None,
            error=None
        )

        self.executions[execution_id] = execution
        self.total_executions += 1

    async def _update_execution(
        self,
        execution_id: str,
        status: str,
        output_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """Update workflow execution status."""
        if execution_id in self.executions:
            execution = self.executions[execution_id]
            execution.status = status
            execution.output_data = output_data
            execution.error = error

            if status in ['completed', 'failed']:
                execution.completed_at = datetime.utcnow()

                if status == 'completed':
                    self.successful_executions += 1
                else:
                    self.failed_executions += 1


# Singleton instance
workflow_manager = WorkflowManager()
