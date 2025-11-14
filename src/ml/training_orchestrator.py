"""
Training Orchestration System

Features:
- End-to-end training workflow orchestration
- Integration with model registry and dataset manager
- Experiment tracking with MLflow
- Distributed training support
- Automated hyperparameter tuning
- Training job scheduling
- Resource allocation
- Training callbacks (TensorBoard, checkpoints, early stopping)
- Model evaluation and validation
- Automated model deployment
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
import asyncio
import subprocess
import yaml
import json
from loguru import logger
import mlflow
import mlflow.pytorch

from .model_registry import ModelRegistry, ModelMetrics, ModelFramework, model_registry
from .dataset_manager import DatasetManager, dataset_manager
from .training_pipeline import TrainingConfig, ModelArchitecture


class TrainingStatus(Enum):
    """Training job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TrainingJob:
    """Training job configuration."""
    job_id: str
    name: str
    dataset_id: str
    model_name: str
    architecture: ModelArchitecture
    training_config: TrainingConfig

    # Status
    status: TrainingStatus
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    # Results
    best_map50: Optional[float]
    best_checkpoint: Optional[str]
    mlflow_run_id: Optional[str]

    # Resources
    gpu_count: int
    distributed: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['status'] = self.status.value
        data['architecture'] = self.architecture.value
        data['created_at'] = self.created_at.isoformat()
        if self.started_at:
            data['started_at'] = self.started_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        # training_config is a dataclass
        data['training_config'] = asdict(self.training_config)
        return data


class MLflowTracker:
    """MLflow experiment tracking integration."""

    def __init__(
        self,
        tracking_uri: str = "./mlruns",
        experiment_name: str = "circuit_ai_training"
    ):
        """
        Initialize MLflow tracker.

        Args:
            tracking_uri: MLflow tracking URI
            experiment_name: Experiment name
        """
        self.tracking_uri = tracking_uri
        self.experiment_name = experiment_name

        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)

        logger.info(f"MLflow tracker initialized: {experiment_name}")

    def start_run(
        self,
        run_name: str,
        tags: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Start MLflow run.

        Args:
            run_name: Run name
            tags: Run tags

        Returns:
            Run ID
        """
        run = mlflow.start_run(run_name=run_name, tags=tags or {})
        logger.info(f"Started MLflow run: {run.info.run_id}")
        return run.info.run_id

    def log_params(self, params: Dict[str, Any]):
        """Log parameters."""
        mlflow.log_params(params)

    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None):
        """Log metrics."""
        mlflow.log_metrics(metrics, step=step)

    def log_artifact(self, artifact_path: str):
        """Log artifact file."""
        mlflow.log_artifact(artifact_path)

    def log_model(
        self,
        model: Any,
        artifact_path: str,
        registered_model_name: Optional[str] = None
    ):
        """Log PyTorch model."""
        mlflow.pytorch.log_model(
            model,
            artifact_path,
            registered_model_name=registered_model_name
        )

    def end_run(self):
        """End current run."""
        mlflow.end_run()


class TrainingOrchestrator:
    """Orchestrate end-to-end training workflows."""

    def __init__(
        self,
        model_registry: ModelRegistry,
        dataset_manager: DatasetManager,
        working_dir: str = "./training",
        mlflow_tracking_uri: str = "./mlruns"
    ):
        """
        Initialize training orchestrator.

        Args:
            model_registry: Model registry instance
            dataset_manager: Dataset manager instance
            working_dir: Working directory for training
            mlflow_tracking_uri: MLflow tracking URI
        """
        self.model_registry = model_registry
        self.dataset_manager = dataset_manager

        self.working_dir = Path(working_dir)
        self.working_dir.mkdir(parents=True, exist_ok=True)

        self.mlflow_tracker = MLflowTracker(tracking_uri=mlflow_tracking_uri)

        self.jobs: Dict[str, TrainingJob] = {}
        self._load_jobs()

        logger.info("TrainingOrchestrator initialized")

    def _load_jobs(self):
        """Load training jobs from disk."""
        jobs_file = self.working_dir / "jobs.json"

        if jobs_file.exists():
            with open(jobs_file, 'r') as f:
                data = json.load(f)

            for job_data in data.get('jobs', []):
                # Reconstruct job
                job_data['status'] = TrainingStatus(job_data['status'])
                job_data['architecture'] = ModelArchitecture(job_data['architecture'])
                job_data['created_at'] = datetime.fromisoformat(job_data['created_at'])
                if job_data.get('started_at'):
                    job_data['started_at'] = datetime.fromisoformat(job_data['started_at'])
                if job_data.get('completed_at'):
                    job_data['completed_at'] = datetime.fromisoformat(job_data['completed_at'])

                # Reconstruct training_config
                config_data = job_data.pop('training_config')
                config_data['model_architecture'] = ModelArchitecture(config_data['model_architecture'])
                job_data['training_config'] = TrainingConfig(**config_data)

                job = TrainingJob(**job_data)
                self.jobs[job.job_id] = job

    def _save_jobs(self):
        """Save training jobs to disk."""
        jobs_file = self.working_dir / "jobs.json"

        data = {
            'updated_at': datetime.utcnow().isoformat(),
            'jobs': [job.to_dict() for job in self.jobs.values()]
        }

        with open(jobs_file, 'w') as f:
            json.dump(data, f, indent=2)

    def create_training_job(
        self,
        name: str,
        dataset_id: str,
        model_name: str,
        architecture: ModelArchitecture,
        num_epochs: int = 100,
        batch_size: int = 16,
        learning_rate: float = 0.01,
        image_size: int = 640,
        gpu_count: int = 1,
        distributed: bool = False,
        **training_kwargs
    ) -> str:
        """
        Create new training job.

        Args:
            name: Job name
            dataset_id: Dataset to train on
            model_name: Model name for registry
            architecture: Model architecture
            num_epochs: Number of epochs
            batch_size: Batch size
            learning_rate: Learning rate
            image_size: Input image size
            gpu_count: Number of GPUs
            distributed: Use distributed training
            **training_kwargs: Additional training parameters

        Returns:
            Job ID
        """
        # Validate dataset exists
        dataset = self.dataset_manager.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset not found: {dataset_id}")

        # Create training config
        training_config = TrainingConfig(
            model_architecture=architecture,
            num_epochs=num_epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            weight_decay=training_kwargs.get('weight_decay', 0.0005),
            optimizer=training_kwargs.get('optimizer', 'adam'),
            scheduler=training_kwargs.get('scheduler', 'cosine'),
            augmentation=training_kwargs.get('augmentation', True),
            pretrained=training_kwargs.get('pretrained', True),
            freeze_backbone=training_kwargs.get('freeze_backbone', False),
            num_workers=training_kwargs.get('num_workers', 4),
            early_stopping_patience=training_kwargs.get('early_stopping_patience', 50),
            checkpoint_frequency=training_kwargs.get('checkpoint_frequency', 10),
            mixed_precision=training_kwargs.get('mixed_precision', True)
        )

        # Generate job ID
        job_id = self._generate_job_id(name)

        # Create job
        job = TrainingJob(
            job_id=job_id,
            name=name,
            dataset_id=dataset_id,
            model_name=model_name,
            architecture=architecture,
            training_config=training_config,
            status=TrainingStatus.PENDING,
            created_at=datetime.utcnow(),
            started_at=None,
            completed_at=None,
            best_map50=None,
            best_checkpoint=None,
            mlflow_run_id=None,
            gpu_count=gpu_count,
            distributed=distributed
        )

        # Store job
        self.jobs[job_id] = job
        self._save_jobs()

        logger.info(f"Created training job: {job_id}")

        return job_id

    def _generate_job_id(self, name: str) -> str:
        """Generate unique job ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"{name}_{timestamp}"

    async def run_training_job(self, job_id: str) -> bool:
        """
        Execute training job.

        Args:
            job_id: Job to run

        Returns:
            Success status
        """
        job = self.jobs.get(job_id)

        if not job:
            logger.error(f"Job not found: {job_id}")
            return False

        if job.status != TrainingStatus.PENDING:
            logger.error(f"Job not in pending state: {job_id}")
            return False

        # Update status
        job.status = TrainingStatus.RUNNING
        job.started_at = datetime.utcnow()
        self._save_jobs()

        # Get dataset
        dataset = self.dataset_manager.get_dataset(job.dataset_id)

        # Start MLflow run
        run_id = self.mlflow_tracker.start_run(
            run_name=job.name,
            tags={
                'job_id': job.job_id,
                'architecture': job.architecture.value,
                'dataset': dataset.name
            }
        )
        job.mlflow_run_id = run_id

        # Log parameters
        self.mlflow_tracker.log_params({
            'architecture': job.architecture.value,
            'epochs': job.training_config.num_epochs,
            'batch_size': job.training_config.batch_size,
            'learning_rate': job.training_config.learning_rate,
            'image_size': 640,
            'optimizer': job.training_config.optimizer,
            'dataset': dataset.name,
            'num_classes': dataset.num_classes
        })

        try:
            # Run training
            if job.architecture == ModelArchitecture.YOLOV5:
                result = await self._train_yolov5(job, dataset)
            elif job.architecture == ModelArchitecture.YOLOV8:
                result = await self._train_yolov8(job, dataset)
            else:
                raise NotImplementedError(f"Architecture {job.architecture} not supported")

            # Update job with results
            job.best_map50 = result.get('map50')
            job.best_checkpoint = result.get('best_checkpoint')
            job.status = TrainingStatus.COMPLETED
            job.completed_at = datetime.utcnow()

            # Log final metrics
            self.mlflow_tracker.log_metrics({
                'final_map50': result.get('map50', 0),
                'final_precision': result.get('precision', 0),
                'final_recall': result.get('recall', 0)
            })

            # Log model artifact
            if result.get('best_checkpoint'):
                self.mlflow_tracker.log_artifact(result['best_checkpoint'])

            # Register model in registry
            if result.get('best_checkpoint'):
                await self._register_trained_model(job, result, dataset)

            logger.info(f"Training job completed: {job_id} (mAP50: {result.get('map50', 0):.3f})")

            success = True

        except Exception as e:
            logger.error(f"Training job failed: {job_id} - {e}")
            job.status = TrainingStatus.FAILED
            job.completed_at = datetime.utcnow()
            success = False

        finally:
            self.mlflow_tracker.end_run()
            self._save_jobs()

        return success

    async def _train_yolov8(
        self,
        job: TrainingJob,
        dataset
    ) -> Dict[str, Any]:
        """
        Train YOLOv8 model.

        Args:
            job: Training job
            dataset: Dataset metadata

        Returns:
            Training results
        """
        from ultralytics import YOLO

        # Create output directory
        output_dir = self.working_dir / job.job_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize model
        model_size = job.architecture.value.replace('yolov8', '')  # e.g., 'n', 's', 'm'
        model = YOLO(f'yolov8{model_size}.pt' if job.training_config.pretrained else f'yolov8{model_size}.yaml')

        # Train
        results = model.train(
            data=dataset.config_path,
            epochs=job.training_config.num_epochs,
            batch=job.training_config.batch_size,
            imgsz=640,
            device=list(range(job.gpu_count)) if job.gpu_count > 1 else 0,
            workers=job.training_config.num_workers,
            optimizer=job.training_config.optimizer,
            lr0=job.training_config.learning_rate,
            weight_decay=job.training_config.weight_decay,
            augment=job.training_config.augmentation,
            project=str(output_dir),
            name='train',
            patience=job.training_config.early_stopping_patience,
            save_period=job.training_config.checkpoint_frequency,
            amp=job.training_config.mixed_precision
        )

        # Get best checkpoint
        best_checkpoint = output_dir / 'train' / 'weights' / 'best.pt'

        # Validate
        metrics = model.val()

        return {
            'map50': metrics.box.map50,
            'map50_95': metrics.box.map,
            'precision': metrics.box.mp,
            'recall': metrics.box.mr,
            'best_checkpoint': str(best_checkpoint) if best_checkpoint.exists() else None
        }

    async def _train_yolov5(
        self,
        job: TrainingJob,
        dataset
    ) -> Dict[str, Any]:
        """Train YOLOv5 model."""
        # Similar to YOLOv8 but using YOLOv5 repo
        # Would implement actual YOLOv5 training
        raise NotImplementedError("YOLOv5 training not yet implemented")

    async def _register_trained_model(
        self,
        job: TrainingJob,
        results: Dict[str, Any],
        dataset
    ) -> str:
        """
        Register trained model in model registry.

        Args:
            job: Training job
            results: Training results
            dataset: Dataset metadata

        Returns:
            Model ID
        """
        # Create metrics
        metrics = ModelMetrics(
            map50=results.get('map50', 0),
            map50_95=results.get('map50_95', 0),
            precision=results.get('precision', 0),
            recall=results.get('recall', 0),
            f1_score=2 * (results.get('precision', 0) * results.get('recall', 0)) /
                     (results.get('precision', 0) + results.get('recall', 0) + 1e-8),
            inference_time_ms=0,  # Would measure
            model_size_mb=0,  # Would calculate
            per_class_metrics={}
        )

        # Register model
        model_id = self.model_registry.register_model(
            name=job.model_name,
            version="1.0",
            framework=ModelFramework.PYTORCH,
            architecture=job.architecture.value,
            weights_path=results['best_checkpoint'],
            metrics=metrics,
            dataset_name=dataset.name,
            dataset_version=dataset.version,
            num_classes=dataset.num_classes,
            class_names=dataset.class_names,
            training_config={
                'epochs': job.training_config.num_epochs,
                'batch_size': job.training_config.batch_size,
                'learning_rate': job.training_config.learning_rate
            },
            description=f"Trained on {dataset.name}",
            tags=['yolo', 'pcb', 'component_detection']
        )

        logger.info(f"Registered model: {model_id}")

        return model_id

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get training job status."""
        job = self.jobs.get(job_id)

        if not job:
            return None

        return job.to_dict()

    def list_jobs(
        self,
        status: Optional[TrainingStatus] = None
    ) -> List[TrainingJob]:
        """List training jobs."""
        jobs = list(self.jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]

        jobs.sort(key=lambda j: j.created_at, reverse=True)

        return jobs

    def cancel_job(self, job_id: str) -> bool:
        """Cancel running job."""
        job = self.jobs.get(job_id)

        if not job:
            return False

        if job.status != TrainingStatus.RUNNING:
            return False

        job.status = TrainingStatus.CANCELLED
        job.completed_at = datetime.utcnow()
        self._save_jobs()

        logger.info(f"Cancelled job: {job_id}")

        return True


# Singleton instance
training_orchestrator = TrainingOrchestrator(
    model_registry=model_registry,
    dataset_manager=dataset_manager
)
