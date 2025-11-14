"""
Data Labeling Tool for Creating Training Datasets

Features:
- Image annotation interface
- Bounding box labeling
- Class assignment
- Dataset export (YOLO, COCO formats)
- Annotation validation
- Label quality checks
- Collaborative labeling
- Annotation statistics
- Auto-labeling suggestions
- Label review and correction
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json
import cv2
import numpy as np
from loguru import logger
import yaml


@dataclass
class BoundingBox:
    """Bounding box annotation."""
    x: float
    y: float
    width: float
    height: float
    class_id: int
    class_name: str
    confidence: float = 1.0  # For auto-labels
    annotator: str = "human"


@dataclass
class ImageAnnotation:
    """Annotation for single image."""
    image_id: str
    image_path: str
    image_width: int
    image_height: int
    boxes: List[BoundingBox]
    annotated_by: str
    annotated_at: datetime
    reviewed: bool = False
    review_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['annotated_at'] = self.annotated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImageAnnotation':
        """Create from dictionary."""
        data['annotated_at'] = datetime.fromisoformat(data['annotated_at'])
        data['boxes'] = [BoundingBox(**box) for box in data['boxes']]
        return cls(**data)


class AnnotationValidator:
    """Validate annotation quality."""

    def __init__(self):
        """Initialize validator."""
        logger.info("AnnotationValidator initialized")

    def validate_annotation(
        self,
        annotation: ImageAnnotation
    ) -> Dict[str, Any]:
        """
        Validate annotation quality.

        Args:
            annotation: Image annotation

        Returns:
            Validation results
        """
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'quality_score': 100.0
        }

        # Check for boxes
        if not annotation.boxes:
            results['warnings'].append("No boxes annotated")
            results['quality_score'] -= 20

        # Check each box
        for idx, box in enumerate(annotation.boxes):
            # Validate bbox coordinates
            if not self._validate_bbox_coordinates(box, annotation):
                results['errors'].append(
                    f"Box {idx}: Invalid coordinates (outside image bounds)"
                )
                results['valid'] = False
                results['quality_score'] -= 15

            # Check box size
            if box.width < 5 or box.height < 5:
                results['warnings'].append(
                    f"Box {idx}: Very small box ({box.width:.1f}x{box.height:.1f})"
                )
                results['quality_score'] -= 5

            # Check aspect ratio
            aspect_ratio = box.width / box.height if box.height > 0 else 0
            if aspect_ratio > 10 or aspect_ratio < 0.1:
                results['warnings'].append(
                    f"Box {idx}: Extreme aspect ratio ({aspect_ratio:.2f})"
                )
                results['quality_score'] -= 5

        # Check for overlapping boxes
        overlaps = self._find_overlapping_boxes(annotation.boxes)
        if overlaps:
            results['warnings'].append(
                f"Found {len(overlaps)} overlapping box pairs"
            )
            results['quality_score'] -= len(overlaps) * 3

        results['quality_score'] = max(0, results['quality_score'])

        return results

    def _validate_bbox_coordinates(
        self,
        box: BoundingBox,
        annotation: ImageAnnotation
    ) -> bool:
        """Check if bbox is within image bounds."""
        return (
            0 <= box.x < annotation.image_width and
            0 <= box.y < annotation.image_height and
            box.x + box.width <= annotation.image_width and
            box.y + box.height <= annotation.image_height
        )

    def _find_overlapping_boxes(
        self,
        boxes: List[BoundingBox],
        iou_threshold: float = 0.5
    ) -> List[Tuple[int, int]]:
        """Find overlapping boxes."""
        overlaps = []

        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                box1 = boxes[i]
                box2 = boxes[j]

                # Skip if different classes
                if box1.class_id != box2.class_id:
                    continue

                # Calculate IoU
                iou = self._calculate_iou(box1, box2)

                if iou > iou_threshold:
                    overlaps.append((i, j))

        return overlaps

    def _calculate_iou(self, box1: BoundingBox, box2: BoundingBox) -> float:
        """Calculate IoU between boxes."""
        # Convert to xyxy format
        box1_xyxy = [
            box1.x,
            box1.y,
            box1.x + box1.width,
            box1.y + box1.height
        ]
        box2_xyxy = [
            box2.x,
            box2.y,
            box2.x + box2.width,
            box2.y + box2.height
        ]

        # Calculate intersection
        x1 = max(box1_xyxy[0], box2_xyxy[0])
        y1 = max(box1_xyxy[1], box2_xyxy[1])
        x2 = min(box1_xyxy[2], box2_xyxy[2])
        y2 = min(box1_xyxy[3], box2_xyxy[3])

        intersection = max(0, x2 - x1) * max(0, y2 - y1)

        # Calculate union
        area1 = box1.width * box1.height
        area2 = box2.width * box2.height
        union = area1 + area2 - intersection

        if union == 0:
            return 0.0

        return intersection / union


class LabelingSession:
    """Manage labeling session."""

    def __init__(
        self,
        session_id: str,
        class_names: List[str],
        output_dir: str
    ):
        """
        Initialize labeling session.

        Args:
            session_id: Session identifier
            class_names: List of class names
            output_dir: Output directory for annotations
        """
        self.session_id = session_id
        self.class_names = class_names
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.annotations: Dict[str, ImageAnnotation] = {}
        self.validator = AnnotationValidator()

        self._load_session()

        logger.info(
            f"LabelingSession {session_id} initialized with "
            f"{len(self.annotations)} existing annotations"
        )

    def _load_session(self):
        """Load existing annotations."""
        session_file = self.output_dir / f"{self.session_id}.json"

        if session_file.exists():
            with open(session_file, 'r') as f:
                data = json.load(f)

            for ann_data in data.get('annotations', []):
                annotation = ImageAnnotation.from_dict(ann_data)
                self.annotations[annotation.image_id] = annotation

    def _save_session(self):
        """Save session data."""
        session_file = self.output_dir / f"{self.session_id}.json"

        data = {
            'session_id': self.session_id,
            'class_names': self.class_names,
            'total_annotations': len(self.annotations),
            'last_updated': datetime.utcnow().isoformat(),
            'annotations': [ann.to_dict() for ann in self.annotations.values()]
        }

        with open(session_file, 'w') as f:
            json.dump(data, f, indent=2)

    def add_annotation(
        self,
        image_id: str,
        image_path: str,
        boxes: List[BoundingBox],
        annotator: str = "user"
    ) -> bool:
        """
        Add image annotation.

        Args:
            image_id: Image identifier
            image_path: Path to image
            boxes: Bounding boxes
            annotator: Annotator name

        Returns:
            Success status
        """
        # Load image to get dimensions
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"Failed to load image: {image_path}")
            return False

        height, width = image.shape[:2]

        # Create annotation
        annotation = ImageAnnotation(
            image_id=image_id,
            image_path=image_path,
            image_width=width,
            image_height=height,
            boxes=boxes,
            annotated_by=annotator,
            annotated_at=datetime.utcnow()
        )

        # Validate
        validation = self.validator.validate_annotation(annotation)

        if not validation['valid']:
            logger.error(f"Invalid annotation: {validation['errors']}")
            return False

        if validation['warnings']:
            logger.warning(f"Annotation warnings: {validation['warnings']}")

        # Store annotation
        self.annotations[image_id] = annotation
        self._save_session()

        logger.info(
            f"Added annotation for {image_id} "
            f"(quality score: {validation['quality_score']:.1f})"
        )

        return True

    def export_yolo(self, output_dir: str) -> str:
        """
        Export annotations in YOLO format.

        Args:
            output_dir: Output directory

        Returns:
            Path to dataset
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Create directory structure
        images_dir = output_path / "images"
        labels_dir = output_path / "labels"
        images_dir.mkdir(exist_ok=True)
        labels_dir.mkdir(exist_ok=True)

        # Export each annotation
        for annotation in self.annotations.values():
            # Copy image
            import shutil
            image_dest = images_dir / Path(annotation.image_path).name
            shutil.copy2(annotation.image_path, image_dest)

            # Create label file
            label_file = labels_dir / f"{annotation.image_id}.txt"

            with open(label_file, 'w') as f:
                for box in annotation.boxes:
                    # Convert to YOLO format (normalized xywh)
                    x_center = (box.x + box.width / 2) / annotation.image_width
                    y_center = (box.y + box.height / 2) / annotation.image_height
                    width_norm = box.width / annotation.image_width
                    height_norm = box.height / annotation.image_height

                    f.write(
                        f"{box.class_id} {x_center:.6f} {y_center:.6f} "
                        f"{width_norm:.6f} {height_norm:.6f}\n"
                    )

        # Create data.yaml
        data_yaml = {
            'path': str(output_path.absolute()),
            'train': str(images_dir),
            'val': str(images_dir),  # Would split in real implementation
            'nc': len(self.class_names),
            'names': self.class_names
        }

        with open(output_path / "data.yaml", 'w') as f:
            yaml.dump(data_yaml, f)

        logger.info(f"Exported {len(self.annotations)} annotations to YOLO format")

        return str(output_path)

    def get_statistics(self) -> Dict[str, Any]:
        """Get annotation statistics."""
        total_boxes = sum(len(ann.boxes) for ann in self.annotations.values())

        # Boxes per class
        class_counts = {name: 0 for name in self.class_names}
        for annotation in self.annotations.values():
            for box in annotation.boxes:
                if box.class_name in class_counts:
                    class_counts[box.class_name] += 1

        return {
            'total_images': len(self.annotations),
            'total_boxes': total_boxes,
            'avg_boxes_per_image': total_boxes / len(self.annotations)
            if self.annotations else 0,
            'class_distribution': class_counts,
            'reviewed_count': sum(1 for ann in self.annotations.values() if ann.reviewed)
        }


class AutoLabeler:
    """Suggest labels using pre-trained model."""

    def __init__(self, model):
        """
        Initialize auto-labeler.

        Args:
            model: Pre-trained detection model
        """
        self.model = model
        logger.info("AutoLabeler initialized")

    async def suggest_labels(
        self,
        image_path: str,
        confidence_threshold: float = 0.3
    ) -> List[BoundingBox]:
        """
        Suggest labels for image.

        Args:
            image_path: Path to image
            confidence_threshold: Confidence threshold

        Returns:
            List of suggested boxes
        """
        # Run inference
        results = self.model.predict(image_path, conf=confidence_threshold)[0]

        suggestions = []

        if results.boxes:
            for box in results.boxes:
                bbox = box.xyxy[0].tolist()
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])

                suggestions.append(BoundingBox(
                    x=bbox[0],
                    y=bbox[1],
                    width=bbox[2] - bbox[0],
                    height=bbox[3] - bbox[1],
                    class_id=class_id,
                    class_name=self.model.names[class_id],
                    confidence=confidence,
                    annotator="auto"
                ))

        logger.info(f"Generated {len(suggestions)} label suggestions")

        return suggestions


# Example usage
class LabelingManager:
    """High-level labeling management."""

    def __init__(self, class_names: List[str]):
        """Initialize manager."""
        self.class_names = class_names
        self.sessions: Dict[str, LabelingSession] = {}
        logger.info("LabelingManager initialized")

    def create_session(
        self,
        session_id: str,
        output_dir: str
    ) -> LabelingSession:
        """Create new labeling session."""
        session = LabelingSession(
            session_id=session_id,
            class_names=self.class_names,
            output_dir=output_dir
        )

        self.sessions[session_id] = session

        return session

    def get_session(self, session_id: str) -> Optional[LabelingSession]:
        """Get existing session."""
        return self.sessions.get(session_id)
