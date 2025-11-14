"""
Circuit.AI Workflow Infrastructure

Complete workflow orchestration system for all Circuit.AI use cases.

Usage:
    from src.workflows import workflow_manager

    # Analyze PCB
    execution_id = await workflow_manager.analyze_pcb(
        user_id="user123",
        image_path="/path/to/pcb.jpg"
    )

    # Onboard user
    execution_id = await workflow_manager.onboard_user(
        email="user@example.com",
        password="secure_password"
    )

    # Get status
    status = workflow_manager.get_workflow_status(execution_id)
"""

from .workflow_manager import workflow_manager, WorkflowManager, WorkflowType
from .pcb_analysis_workflow import pcb_analysis_workflow, PCBAnalysisWorkflow
from .user_onboarding_workflow import user_onboarding_workflow, UserOnboardingWorkflow
from .billing_workflow import billing_workflow, SubscriptionWorkflow
from .batch_processing_workflow import batch_processing_workflow, BatchProcessingWorkflow
from .content_generation_workflow import content_generation_workflow, ContentGenerationWorkflow
from .notification_workflow import notification_workflow, NotificationWorkflow, NotificationChannel, NotificationPriority

__all__ = [
    # Main interface
    'workflow_manager',
    'WorkflowManager',
    'WorkflowType',

    # Individual workflows
    'pcb_analysis_workflow',
    'PCBAnalysisWorkflow',
    'user_onboarding_workflow',
    'UserOnboardingWorkflow',
    'billing_workflow',
    'SubscriptionWorkflow',
    'batch_processing_workflow',
    'BatchProcessingWorkflow',
    'content_generation_workflow',
    'ContentGenerationWorkflow',
    'notification_workflow',
    'NotificationWorkflow',

    # Enums and types
    'NotificationChannel',
    'NotificationPriority',
]
