"""
Video Processing Pipeline for PCB Inspection

Features:
- Video frame extraction and analysis
- Real-time defect detection in video streams
- Motion analysis for pick-and-place verification
- Solder joint inspection from video
- Assembly process verification
- Time-lapse PCB assembly analysis
- Video annotation and reporting
- Multi-camera synchronization
"""

from typing import Dict, Any, List, Optional, Tuple, Generator
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import cv2
import numpy as np
from pathlib import Path
import tempfile
from loguru import logger
import ffmpeg
from collections import deque


class VideoFormat(Enum):
    """Supported video formats."""
    MP4 = "mp4"
    AVI = "avi"
    MOV = "mov"
    WEBM = "webm"


class DefectType(Enum):
    """Types of defects detectable in video."""
    MISSING_COMPONENT = "missing_component"
    MISALIGNED_COMPONENT = "misaligned_component"
    SOLDER_BRIDGE = "solder_bridge"
    INSUFFICIENT_SOLDER = "insufficient_solder"
    TOMBSTONE = "tombstone"
    WRONG_COMPONENT = "wrong_component"
    CONTAMINATION = "contamination"
    SCRATCH = "scratch"


@dataclass
class VideoMetadata:
    """Video file metadata."""
    duration_seconds: float
    fps: float
    width: int
    height: int
    total_frames: int
    codec: str
    bitrate: int
    file_size_bytes: int


@dataclass
class FrameAnalysis:
    """Analysis results for a single frame."""
    frame_number: int
    timestamp_ms: float
    defects: List[Dict[str, Any]]
    component_count: int
    quality_score: float  # 0-100
    motion_detected: bool
    focus_score: float
    brightness: float


@dataclass
class VideoDefect:
    """Defect detected in video."""
    defect_type: DefectType
    severity: str  # critical, high, medium, low
    frame_number: int
    timestamp_ms: float
    location: Tuple[int, int, int, int]  # x, y, w, h
    confidence: float
    description: str
    thumbnail: Optional[np.ndarray]


@dataclass
class VideoAnalysisReport:
    """Complete video analysis report."""
    video_id: str
    metadata: VideoMetadata
    frame_analyses: List[FrameAnalysis]
    defects: List[VideoDefect]
    overall_quality: float
    assembly_verified: bool
    processing_time_seconds: float
    recommendations: List[str]


class VideoFrameExtractor:
    """Extract frames from video files."""

    def __init__(self):
        """Initialize frame extractor."""
        logger.info("VideoFrameExtractor initialized")

    def extract_metadata(self, video_path: str) -> VideoMetadata:
        """
        Extract video metadata.

        Args:
            video_path: Path to video file

        Returns:
            Video metadata
        """
        cap = cv2.VideoCapture(video_path)

        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))

            # Get file size
            file_size = Path(video_path).stat().st_size

            # Calculate duration
            duration = total_frames / fps if fps > 0 else 0

            # Codec
            codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])

            return VideoMetadata(
                duration_seconds=duration,
                fps=fps,
                width=width,
                height=height,
                total_frames=total_frames,
                codec=codec,
                bitrate=0,  # Would need ffmpeg for accurate bitrate
                file_size_bytes=file_size
            )

        finally:
            cap.release()

    def extract_frames(
        self,
        video_path: str,
        sample_rate: int = 1,
        max_frames: Optional[int] = None
    ) -> Generator[Tuple[int, np.ndarray], None, None]:
        """
        Extract frames from video.

        Args:
            video_path: Path to video file
            sample_rate: Extract every Nth frame
            max_frames: Maximum frames to extract

        Yields:
            (frame_number, frame_image) tuples
        """
        cap = cv2.VideoCapture(video_path)

        try:
            frame_number = 0
            extracted_count = 0

            while True:
                ret, frame = cap.read()

                if not ret:
                    break

                # Sample frames
                if frame_number % sample_rate == 0:
                    yield (frame_number, frame)
                    extracted_count += 1

                    if max_frames and extracted_count >= max_frames:
                        break

                frame_number += 1

        finally:
            cap.release()

    def extract_frame_at_time(
        self,
        video_path: str,
        timestamp_ms: float
    ) -> Optional[np.ndarray]:
        """
        Extract frame at specific timestamp.

        Args:
            video_path: Path to video file
            timestamp_ms: Timestamp in milliseconds

        Returns:
            Frame image or None
        """
        cap = cv2.VideoCapture(video_path)

        try:
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp_ms)
            ret, frame = cap.read()

            if ret:
                return frame

        finally:
            cap.release()

        return None

    async def create_thumbnail(
        self,
        video_path: str,
        output_path: str,
        timestamp_ms: Optional[float] = None
    ):
        """
        Create thumbnail from video.

        Args:
            video_path: Path to video file
            output_path: Output thumbnail path
            timestamp_ms: Timestamp (None = middle of video)
        """
        metadata = self.extract_metadata(video_path)

        if timestamp_ms is None:
            timestamp_ms = (metadata.duration_seconds * 1000) / 2

        frame = self.extract_frame_at_time(video_path, timestamp_ms)

        if frame is not None:
            # Resize to thumbnail
            thumbnail = cv2.resize(frame, (320, 240))
            cv2.imwrite(output_path, thumbnail)


class DefectDetector:
    """Detect defects in PCB video frames."""

    def __init__(self):
        """Initialize defect detector."""
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2()
        logger.info("DefectDetector initialized")

    def detect_defects(
        self,
        frame: np.ndarray,
        reference_frame: Optional[np.ndarray] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect defects in frame.

        Args:
            frame: Video frame
            reference_frame: Reference/golden frame for comparison

        Returns:
            List of detected defects
        """
        defects = []

        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Detect missing components (via template matching or comparison)
        if reference_frame is not None:
            missing_defects = self._detect_missing_components(
                frame,
                reference_frame
            )
            defects.extend(missing_defects)

        # Detect solder issues
        solder_defects = self._detect_solder_defects(gray)
        defects.extend(solder_defects)

        # Detect contamination
        contamination_defects = self._detect_contamination(gray)
        defects.extend(contamination_defects)

        return defects

    def _detect_missing_components(
        self,
        current: np.ndarray,
        reference: np.ndarray
    ) -> List[Dict[str, Any]]:
        """Detect missing components by comparing to reference."""
        defects = []

        # Resize to same size if needed
        if current.shape != reference.shape:
            reference = cv2.resize(reference, (current.shape[1], current.shape[0]))

        # Convert both to grayscale
        current_gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
        reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)

        # Compute difference
        diff = cv2.absdiff(current_gray, reference_gray)

        # Threshold
        _, thresh = cv2.threshold(diff, 50, 255, cv2.THRESH_BINARY)

        # Find contours
        contours, _ = cv2.findContours(
            thresh,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            area = cv2.contourArea(contour)

            # Filter by size (typical component size)
            if 100 < area < 10000:
                x, y, w, h = cv2.boundingRect(contour)

                defects.append({
                    'type': DefectType.MISSING_COMPONENT.value,
                    'location': (x, y, w, h),
                    'confidence': 0.75,
                    'severity': 'high',
                    'area': area
                })

        return defects

    def _detect_solder_defects(self, gray: np.ndarray) -> List[Dict[str, Any]]:
        """Detect solder joint defects."""
        defects = []

        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Detect bright spots (good solder joints should be shiny)
        _, bright_mask = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY)

        # Detect dark areas (insufficient solder)
        _, dark_mask = cv2.threshold(blurred, 80, 255, cv2.THRESH_BINARY_INV)

        # Find solder bridges (connected bright areas)
        kernel = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(bright_mask, kernel, iterations=2)

        contours, _ = cv2.findContours(
            dilated,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            area = cv2.contourArea(contour)

            # Large bright areas might be solder bridges
            if area > 500:
                x, y, w, h = cv2.boundingRect(contour)

                # Check aspect ratio
                aspect_ratio = w / h if h > 0 else 0

                if aspect_ratio > 3 or aspect_ratio < 0.3:
                    defects.append({
                        'type': DefectType.SOLDER_BRIDGE.value,
                        'location': (x, y, w, h),
                        'confidence': 0.65,
                        'severity': 'medium',
                        'area': area
                    })

        return defects

    def _detect_contamination(self, gray: np.ndarray) -> List[Dict[str, Any]]:
        """Detect contamination or foreign objects."""
        defects = []

        # Edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Find unusual patterns
        contours, _ = cv2.findContours(
            edges,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            # Check for irregular shapes (not rectangular)
            perimeter = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.04 * perimeter, True)

            # Irregular shapes with many vertices
            if len(approx) > 8:
                x, y, w, h = cv2.boundingRect(contour)
                area = cv2.contourArea(contour)

                if area > 50:
                    defects.append({
                        'type': DefectType.CONTAMINATION.value,
                        'location': (x, y, w, h),
                        'confidence': 0.50,
                        'severity': 'low',
                        'area': area
                    })

        return defects

    def calculate_focus_score(self, frame: np.ndarray) -> float:
        """
        Calculate focus score using Laplacian variance.

        Args:
            frame: Video frame

        Returns:
            Focus score (higher = better focus)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = laplacian.var()
        return variance


class MotionAnalyzer:
    """Analyze motion in video for pick-and-place verification."""

    def __init__(self, history_size: int = 30):
        """
        Initialize motion analyzer.

        Args:
            history_size: Number of frames to keep in history
        """
        self.frame_history: deque = deque(maxlen=history_size)
        self.optical_flow_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )
        logger.info("MotionAnalyzer initialized")

    def detect_motion(
        self,
        current_frame: np.ndarray,
        previous_frame: Optional[np.ndarray] = None
    ) -> Tuple[bool, float]:
        """
        Detect motion between frames.

        Args:
            current_frame: Current frame
            previous_frame: Previous frame

        Returns:
            (motion_detected, motion_magnitude)
        """
        if previous_frame is None:
            return False, 0.0

        # Convert to grayscale
        current_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
        previous_gray = cv2.cvtColor(previous_frame, cv2.COLOR_BGR2GRAY)

        # Calculate absolute difference
        diff = cv2.absdiff(current_gray, previous_gray)

        # Threshold
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)

        # Calculate motion magnitude
        motion_pixels = np.sum(thresh > 0)
        total_pixels = thresh.shape[0] * thresh.shape[1]
        motion_magnitude = motion_pixels / total_pixels

        motion_detected = motion_magnitude > 0.01  # 1% threshold

        return motion_detected, motion_magnitude

    def track_component_placement(
        self,
        frames: List[np.ndarray]
    ) -> List[Dict[str, Any]]:
        """
        Track component placement events.

        Args:
            frames: Sequence of frames

        Returns:
            List of placement events
        """
        placement_events = []

        for i in range(1, len(frames)):
            motion_detected, magnitude = self.detect_motion(frames[i], frames[i-1])

            if motion_detected and magnitude > 0.05:
                # Significant motion detected
                placement_events.append({
                    'frame_index': i,
                    'motion_magnitude': magnitude,
                    'event_type': 'component_placement'
                })

        return placement_events


class VideoProcessor:
    """Main video processing pipeline."""

    def __init__(self):
        """Initialize video processor."""
        self.extractor = VideoFrameExtractor()
        self.defect_detector = DefectDetector()
        self.motion_analyzer = MotionAnalyzer()
        logger.info("VideoProcessor initialized")

    async def analyze_video(
        self,
        video_path: str,
        reference_image: Optional[np.ndarray] = None,
        sample_rate: int = 5,
        detect_motion: bool = True
    ) -> VideoAnalysisReport:
        """
        Analyze PCB inspection video.

        Args:
            video_path: Path to video file
            reference_image: Reference/golden image for comparison
            sample_rate: Analyze every Nth frame
            detect_motion: Enable motion detection

        Returns:
            Video analysis report
        """
        start_time = datetime.utcnow()

        # Extract metadata
        metadata = self.extractor.extract_metadata(video_path)

        logger.info(
            f"Analyzing video: {metadata.total_frames} frames "
            f"at {metadata.fps} FPS"
        )

        frame_analyses = []
        all_defects = []
        previous_frame = None

        # Process frames
        for frame_num, frame in self.extractor.extract_frames(
            video_path,
            sample_rate=sample_rate
        ):
            # Calculate timestamp
            timestamp_ms = (frame_num / metadata.fps) * 1000

            # Detect motion
            motion_detected = False
            if detect_motion and previous_frame is not None:
                motion_detected, _ = self.motion_analyzer.detect_motion(
                    frame,
                    previous_frame
                )

            # Detect defects
            frame_defects = self.defect_detector.detect_defects(
                frame,
                reference_frame=reference_image
            )

            # Convert to VideoDefect objects
            for defect in frame_defects:
                video_defect = VideoDefect(
                    defect_type=DefectType(defect['type']),
                    severity=defect['severity'],
                    frame_number=frame_num,
                    timestamp_ms=timestamp_ms,
                    location=defect['location'],
                    confidence=defect['confidence'],
                    description=f"{defect['type']} detected",
                    thumbnail=None  # Could extract region
                )
                all_defects.append(video_defect)

            # Calculate quality metrics
            focus_score = self.defect_detector.calculate_focus_score(frame)
            brightness = np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))

            # Quality score (0-100)
            quality_score = 100.0
            quality_score -= len(frame_defects) * 10  # Deduct for defects
            quality_score -= max(0, (180 - focus_score) / 2)  # Deduct for blur
            quality_score = max(0, min(100, quality_score))

            frame_analysis = FrameAnalysis(
                frame_number=frame_num,
                timestamp_ms=timestamp_ms,
                defects=frame_defects,
                component_count=0,  # Would need component detection
                quality_score=quality_score,
                motion_detected=motion_detected,
                focus_score=focus_score,
                brightness=brightness
            )

            frame_analyses.append(frame_analysis)
            previous_frame = frame

            # Log progress
            if frame_num % 100 == 0:
                logger.debug(f"Processed frame {frame_num}/{metadata.total_frames}")

        # Calculate overall quality
        avg_quality = np.mean([fa.quality_score for fa in frame_analyses])

        # Determine if assembly verified
        critical_defects = [
            d for d in all_defects
            if d.severity in ['critical', 'high']
        ]
        assembly_verified = len(critical_defects) == 0

        # Generate recommendations
        recommendations = self._generate_recommendations(
            all_defects,
            frame_analyses
        )

        processing_time = (datetime.utcnow() - start_time).total_seconds()

        return VideoAnalysisReport(
            video_id=Path(video_path).stem,
            metadata=metadata,
            frame_analyses=frame_analyses,
            defects=all_defects,
            overall_quality=avg_quality,
            assembly_verified=assembly_verified,
            processing_time_seconds=processing_time,
            recommendations=recommendations
        )

    def _generate_recommendations(
        self,
        defects: List[VideoDefect],
        frame_analyses: List[FrameAnalysis]
    ) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []

        # Check defect types
        defect_types = {}
        for defect in defects:
            defect_types[defect.defect_type] = defect_types.get(defect.defect_type, 0) + 1

        if DefectType.MISSING_COMPONENT in defect_types:
            recommendations.append(
                f"Found {defect_types[DefectType.MISSING_COMPONENT]} missing components. "
                "Verify pick-and-place programming."
            )

        if DefectType.SOLDER_BRIDGE in defect_types:
            recommendations.append(
                "Solder bridges detected. Review reflow profile and solder paste amount."
            )

        # Check focus issues
        avg_focus = np.mean([fa.focus_score for fa in frame_analyses])
        if avg_focus < 150:
            recommendations.append(
                "Video appears out of focus. Use better camera or adjust focus."
            )

        # Check brightness
        avg_brightness = np.mean([fa.brightness for fa in frame_analyses])
        if avg_brightness < 80:
            recommendations.append("Video is too dark. Improve lighting.")
        elif avg_brightness > 200:
            recommendations.append("Video is overexposed. Reduce lighting.")

        if not recommendations:
            recommendations.append("No significant issues detected. Quality looks good!")

        return recommendations

    async def create_annotated_video(
        self,
        input_path: str,
        output_path: str,
        defects: List[VideoDefect],
        fps: Optional[float] = None
    ):
        """
        Create annotated video with defect markers.

        Args:
            input_path: Input video path
            output_path: Output video path
            defects: Defects to annotate
            fps: Output FPS (None = same as input)
        """
        metadata = self.extractor.extract_metadata(input_path)
        output_fps = fps or metadata.fps

        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(
            output_path,
            fourcc,
            output_fps,
            (metadata.width, metadata.height)
        )

        try:
            # Group defects by frame
            defects_by_frame = {}
            for defect in defects:
                frame_num = defect.frame_number
                if frame_num not in defects_by_frame:
                    defects_by_frame[frame_num] = []
                defects_by_frame[frame_num].append(defect)

            # Process each frame
            for frame_num, frame in self.extractor.extract_frames(input_path, sample_rate=1):
                # Draw defects for this frame
                if frame_num in defects_by_frame:
                    for defect in defects_by_frame[frame_num]:
                        x, y, w, h = defect.location

                        # Color based on severity
                        color = {
                            'critical': (0, 0, 255),  # Red
                            'high': (0, 165, 255),  # Orange
                            'medium': (0, 255, 255),  # Yellow
                            'low': (0, 255, 0)  # Green
                        }.get(defect.severity, (255, 255, 255))

                        # Draw rectangle
                        cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)

                        # Draw label
                        label = f"{defect.defect_type.value}: {defect.confidence:.0%}"
                        cv2.putText(
                            frame,
                            label,
                            (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            color,
                            2
                        )

                out.write(frame)

        finally:
            out.release()

        logger.info(f"Annotated video saved to: {output_path}")


# Singleton instance
video_processor = VideoProcessor()
