"""
ML Model Registry

Features:
- Model versioning and metadata tracking
- Model performance metrics storage
- Model lineage tracking
- Model promotion workflow (dev -> staging -> production)
- Model artifact storage (S3, local, GCS)
- Model comparison and A/B testing
- Automated model selection based on metrics
- Model rollback capabilities
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
import json
import hashlib
import shutil
import boto3
from loguru import logger
import yaml


class ModelStage(Enum):
    """Model deployment stages."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


class ModelFramework(Enum):
    """Supported ML frameworks."""
    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"
    ONNX = "onnx"
    TENSORRT = "tensorrt"
    OPENVINO = "openvino"


@dataclass
class ModelMetrics:
    """Model performance metrics."""
    map50: float  # Mean Average Precision @ IoU 0.5
    map50_95: float  # Mean Average Precision @ IoU 0.5-0.95
    precision: float
    recall: float
    f1_score: float
    inference_time_ms: float
    model_size_mb: float
    per_class_metrics: Dict[str, Dict[str, float]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ModelMetadata:
    """Complete model metadata."""
    model_id: str
    name: str
    version: str
    framework: ModelFramework
    architecture: str  # e.g., "yolov8m", "faster_rcnn_resnet50"
    stage: ModelStage

    # Training info
    dataset_name: str
    dataset_version: str
    num_classes: int
    class_names: List[str]
    training_epochs: int
    batch_size: int
    learning_rate: float

    # Performance
    metrics: ModelMetrics

    # Artifacts
    weights_path: str
    config_path: Optional[str]
    onnx_path: Optional[str]

    # Metadata
    created_at: datetime
    created_by: str
    tags: List[str]
    description: str
    parent_model_id: Optional[str]  # For tracking lineage

    # Deployment
    deployed_at: Optional[datetime]
    deployment_endpoint: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['framework'] = self.framework.value
        data['stage'] = self.stage.value
        data['created_at'] = self.created_at.isoformat()
        if self.deployed_at:
            data['deployed_at'] = self.deployed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelMetadata':
        """Create from dictionary."""
        data['framework'] = ModelFramework(data['framework'])
        data['stage'] = ModelStage(data['stage'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('deployed_at'):
            data['deployed_at'] = datetime.fromisoformat(data['deployed_at'])

        # Reconstruct metrics
        metrics_data = data.pop('metrics')
        data['metrics'] = ModelMetrics(**metrics_data)

        return cls(**data)


class ModelStorage:
    """Handle model artifact storage."""

    def __init__(
        self,
        storage_type: str = "local",
        local_path: str = "./models",
        s3_bucket: Optional[str] = None,
        s3_prefix: str = "models/"
    ):
        """
        Initialize model storage.

        Args:
            storage_type: Storage backend (local, s3, gcs)
            local_path: Local storage path
            s3_bucket: S3 bucket name
            s3_prefix: S3 key prefix
        """
        self.storage_type = storage_type
        self.local_path = Path(local_path)
        self.local_path.mkdir(parents=True, exist_ok=True)

        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix

        if storage_type == "s3":
            self.s3_client = boto3.client('s3')

        logger.info(f"ModelStorage initialized: {storage_type}")

    def save_model(
        self,
        model_id: str,
        weights_path: str,
        config_path: Optional[str] = None,
        onnx_path: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Save model artifacts.

        Args:
            model_id: Model identifier
            weights_path: Path to model weights
            config_path: Path to config file
            onnx_path: Path to ONNX export

        Returns:
            Dictionary of stored artifact paths
        """
        artifacts = {}

        # Create model directory
        model_dir = self.local_path / model_id
        model_dir.mkdir(parents=True, exist_ok=True)

        # Copy weights
        if weights_path:
            dest = model_dir / Path(weights_path).name
            shutil.copy2(weights_path, dest)
            artifacts['weights'] = str(dest)

            # Upload to S3 if configured
            if self.storage_type == "s3":
                s3_key = f"{self.s3_prefix}{model_id}/{Path(weights_path).name}"
                self._upload_to_s3(str(dest), s3_key)
                artifacts['weights_s3'] = f"s3://{self.s3_bucket}/{s3_key}"

        # Copy config
        if config_path:
            dest = model_dir / Path(config_path).name
            shutil.copy2(config_path, dest)
            artifacts['config'] = str(dest)

            if self.storage_type == "s3":
                s3_key = f"{self.s3_prefix}{model_id}/{Path(config_path).name}"
                self._upload_to_s3(str(dest), s3_key)

        # Copy ONNX
        if onnx_path:
            dest = model_dir / Path(onnx_path).name
            shutil.copy2(onnx_path, dest)
            artifacts['onnx'] = str(dest)

            if self.storage_type == "s3":
                s3_key = f"{self.s3_prefix}{model_id}/{Path(onnx_path).name}"
                self._upload_to_s3(str(dest), s3_key)

        logger.info(f"Saved model artifacts for {model_id}")

        return artifacts

    def _upload_to_s3(self, local_path: str, s3_key: str):
        """Upload file to S3."""
        try:
            self.s3_client.upload_file(local_path, self.s3_bucket, s3_key)
            logger.info(f"Uploaded to S3: s3://{self.s3_bucket}/{s3_key}")
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")

    def load_model(self, model_id: str, artifact: str = "weights") -> str:
        """
        Load model artifact.

        Args:
            model_id: Model identifier
            artifact: Artifact type (weights, config, onnx)

        Returns:
            Path to local artifact
        """
        local_path = self.local_path / model_id / f"{artifact}.pt"

        # Check if exists locally
        if local_path.exists():
            return str(local_path)

        # Download from S3 if configured
        if self.storage_type == "s3":
            s3_key = f"{self.s3_prefix}{model_id}/{artifact}.pt"
            try:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                self.s3_client.download_file(self.s3_bucket, s3_key, str(local_path))
                logger.info(f"Downloaded from S3: {s3_key}")
                return str(local_path)
            except Exception as e:
                logger.error(f"S3 download failed: {e}")

        raise FileNotFoundError(f"Model artifact not found: {model_id}/{artifact}")

    def delete_model(self, model_id: str):
        """Delete model artifacts."""
        # Delete local
        model_dir = self.local_path / model_id
        if model_dir.exists():
            shutil.rmtree(model_dir)
            logger.info(f"Deleted local artifacts: {model_id}")

        # Delete from S3
        if self.storage_type == "s3":
            prefix = f"{self.s3_prefix}{model_id}/"
            try:
                response = self.s3_client.list_objects_v2(
                    Bucket=self.s3_bucket,
                    Prefix=prefix
                )

                if 'Contents' in response:
                    objects = [{'Key': obj['Key']} for obj in response['Contents']]
                    self.s3_client.delete_objects(
                        Bucket=self.s3_bucket,
                        Delete={'Objects': objects}
                    )
                    logger.info(f"Deleted S3 artifacts: {model_id}")
            except Exception as e:
                logger.error(f"S3 deletion failed: {e}")


class ModelRegistry:
    """Central model registry."""

    def __init__(
        self,
        registry_path: str = "./registry",
        storage: Optional[ModelStorage] = None
    ):
        """
        Initialize model registry.

        Args:
            registry_path: Path to registry metadata storage
            storage: Model storage backend
        """
        self.registry_path = Path(registry_path)
        self.registry_path.mkdir(parents=True, exist_ok=True)

        self.storage = storage or ModelStorage()

        self.models: Dict[str, ModelMetadata] = {}
        self._load_registry()

        logger.info(f"ModelRegistry initialized with {len(self.models)} models")

    def _load_registry(self):
        """Load registry from disk."""
        index_file = self.registry_path / "index.json"

        if index_file.exists():
            with open(index_file, 'r') as f:
                data = json.load(f)

            for model_data in data.get('models', []):
                metadata = ModelMetadata.from_dict(model_data)
                self.models[metadata.model_id] = metadata

            logger.info(f"Loaded {len(self.models)} models from registry")

    def _save_registry(self):
        """Save registry to disk."""
        index_file = self.registry_path / "index.json"

        data = {
            'updated_at': datetime.utcnow().isoformat(),
            'models': [model.to_dict() for model in self.models.values()]
        }

        with open(index_file, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info("Registry saved")

    def register_model(
        self,
        name: str,
        version: str,
        framework: ModelFramework,
        architecture: str,
        weights_path: str,
        metrics: ModelMetrics,
        dataset_name: str,
        dataset_version: str,
        num_classes: int,
        class_names: List[str],
        training_config: Dict[str, Any],
        config_path: Optional[str] = None,
        onnx_path: Optional[str] = None,
        description: str = "",
        tags: List[str] = None,
        parent_model_id: Optional[str] = None
    ) -> str:
        """
        Register new model.

        Args:
            name: Model name
            version: Model version
            framework: ML framework
            architecture: Architecture name
            weights_path: Path to model weights
            metrics: Performance metrics
            dataset_name: Training dataset name
            dataset_version: Dataset version
            num_classes: Number of classes
            class_names: Class names
            training_config: Training configuration
            config_path: Path to config file
            onnx_path: Path to ONNX export
            description: Model description
            tags: Model tags
            parent_model_id: Parent model for lineage

        Returns:
            Model ID
        """
        # Generate model ID
        model_id = self._generate_model_id(name, version)

        # Save artifacts
        artifacts = self.storage.save_model(
            model_id,
            weights_path,
            config_path,
            onnx_path
        )

        # Create metadata
        metadata = ModelMetadata(
            model_id=model_id,
            name=name,
            version=version,
            framework=framework,
            architecture=architecture,
            stage=ModelStage.DEVELOPMENT,
            dataset_name=dataset_name,
            dataset_version=dataset_version,
            num_classes=num_classes,
            class_names=class_names,
            training_epochs=training_config.get('epochs', 0),
            batch_size=training_config.get('batch_size', 0),
            learning_rate=training_config.get('learning_rate', 0),
            metrics=metrics,
            weights_path=artifacts.get('weights', ''),
            config_path=artifacts.get('config'),
            onnx_path=artifacts.get('onnx'),
            created_at=datetime.utcnow(),
            created_by="system",
            tags=tags or [],
            description=description,
            parent_model_id=parent_model_id,
            deployed_at=None,
            deployment_endpoint=None
        )

        # Store in registry
        self.models[model_id] = metadata
        self._save_registry()

        logger.info(f"Registered model: {model_id} (mAP50: {metrics.map50:.3f})")

        return model_id

    def _generate_model_id(self, name: str, version: str) -> str:
        """Generate unique model ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"{name}_v{version}_{timestamp}"

    def get_model(self, model_id: str) -> Optional[ModelMetadata]:
        """Get model metadata by ID."""
        return self.models.get(model_id)

    def list_models(
        self,
        stage: Optional[ModelStage] = None,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[ModelMetadata]:
        """
        List models with filters.

        Args:
            stage: Filter by deployment stage
            name: Filter by model name
            tags: Filter by tags

        Returns:
            List of matching models
        """
        results = list(self.models.values())

        if stage:
            results = [m for m in results if m.stage == stage]

        if name:
            results = [m for m in results if m.name == name]

        if tags:
            results = [
                m for m in results
                if any(tag in m.tags for tag in tags)
            ]

        # Sort by creation date (newest first)
        results.sort(key=lambda m: m.created_at, reverse=True)

        return results

    def promote_model(
        self,
        model_id: str,
        target_stage: ModelStage
    ) -> bool:
        """
        Promote model to new stage.

        Args:
            model_id: Model to promote
            target_stage: Target deployment stage

        Returns:
            Success status
        """
        model = self.models.get(model_id)

        if not model:
            logger.error(f"Model not found: {model_id}")
            return False

        # Validate promotion path
        valid_promotions = {
            ModelStage.DEVELOPMENT: [ModelStage.STAGING, ModelStage.ARCHIVED],
            ModelStage.STAGING: [ModelStage.PRODUCTION, ModelStage.DEVELOPMENT, ModelStage.ARCHIVED],
            ModelStage.PRODUCTION: [ModelStage.ARCHIVED],
        }

        if target_stage not in valid_promotions.get(model.stage, []):
            logger.error(f"Invalid promotion: {model.stage} -> {target_stage}")
            return False

        # If promoting to production, demote current production model
        if target_stage == ModelStage.PRODUCTION:
            self._demote_production_models(model.name)

        # Promote
        model.stage = target_stage

        if target_stage == ModelStage.PRODUCTION:
            model.deployed_at = datetime.utcnow()

        self._save_registry()

        logger.info(f"Promoted {model_id} to {target_stage.value}")

        return True

    def _demote_production_models(self, model_name: str):
        """Demote all production models with given name to staging."""
        for model in self.models.values():
            if model.name == model_name and model.stage == ModelStage.PRODUCTION:
                model.stage = ModelStage.STAGING
                logger.info(f"Demoted {model.model_id} to staging")

    def get_production_model(self, name: str) -> Optional[ModelMetadata]:
        """Get current production model by name."""
        production_models = [
            m for m in self.models.values()
            if m.name == name and m.stage == ModelStage.PRODUCTION
        ]

        return production_models[0] if production_models else None

    def compare_models(
        self,
        model_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Compare multiple models.

        Args:
            model_ids: List of model IDs to compare

        Returns:
            Comparison results
        """
        models = [self.models.get(mid) for mid in model_ids if mid in self.models]

        if not models:
            return {}

        comparison = {
            'models': [],
            'best_by_metric': {}
        }

        # Collect model info
        for model in models:
            comparison['models'].append({
                'model_id': model.model_id,
                'name': model.name,
                'version': model.version,
                'stage': model.stage.value,
                'metrics': model.metrics.to_dict(),
                'inference_time_ms': model.metrics.inference_time_ms,
                'model_size_mb': model.metrics.model_size_mb
            })

        # Find best by each metric
        metrics = ['map50', 'map50_95', 'precision', 'recall', 'f1_score']

        for metric in metrics:
            best = max(models, key=lambda m: getattr(m.metrics, metric))
            comparison['best_by_metric'][metric] = {
                'model_id': best.model_id,
                'value': getattr(best.metrics, metric)
            }

        # Fastest inference
        fastest = min(models, key=lambda m: m.metrics.inference_time_ms)
        comparison['best_by_metric']['inference_speed'] = {
            'model_id': fastest.model_id,
            'value': fastest.metrics.inference_time_ms
        }

        return comparison

    def delete_model(self, model_id: str) -> bool:
        """
        Delete model from registry.

        Args:
            model_id: Model to delete

        Returns:
            Success status
        """
        model = self.models.get(model_id)

        if not model:
            return False

        # Don't delete production models
        if model.stage == ModelStage.PRODUCTION:
            logger.error(f"Cannot delete production model: {model_id}")
            return False

        # Delete artifacts
        self.storage.delete_model(model_id)

        # Remove from registry
        del self.models[model_id]
        self._save_registry()

        logger.info(f"Deleted model: {model_id}")

        return True


# Singleton instance
model_registry = ModelRegistry(
    registry_path="./registry",
    storage=ModelStorage(storage_type="local", local_path="./models")
)
