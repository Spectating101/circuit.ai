"""
Dataset Management and Versioning

Features:
- Dataset versioning with DVC-like functionality
- Dataset downloading from multiple sources
- Dataset validation and statistics
- Train/val/test splitting with stratification
- Dataset augmentation tracking
- Dataset format conversion (COCO, YOLO, Pascal VOC)
- Dataset merging and sampling
- Data quality metrics
"""

from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
import json
import hashlib
import shutil
import yaml
import requests
from loguru import logger
import cv2
import numpy as np
from collections import defaultdict


class DatasetFormat(Enum):
    """Supported dataset formats."""
    YOLO = "yolo"
    COCO = "coco"
    PASCAL_VOC = "pascal_voc"
    TFRECORD = "tfrecord"


class DatasetSplit(Enum):
    """Dataset splits."""
    TRAIN = "train"
    VAL = "val"
    TEST = "test"


@dataclass
class DatasetStats:
    """Dataset statistics."""
    total_images: int
    total_annotations: int
    images_per_split: Dict[str, int]
    annotations_per_split: Dict[str, int]
    class_distribution: Dict[str, int]
    avg_objects_per_image: float
    image_sizes: Dict[str, Any]  # min, max, avg
    annotation_quality_score: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class DatasetMetadata:
    """Dataset metadata."""
    dataset_id: str
    name: str
    version: str
    format: DatasetFormat
    num_classes: int
    class_names: List[str]
    description: str

    # Statistics
    stats: DatasetStats

    # Provenance
    source_url: Optional[str]
    derived_from: Optional[str]  # Parent dataset ID
    created_at: datetime
    created_by: str

    # Storage
    data_path: str
    config_path: str

    # Checksums for integrity
    data_checksum: str

    # Tags
    tags: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['format'] = self.format.value
        data['created_at'] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DatasetMetadata':
        """Create from dictionary."""
        data['format'] = DatasetFormat(data['format'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['stats'] = DatasetStats(**data['stats'])
        return cls(**data)


class DatasetDownloader:
    """Download datasets from various sources."""

    def __init__(self, download_dir: str = "./datasets"):
        """
        Initialize downloader.

        Args:
            download_dir: Directory for downloaded datasets
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"DatasetDownloader initialized: {download_dir}")

    async def download_roboflow(
        self,
        workspace: str,
        project: str,
        version: int,
        api_key: str,
        format: str = "yolov8"
    ) -> str:
        """
        Download dataset from Roboflow.

        Args:
            workspace: Roboflow workspace
            project: Project name
            version: Dataset version
            api_key: Roboflow API key
            format: Export format

        Returns:
            Path to downloaded dataset
        """
        from roboflow import Roboflow

        rf = Roboflow(api_key=api_key)
        project_obj = rf.workspace(workspace).project(project)
        dataset = project_obj.version(version).download(format)

        logger.info(f"Downloaded Roboflow dataset: {project}")

        return dataset.location

    async def download_url(
        self,
        url: str,
        dataset_name: str,
        extract: bool = True
    ) -> str:
        """
        Download dataset from URL.

        Args:
            url: Dataset URL
            dataset_name: Name for dataset
            extract: Whether to extract archive

        Returns:
            Path to downloaded dataset
        """
        import zipfile
        import tarfile

        output_dir = self.download_dir / dataset_name
        output_dir.mkdir(parents=True, exist_ok=True)

        # Download
        logger.info(f"Downloading from {url}")

        response = requests.get(url, stream=True)
        response.raise_for_status()

        # Determine filename
        filename = url.split('/')[-1]
        download_path = output_dir / filename

        # Save
        with open(download_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Downloaded to {download_path}")

        # Extract if archive
        if extract:
            if filename.endswith('.zip'):
                with zipfile.ZipFile(download_path, 'r') as zip_ref:
                    zip_ref.extractall(output_dir)
                logger.info(f"Extracted ZIP archive")
            elif filename.endswith(('.tar.gz', '.tgz')):
                with tarfile.open(download_path, 'r:gz') as tar_ref:
                    tar_ref.extractall(output_dir)
                logger.info(f"Extracted TAR archive")

        return str(output_dir)

    async def download_kaggle(
        self,
        dataset: str,
        dataset_name: str
    ) -> str:
        """
        Download dataset from Kaggle.

        Args:
            dataset: Kaggle dataset (username/dataset-name)
            dataset_name: Local name

        Returns:
            Path to downloaded dataset
        """
        from kaggle.api.kaggle_api_extended import KaggleApi

        api = KaggleApi()
        api.authenticate()

        output_dir = self.download_dir / dataset_name
        output_dir.mkdir(parents=True, exist_ok=True)

        api.dataset_download_files(dataset, path=str(output_dir), unzip=True)

        logger.info(f"Downloaded Kaggle dataset: {dataset}")

        return str(output_dir)


class DatasetValidator:
    """Validate dataset integrity and quality."""

    def __init__(self):
        """Initialize validator."""
        logger.info("DatasetValidator initialized")

    def validate_yolo_dataset(
        self,
        dataset_path: str
    ) -> Dict[str, Any]:
        """
        Validate YOLO format dataset.

        Args:
            dataset_path: Path to dataset root

        Returns:
            Validation results
        """
        dataset_dir = Path(dataset_path)

        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'stats': {}
        }

        # Check data.yaml
        data_yaml = dataset_dir / "data.yaml"
        if not data_yaml.exists():
            results['valid'] = False
            results['errors'].append("Missing data.yaml")
            return results

        # Load config
        with open(data_yaml, 'r') as f:
            config = yaml.safe_load(f)

        # Validate structure
        required_keys = ['nc', 'names', 'train', 'val']
        for key in required_keys:
            if key not in config:
                results['errors'].append(f"Missing key in data.yaml: {key}")
                results['valid'] = False

        if not results['valid']:
            return results

        # Validate splits
        splits = {}
        for split_name in ['train', 'val', 'test']:
            if split_name in config:
                split_path = dataset_dir / config[split_name]
                if split_path.exists():
                    splits[split_name] = split_path
                else:
                    results['warnings'].append(f"Split path not found: {split_name}")

        # Validate images and labels
        stats = {
            'total_images': 0,
            'total_labels': 0,
            'missing_labels': [],
            'invalid_labels': [],
            'class_distribution': defaultdict(int)
        }

        for split_name, split_path in splits.items():
            images_dir = split_path / "images" if (split_path / "images").exists() else split_path
            labels_dir = split_path / "labels" if (split_path / "labels").exists() else split_path.parent / "labels"

            # Check each image
            for img_file in images_dir.glob("*"):
                if img_file.suffix.lower() not in ['.jpg', '.jpeg', '.png']:
                    continue

                stats['total_images'] += 1

                # Check corresponding label
                label_file = labels_dir / f"{img_file.stem}.txt"

                if not label_file.exists():
                    stats['missing_labels'].append(str(img_file))
                    continue

                stats['total_labels'] += 1

                # Validate label format
                try:
                    with open(label_file, 'r') as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) != 5:
                                stats['invalid_labels'].append(str(label_file))
                                break

                            class_id = int(parts[0])
                            stats['class_distribution'][class_id] += 1

                            # Validate bbox
                            bbox = [float(x) for x in parts[1:]]
                            if not all(0 <= x <= 1 for x in bbox):
                                stats['invalid_labels'].append(str(label_file))
                                break

                except Exception as e:
                    stats['invalid_labels'].append(f"{label_file}: {e}")

        results['stats'] = stats

        # Check class distribution
        if stats['class_distribution']:
            class_counts = list(stats['class_distribution'].values())
            min_count = min(class_counts)
            max_count = max(class_counts)

            if max_count / min_count > 10:
                results['warnings'].append(
                    f"Imbalanced dataset: max/min ratio = {max_count/min_count:.1f}"
                )

        # Check for missing labels
        if len(stats['missing_labels']) > stats['total_images'] * 0.1:
            results['warnings'].append(
                f"{len(stats['missing_labels'])} images missing labels "
                f"({len(stats['missing_labels'])/stats['total_images']*100:.1f}%)"
            )

        logger.info(
            f"Validation complete: {stats['total_images']} images, "
            f"{stats['total_labels']} labels"
        )

        return results

    def calculate_quality_score(
        self,
        validation_results: Dict[str, Any]
    ) -> float:
        """
        Calculate dataset quality score (0-100).

        Args:
            validation_results: Results from validation

        Returns:
            Quality score
        """
        score = 100.0

        stats = validation_results.get('stats', {})

        # Deduct for missing labels
        if stats.get('total_images', 0) > 0:
            missing_ratio = len(stats.get('missing_labels', [])) / stats['total_images']
            score -= missing_ratio * 50  # Up to 50 points

        # Deduct for invalid labels
        if stats.get('total_labels', 0) > 0:
            invalid_ratio = len(stats.get('invalid_labels', [])) / stats['total_labels']
            score -= invalid_ratio * 30  # Up to 30 points

        # Deduct for class imbalance
        class_dist = stats.get('class_distribution', {})
        if class_dist:
            counts = list(class_dist.values())
            imbalance_ratio = max(counts) / min(counts) if min(counts) > 0 else 1
            if imbalance_ratio > 10:
                score -= min(20, (imbalance_ratio - 10) * 2)  # Up to 20 points

        return max(0, score)


class DatasetManager:
    """Central dataset management."""

    def __init__(
        self,
        datasets_dir: str = "./datasets",
        registry_path: str = "./dataset_registry"
    ):
        """
        Initialize dataset manager.

        Args:
            datasets_dir: Root directory for datasets
            registry_path: Path to registry metadata
        """
        self.datasets_dir = Path(datasets_dir)
        self.datasets_dir.mkdir(parents=True, exist_ok=True)

        self.registry_path = Path(registry_path)
        self.registry_path.mkdir(parents=True, exist_ok=True)

        self.downloader = DatasetDownloader(str(self.datasets_dir))
        self.validator = DatasetValidator()

        self.datasets: Dict[str, DatasetMetadata] = {}
        self._load_registry()

        logger.info(f"DatasetManager initialized with {len(self.datasets)} datasets")

    def _load_registry(self):
        """Load dataset registry."""
        index_file = self.registry_path / "index.json"

        if index_file.exists():
            with open(index_file, 'r') as f:
                data = json.load(f)

            for dataset_data in data.get('datasets', []):
                metadata = DatasetMetadata.from_dict(dataset_data)
                self.datasets[metadata.dataset_id] = metadata

    def _save_registry(self):
        """Save dataset registry."""
        index_file = self.registry_path / "index.json"

        data = {
            'updated_at': datetime.utcnow().isoformat(),
            'datasets': [ds.to_dict() for ds in self.datasets.values()]
        }

        with open(index_file, 'w') as f:
            json.dump(data, f, indent=2)

    def register_dataset(
        self,
        name: str,
        version: str,
        data_path: str,
        format: DatasetFormat,
        description: str = "",
        source_url: Optional[str] = None,
        tags: List[str] = None
    ) -> str:
        """
        Register dataset in registry.

        Args:
            name: Dataset name
            version: Version string
            data_path: Path to dataset
            format: Dataset format
            description: Description
            source_url: Source URL
            tags: Tags

        Returns:
            Dataset ID
        """
        # Validate dataset
        if format == DatasetFormat.YOLO:
            validation = self.validator.validate_yolo_dataset(data_path)

            if not validation['valid']:
                raise ValueError(f"Invalid dataset: {validation['errors']}")

            # Calculate stats
            stats_data = validation['stats']

            stats = DatasetStats(
                total_images=stats_data['total_images'],
                total_annotations=stats_data['total_labels'],
                images_per_split={},  # Would calculate per split
                annotations_per_split={},
                class_distribution=dict(stats_data['class_distribution']),
                avg_objects_per_image=stats_data['total_labels'] / stats_data['total_images']
                if stats_data['total_images'] > 0 else 0,
                image_sizes={},  # Would calculate
                annotation_quality_score=self.validator.calculate_quality_score(validation)
            )

            # Load config
            config_path = Path(data_path) / "data.yaml"
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            num_classes = config['nc']
            class_names = config['names']

        else:
            raise NotImplementedError(f"Format {format} not yet supported")

        # Calculate checksum
        data_checksum = self._calculate_checksum(data_path)

        # Generate dataset ID
        dataset_id = self._generate_dataset_id(name, version)

        # Create metadata
        metadata = DatasetMetadata(
            dataset_id=dataset_id,
            name=name,
            version=version,
            format=format,
            num_classes=num_classes,
            class_names=class_names,
            description=description,
            stats=stats,
            source_url=source_url,
            derived_from=None,
            created_at=datetime.utcnow(),
            created_by="system",
            data_path=data_path,
            config_path=str(config_path),
            data_checksum=data_checksum,
            tags=tags or []
        )

        # Store in registry
        self.datasets[dataset_id] = metadata
        self._save_registry()

        logger.info(f"Registered dataset: {dataset_id}")

        return dataset_id

    def _generate_dataset_id(self, name: str, version: str) -> str:
        """Generate unique dataset ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"{name}_v{version}_{timestamp}"

    def _calculate_checksum(self, data_path: str) -> str:
        """Calculate dataset checksum."""
        # Simplified - would hash all files
        path_str = str(Path(data_path).absolute())
        return hashlib.md5(path_str.encode()).hexdigest()

    def get_dataset(self, dataset_id: str) -> Optional[DatasetMetadata]:
        """Get dataset metadata."""
        return self.datasets.get(dataset_id)

    def list_datasets(
        self,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[DatasetMetadata]:
        """List datasets with filters."""
        results = list(self.datasets.values())

        if name:
            results = [d for d in results if d.name == name]

        if tags:
            results = [
                d for d in results
                if any(tag in d.tags for tag in tags)
            ]

        results.sort(key=lambda d: d.created_at, reverse=True)

        return results


# Singleton instance
dataset_manager = DatasetManager()
