"""
AI-Powered Anomaly Detection for PCB Analysis

Detects:
- Unusual component placements
- Potential design flaws
- Manufacturing defects
- Thermal hotspots
- Signal integrity issues
- Power distribution anomalies
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.cluster import DBSCAN
import cv2
from loguru import logger


class AnomalySeverity(Enum):
    """Anomaly severity levels."""
    CRITICAL = "critical"  # Will cause failure
    HIGH = "high"  # Likely to cause issues
    MEDIUM = "medium"  # May cause issues
    LOW = "low"  # Unlikely to cause issues
    INFO = "info"  # Informational only


class AnomalyType(Enum):
    """Types of anomalies."""
    COMPONENT_PLACEMENT = "component_placement"
    THERMAL_HOTSPOT = "thermal_hotspot"
    POWER_DISTRIBUTION = "power_distribution"
    SIGNAL_INTEGRITY = "signal_integrity"
    MANUFACTURING_DEFECT = "manufacturing_defect"
    DESIGN_RULE_VIOLATION = "design_rule_violation"
    OBSOLETE_COMPONENT = "obsolete_component"
    OVER_SPECIFICATION = "over_specification"
    UNDER_SPECIFICATION = "under_specification"


@dataclass
class Anomaly:
    """Detected anomaly."""
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    confidence: float  # 0-1
    title: str
    description: str
    location: Optional[Dict[str, Any]]  # x, y coordinates or component ID
    affected_components: List[str]
    root_cause: str
    recommended_fix: str
    impact: str
    detection_method: str


@dataclass
class PredictiveMaintenanceScore:
    """Predictive maintenance assessment."""
    overall_score: float  # 0-100, higher = better
    reliability_score: float  # 0-100
    longevity_estimate_years: float
    failure_probability: float  # 0-1
    mtbf_hours: float  # Mean Time Between Failures
    weak_points: List[Dict[str, Any]]
    recommendations: List[str]


class AnomalyDetector:
    """AI-powered anomaly detection for PCB analysis."""

    def __init__(self):
        """Initialize anomaly detector."""
        self.isolation_forest = IsolationForest(
            contamination=0.1,
            random_state=42
        )
        self.dbscan = DBSCAN(eps=0.3, min_samples=2)
        logger.info("AnomalyDetector initialized")

    async def detect_anomalies(
        self,
        pcb_analysis: Dict[str, Any],
        pcb_image: Optional[np.ndarray] = None
    ) -> List[Anomaly]:
        """
        Detect all types of anomalies in PCB.

        Args:
            pcb_analysis: PCB analysis results
            pcb_image: Original PCB image (optional)

        Returns:
            List of detected anomalies
        """
        anomalies = []

        # Run all detection methods in parallel
        component_anomalies = await self._detect_component_anomalies(pcb_analysis)
        anomalies.extend(component_anomalies)

        if pcb_image is not None:
            thermal_anomalies = await self._detect_thermal_anomalies(pcb_image, pcb_analysis)
            anomalies.extend(thermal_anomalies)

            manufacturing_defects = await self._detect_manufacturing_defects(pcb_image)
            anomalies.extend(manufacturing_defects)

        power_anomalies = await self._detect_power_anomalies(pcb_analysis)
        anomalies.extend(power_anomalies)

        signal_anomalies = await self._detect_signal_integrity_issues(pcb_analysis)
        anomalies.extend(signal_anomalies)

        design_violations = await self._detect_design_rule_violations(pcb_analysis)
        anomalies.extend(design_violations)

        # Sort by severity
        severity_order = {
            AnomalySeverity.CRITICAL: 0,
            AnomalySeverity.HIGH: 1,
            AnomalySeverity.MEDIUM: 2,
            AnomalySeverity.LOW: 3,
            AnomalySeverity.INFO: 4
        }
        anomalies.sort(key=lambda a: (severity_order[a.severity], -a.confidence))

        logger.info(f"Detected {len(anomalies)} anomalies")
        return anomalies

    async def _detect_component_anomalies(
        self,
        pcb_analysis: Dict[str, Any]
    ) -> List[Anomaly]:
        """Detect component-related anomalies using ML."""
        anomalies = []
        components = pcb_analysis.get('components', [])

        if not components:
            return anomalies

        # Extract features for anomaly detection
        features = []
        for comp in components:
            feature_vector = [
                comp.get('bounding_box', {}).get('width', 0),
                comp.get('bounding_box', {}).get('height', 0),
                comp.get('confidence', 0),
                len(comp.get('pins', [])),
            ]
            features.append(feature_vector)

        features_array = np.array(features)

        # Detect outliers using Isolation Forest
        if len(features_array) > 5:  # Need sufficient data
            predictions = self.isolation_forest.fit_predict(features_array)

            for i, pred in enumerate(predictions):
                if pred == -1:  # Anomaly detected
                    comp = components[i]
                    anomalies.append(Anomaly(
                        anomaly_type=AnomalyType.COMPONENT_PLACEMENT,
                        severity=AnomalySeverity.MEDIUM,
                        confidence=0.7,
                        title=f"Unusual Component Placement: {comp.get('type', 'Unknown')}",
                        description=f"Component at position ({comp.get('bounding_box', {}).get('x', 0)}, {comp.get('bounding_box', {}).get('y', 0)}) has unusual characteristics compared to others.",
                        location=comp.get('bounding_box'),
                        affected_components=[comp.get('id', str(i))],
                        root_cause="Component dimensions or placement significantly differ from statistical norm",
                        recommended_fix="Verify component placement and orientation against design files",
                        impact="May indicate placement error or component substitution",
                        detection_method="Isolation Forest ML algorithm"
                    ))

        # Check for component clustering issues
        if len(components) > 10:
            positions = np.array([
                [comp.get('bounding_box', {}).get('x', 0),
                 comp.get('bounding_box', {}).get('y', 0)]
                for comp in components
            ])

            clusters = self.dbscan.fit_predict(positions)
            unique_clusters = set(clusters)

            # Check for overcrowding
            for cluster_id in unique_clusters:
                if cluster_id == -1:  # Noise points
                    continue

                cluster_components = [
                    components[i] for i, c in enumerate(clusters) if c == cluster_id
                ]

                if len(cluster_components) > 15:  # Too many components in small area
                    anomalies.append(Anomaly(
                        anomaly_type=AnomalyType.COMPONENT_PLACEMENT,
                        severity=AnomalySeverity.HIGH,
                        confidence=0.85,
                        title="Component Overcrowding Detected",
                        description=f"Cluster contains {len(cluster_components)} components in close proximity, increasing thermal and manufacturing risks.",
                        location=None,
                        affected_components=[c.get('id', str(i)) for i, c in enumerate(cluster_components)],
                        root_cause="Insufficient spacing between components",
                        recommended_fix="Redistribute components to improve airflow and manufacturing yield",
                        impact="Increased thermal stress, reduced manufacturing yield, harder repairs",
                        detection_method="DBSCAN clustering algorithm"
                    ))

        return anomalies

    async def _detect_thermal_anomalies(
        self,
        pcb_image: np.ndarray,
        pcb_analysis: Dict[str, Any]
    ) -> List[Anomaly]:
        """Detect potential thermal hotspots."""
        anomalies = []

        # Simulate thermal analysis based on component power ratings
        components = pcb_analysis.get('components', [])
        high_power_components = [
            c for c in components
            if c.get('power_rating', 0) > 1.0  # > 1W
        ]

        for comp in high_power_components:
            bbox = comp.get('bounding_box', {})

            # Check proximity to other high-power components
            nearby_high_power = 0
            comp_x = bbox.get('x', 0)
            comp_y = bbox.get('y', 0)

            for other in high_power_components:
                if other == comp:
                    continue

                other_bbox = other.get('bounding_box', {})
                distance = np.sqrt(
                    (comp_x - other_bbox.get('x', 0)) ** 2 +
                    (comp_y - other_bbox.get('y', 0)) ** 2
                )

                if distance < 50:  # pixels, close proximity
                    nearby_high_power += 1

            if nearby_high_power >= 2:
                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.THERMAL_HOTSPOT,
                    severity=AnomalySeverity.HIGH,
                    confidence=0.8,
                    title="Thermal Hotspot Risk",
                    description=f"High-power component ({comp.get('type')}, {comp.get('power_rating')}W) is near {nearby_high_power} other high-power components.",
                    location=bbox,
                    affected_components=[comp.get('id', '')],
                    root_cause="Multiple high-power components in close proximity without adequate cooling",
                    recommended_fix="Add heatsinks, improve airflow, or redistribute high-power components",
                    impact="Potential overheating, reduced component lifespan, thermal runaway risk",
                    detection_method="Power density analysis"
                ))

        return anomalies

    async def _detect_manufacturing_defects(
        self,
        pcb_image: np.ndarray
    ) -> List[Anomaly]:
        """Detect manufacturing defects using computer vision."""
        anomalies = []

        # Convert to grayscale
        gray = cv2.cvtColor(pcb_image, cv2.COLOR_BGR2GRAY) if len(pcb_image.shape) == 3 else pcb_image

        # Detect scratches using edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Look for long, thin contours (potential scratches)
        for contour in contours:
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)

            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter ** 2)

                # Long thin objects have low circularity
                if circularity < 0.1 and area > 500:
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = max(w, h) / min(w, h)

                    if aspect_ratio > 10:  # Very elongated
                        anomalies.append(Anomaly(
                            anomaly_type=AnomalyType.MANUFACTURING_DEFECT,
                            severity=AnomalySeverity.MEDIUM,
                            confidence=0.6,
                            title="Potential Scratch or Trace Damage",
                            description=f"Detected elongated mark at ({x}, {y}) with length {max(w, h)}px that may indicate physical damage.",
                            location={'x': x, 'y': y, 'width': w, 'height': h},
                            affected_components=[],
                            root_cause="Possible handling damage, manufacturing defect, or tooling marks",
                            recommended_fix="Inspect under magnification, ensure no trace damage",
                            impact="May cause open circuits or intermittent connections",
                            detection_method="Canny edge detection + contour analysis"
                        ))

        # Detect solder bridges (bright spots where shouldn't be)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        bright_contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in bright_contours:
            area = cv2.contourArea(contour)

            # Small bright spots could be solder bridges
            if 50 < area < 500:
                x, y, w, h = cv2.boundingRect(contour)

                anomalies.append(Anomaly(
                    anomaly_type=AnomalyType.MANUFACTURING_DEFECT,
                    severity=AnomalySeverity.HIGH,
                    confidence=0.5,
                    title="Potential Solder Bridge",
                    description=f"Detected unexpected bright spot at ({x}, {y}) that may indicate solder bridging.",
                    location={'x': x, 'y': y, 'width': w, 'height': h},
                    affected_components=[],
                    root_cause="Excess solder or solder splash during reflow",
                    recommended_fix="Inspect solder joints, remove any bridges with solder wick",
                    impact="Short circuit risk, functional failure",
                    detection_method="Threshold-based bright spot detection"
                ))

        return anomalies

    async def _detect_power_anomalies(
        self,
        pcb_analysis: Dict[str, Any]
    ) -> List[Anomaly]:
        """Detect power distribution issues."""
        anomalies = []
        components = pcb_analysis.get('components', [])

        # Check for missing power components
        has_voltage_regulator = any(
            'regulator' in c.get('type', '').lower() or
            'ldo' in c.get('type', '').lower()
            for c in components
        )

        has_ics = any(c.get('type') == 'ic' for c in components)

        if has_ics and not has_voltage_regulator:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.POWER_DISTRIBUTION,
                severity=AnomalySeverity.HIGH,
                confidence=0.75,
                title="Missing Voltage Regulation",
                description="Detected ICs without apparent voltage regulator. Unregulated power can damage components.",
                location=None,
                affected_components=[],
                root_cause="No voltage regulator detected in power path",
                recommended_fix="Add appropriate voltage regulator (LDO or switching) for IC power supply",
                impact="Component damage risk, unstable operation, noise sensitivity",
                detection_method="Component type analysis"
            ))

        # Check power consumption vs supply capability
        total_power = sum(c.get('power_rating', 0) for c in components)

        if total_power > 10.0:  # > 10W
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.POWER_DISTRIBUTION,
                severity=AnomalySeverity.MEDIUM,
                confidence=0.85,
                title="High Power Consumption",
                description=f"Total estimated power consumption: {total_power:.1f}W. Verify power supply can handle load.",
                location=None,
                affected_components=[],
                root_cause="Cumulative power consumption exceeds typical supply capacity",
                recommended_fix="Verify power supply rating, consider adding power monitoring, check trace widths",
                impact="Power supply overload, voltage droop, thermal issues",
                detection_method="Power budget analysis"
            ))

        return anomalies

    async def _detect_signal_integrity_issues(
        self,
        pcb_analysis: Dict[str, Any]
    ) -> List[Anomaly]:
        """Detect potential signal integrity problems."""
        anomalies = []
        components = pcb_analysis.get('components', [])

        # Check for missing termination resistors on high-speed signals
        # (simplified heuristic)
        has_high_speed_ics = any(
            'usb' in c.get('type', '').lower() or
            'ethernet' in c.get('type', '').lower() or
            'hdmi' in c.get('type', '').lower()
            for c in components
        )

        resistor_count = len([c for c in components if c.get('type') == 'resistor'])

        if has_high_speed_ics and resistor_count < 2:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.SIGNAL_INTEGRITY,
                severity=AnomalySeverity.MEDIUM,
                confidence=0.6,
                title="Missing Termination Resistors",
                description="High-speed interface detected without sufficient termination resistors.",
                location=None,
                affected_components=[],
                root_cause="High-speed signals require proper impedance matching and termination",
                recommended_fix="Add series/termination resistors per interface specification",
                impact="Signal reflections, EMI issues, communication errors",
                detection_method="Interface type analysis"
            ))

        return anomalies

    async def _detect_design_rule_violations(
        self,
        pcb_analysis: Dict[str, Any]
    ) -> List[Anomaly]:
        """Detect design rule violations."""
        anomalies = []
        components = pcb_analysis.get('components', [])

        # Check component count sanity
        if len(components) < 3:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.DESIGN_RULE_VIOLATION,
                severity=AnomalySeverity.INFO,
                confidence=0.9,
                title="Very Simple Design",
                description=f"Only {len(components)} components detected. This may be intentional or incomplete analysis.",
                location=None,
                affected_components=[],
                root_cause="Low component count",
                recommended_fix="Verify all components were detected correctly",
                impact="None if intentional",
                detection_method="Component count check"
            ))

        return anomalies

    async def predict_reliability(
        self,
        pcb_analysis: Dict[str, Any],
        operating_conditions: Optional[Dict[str, Any]] = None
    ) -> PredictiveMaintenanceScore:
        """
        Predict PCB reliability and maintenance needs.

        Args:
            pcb_analysis: PCB analysis results
            operating_conditions: Environmental conditions (temp, humidity, etc.)

        Returns:
            Predictive maintenance score
        """
        components = pcb_analysis.get('components', [])
        anomalies = await self.detect_anomalies(pcb_analysis)

        # Calculate reliability score (0-100)
        base_score = 100.0

        # Deduct points for anomalies
        severity_penalties = {
            AnomalySeverity.CRITICAL: 20,
            AnomalySeverity.HIGH: 10,
            AnomalySeverity.MEDIUM: 5,
            AnomalySeverity.LOW: 2,
            AnomalySeverity.INFO: 0
        }

        for anomaly in anomalies:
            base_score -= severity_penalties[anomaly.severity]

        reliability_score = max(0, base_score)

        # Estimate longevity based on component quality
        avg_temp_rating = np.mean([
            c.get('temperature_rating', 125)
            for c in components
            if 'temperature_rating' in c
        ]) if components else 125

        operating_temp = operating_conditions.get('temperature', 25) if operating_conditions else 25
        temp_margin = avg_temp_rating - operating_temp

        # Arrhenius equation approximation for longevity
        longevity_years = 10 * (1 + temp_margin / 50)

        # MTBF calculation (simplified)
        mtbf_hours = reliability_score * 1000  # Rough estimate

        # Failure probability
        failure_prob = 1.0 - (reliability_score / 100.0)

        # Identify weak points
        weak_points = []
        critical_anomalies = [a for a in anomalies if a.severity == AnomalySeverity.CRITICAL]

        for anomaly in critical_anomalies:
            weak_points.append({
                'issue': anomaly.title,
                'location': anomaly.location,
                'impact': anomaly.impact
            })

        # Generate recommendations
        recommendations = []

        if reliability_score < 70:
            recommendations.append("Address all critical and high-severity anomalies immediately")

        if temp_margin < 20:
            recommendations.append("Consider components with higher temperature ratings for better longevity")

        if len(critical_anomalies) > 0:
            recommendations.append(f"Fix {len(critical_anomalies)} critical issues before deployment")

        if not recommendations:
            recommendations.append("Design appears robust, maintain regular inspection schedule")

        return PredictiveMaintenanceScore(
            overall_score=reliability_score,
            reliability_score=reliability_score,
            longevity_estimate_years=longevity_years,
            failure_probability=failure_prob,
            mtbf_hours=mtbf_hours,
            weak_points=weak_points,
            recommendations=recommendations
        )


# Singleton instance
anomaly_detector = AnomalyDetector()
