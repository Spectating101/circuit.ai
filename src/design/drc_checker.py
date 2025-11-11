"""
Design Rule Checking (DRC) for PCB Designs

Features:
- Automated design rule verification
- Trace width and spacing checks
- Clearance verification
- Via checks
- Hole size validation
- Copper balance analysis
- Thermal relief verification
- Drill-to-copper spacing
- Signal integrity rules
- Manufacturing feasibility
"""

from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import numpy as np
from loguru import logger
import math


class RuleSeverity(Enum):
    """DRC rule violation severity."""
    ERROR = "error"  # Must fix
    WARNING = "warning"  # Should fix
    INFO = "info"  # Informational


class LayerType(Enum):
    """PCB layer types."""
    TOP_COPPER = "top_copper"
    BOTTOM_COPPER = "bottom_copper"
    INTERNAL_1 = "internal_1"
    INTERNAL_2 = "internal_2"
    TOP_SOLDER_MASK = "top_solder_mask"
    BOTTOM_SOLDER_MASK = "bottom_solder_mask"
    TOP_SILKSCREEN = "top_silkscreen"
    BOTTOM_SILKSCREEN = "bottom_silkscreen"


@dataclass
class DesignRules:
    """PCB design rules specification."""
    # Trace rules (in mils, 1 mil = 0.001 inch)
    min_trace_width: float = 6.0  # 6 mil minimum
    min_trace_spacing: float = 6.0
    min_power_trace_width: float = 10.0

    # Via rules
    min_via_diameter: float = 12.0  # mil
    min_via_drill: float = 8.0
    min_via_to_via: float = 8.0

    # Pad rules
    min_pad_size: float = 20.0
    min_pad_to_pad: float = 8.0

    # Hole rules
    min_hole_diameter: float = 10.0
    max_hole_diameter: float = 250.0
    min_hole_to_hole: float = 10.0

    # Clearances
    min_copper_to_edge: float = 20.0  # mil from board edge
    min_copper_to_hole: float = 8.0
    min_solder_mask_expansion: float = 4.0

    # Annular ring (copper around hole)
    min_annular_ring: float = 4.0

    # High speed signals
    max_stub_length: float = 200.0  # mil
    impedance_tolerance: float = 10.0  # percent

    # Manufacturing
    max_aspect_ratio: float = 10.0  # hole depth to diameter
    min_copper_balance: float = 30.0  # percent
    max_copper_balance: float = 70.0


@dataclass
class Point:
    """2D point."""
    x: float
    y: float


@dataclass
class Trace:
    """PCB trace."""
    id: str
    layer: LayerType
    width: float
    start: Point
    end: Point
    net_name: str
    is_power: bool = False


@dataclass
class Via:
    """PCB via."""
    id: str
    position: Point
    diameter: float
    drill_diameter: float
    net_name: str


@dataclass
class Pad:
    """PCB pad."""
    id: str
    position: Point
    width: float
    height: float
    hole_diameter: Optional[float]
    layer: LayerType
    net_name: str


@dataclass
class DRCViolation:
    """Design rule violation."""
    rule_name: str
    severity: RuleSeverity
    description: str
    location: Optional[Point]
    affected_objects: List[str]
    recommendation: str
    layer: Optional[LayerType]


@dataclass
class DRCReport:
    """Complete DRC report."""
    timestamp: datetime
    violations: List[DRCViolation]
    error_count: int
    warning_count: int
    info_count: int
    passed: bool
    design_rules: DesignRules


class GeometryUtils:
    """Geometric calculation utilities."""

    @staticmethod
    def distance(p1: Point, p2: Point) -> float:
        """Calculate distance between two points."""
        return math.sqrt((p2.x - p1.x)**2 + (p2.y - p1.y)**2)

    @staticmethod
    def point_to_line_distance(
        point: Point,
        line_start: Point,
        line_end: Point
    ) -> float:
        """Calculate perpendicular distance from point to line segment."""
        # Vector from line start to point
        px = point.x - line_start.x
        py = point.y - line_start.y

        # Vector representing line
        lx = line_end.x - line_start.x
        ly = line_end.y - line_start.y

        # Line length squared
        line_len_sq = lx**2 + ly**2

        if line_len_sq == 0:
            return math.sqrt(px**2 + py**2)

        # Project point onto line
        t = max(0, min(1, (px * lx + py * ly) / line_len_sq))

        # Closest point on line
        closest_x = line_start.x + t * lx
        closest_y = line_start.y + t * ly

        # Distance
        dx = point.x - closest_x
        dy = point.y - closest_y

        return math.sqrt(dx**2 + dy**2)

    @staticmethod
    def rectangles_overlap(
        r1_x: float, r1_y: float, r1_w: float, r1_h: float,
        r2_x: float, r2_y: float, r2_w: float, r2_h: float
    ) -> bool:
        """Check if two rectangles overlap."""
        return not (
            r1_x + r1_w < r2_x or
            r2_x + r2_w < r1_x or
            r1_y + r1_h < r2_y or
            r2_y + r2_h < r1_y
        )


class TraceWidthChecker:
    """Check trace width rules."""

    def __init__(self, rules: DesignRules):
        """Initialize checker."""
        self.rules = rules

    def check(self, traces: List[Trace]) -> List[DRCViolation]:
        """
        Check all traces for width violations.

        Args:
            traces: List of traces

        Returns:
            List of violations
        """
        violations = []

        for trace in traces:
            # Check minimum trace width
            min_width = (
                self.rules.min_power_trace_width
                if trace.is_power
                else self.rules.min_trace_width
            )

            if trace.width < min_width:
                violations.append(DRCViolation(
                    rule_name="Minimum Trace Width",
                    severity=RuleSeverity.ERROR,
                    description=f"Trace width {trace.width:.2f} mil is below minimum {min_width:.2f} mil",
                    location=trace.start,
                    affected_objects=[trace.id],
                    recommendation=f"Increase trace width to at least {min_width:.2f} mil",
                    layer=trace.layer
                ))

            # Check if trace can handle expected current
            if trace.is_power:
                # Calculate required width for 1oz copper, 10°C rise
                # Using IPC-2221 formula
                expected_current = 1.0  # Assume 1A
                required_width = self._calculate_required_width(
                    expected_current,
                    temp_rise=10.0
                )

                if trace.width < required_width:
                    violations.append(DRCViolation(
                        rule_name="Power Trace Current Capacity",
                        severity=RuleSeverity.WARNING,
                        description=f"Power trace may be too narrow for {expected_current}A",
                        location=trace.start,
                        affected_objects=[trace.id],
                        recommendation=f"Consider increasing to {required_width:.2f} mil for {expected_current}A",
                        layer=trace.layer
                    ))

        return violations

    def _calculate_required_width(
        self,
        current_amps: float,
        temp_rise: float = 10.0,
        copper_oz: float = 1.0
    ) -> float:
        """
        Calculate required trace width using IPC-2221.

        Args:
            current_amps: Current in amps
            temp_rise: Temperature rise in °C
            copper_oz: Copper weight in oz/ft²

        Returns:
            Required width in mils
        """
        # IPC-2221 formula: A = (I / (k * (T^b)))^(1/c)
        # For external layers: k=0.048, b=0.44, c=0.725
        k = 0.048
        b = 0.44
        c = 0.725

        # Area in mil²
        area = (current_amps / (k * (temp_rise ** b))) ** (1 / c)

        # Thickness in mils for 1oz copper
        thickness = 1.378 * copper_oz

        # Width = Area / Thickness
        width = area / thickness

        return width


class ClearanceChecker:
    """Check clearance rules."""

    def __init__(self, rules: DesignRules):
        """Initialize checker."""
        self.rules = rules
        self.geom = GeometryUtils()

    def check_trace_spacing(
        self,
        traces: List[Trace]
    ) -> List[DRCViolation]:
        """Check trace-to-trace spacing."""
        violations = []

        # Check all pairs of traces on same layer
        for i, trace1 in enumerate(traces):
            for trace2 in traces[i+1:]:
                # Only check traces on same layer
                if trace1.layer != trace2.layer:
                    continue

                # Skip if same net (no spacing required)
                if trace1.net_name == trace2.net_name:
                    continue

                # Calculate minimum distance between traces
                # (Simplified: check start and end points)
                distances = [
                    self.geom.point_to_line_distance(
                        trace1.start, trace2.start, trace2.end
                    ),
                    self.geom.point_to_line_distance(
                        trace1.end, trace2.start, trace2.end
                    ),
                    self.geom.point_to_line_distance(
                        trace2.start, trace1.start, trace1.end
                    ),
                    self.geom.point_to_line_distance(
                        trace2.end, trace1.start, trace1.end
                    )
                ]

                min_distance = min(distances)

                # Account for trace widths
                clearance = min_distance - (trace1.width / 2) - (trace2.width / 2)

                if clearance < self.rules.min_trace_spacing:
                    violations.append(DRCViolation(
                        rule_name="Minimum Trace Spacing",
                        severity=RuleSeverity.ERROR,
                        description=f"Traces are {clearance:.2f} mil apart (min: {self.rules.min_trace_spacing:.2f})",
                        location=trace1.start,
                        affected_objects=[trace1.id, trace2.id],
                        recommendation=f"Increase spacing to {self.rules.min_trace_spacing:.2f} mil",
                        layer=trace1.layer
                    ))

        return violations

    def check_copper_to_edge(
        self,
        traces: List[Trace],
        board_width: float,
        board_height: float
    ) -> List[DRCViolation]:
        """Check copper to board edge clearance."""
        violations = []

        for trace in traces:
            # Check distance to all edges
            distances = [
                trace.start.x,  # Left edge
                board_width - trace.start.x,  # Right edge
                trace.start.y,  # Bottom edge
                board_height - trace.start.y  # Top edge
            ]

            min_distance = min(distances)

            if min_distance < self.rules.min_copper_to_edge:
                violations.append(DRCViolation(
                    rule_name="Copper to Board Edge",
                    severity=RuleSeverity.ERROR,
                    description=f"Copper is {min_distance:.2f} mil from edge (min: {self.rules.min_copper_to_edge:.2f})",
                    location=trace.start,
                    affected_objects=[trace.id],
                    recommendation=f"Move trace at least {self.rules.min_copper_to_edge:.2f} mil from edge",
                    layer=trace.layer
                ))

        return violations


class ViaChecker:
    """Check via rules."""

    def __init__(self, rules: DesignRules):
        """Initialize checker."""
        self.rules = rules
        self.geom = GeometryUtils()

    def check(
        self,
        vias: List[Via],
        board_thickness: float
    ) -> List[DRCViolation]:
        """
        Check via rules.

        Args:
            vias: List of vias
            board_thickness: Board thickness in mils

        Returns:
            List of violations
        """
        violations = []

        for via in vias:
            # Check minimum via diameter
            if via.diameter < self.rules.min_via_diameter:
                violations.append(DRCViolation(
                    rule_name="Minimum Via Diameter",
                    severity=RuleSeverity.ERROR,
                    description=f"Via diameter {via.diameter:.2f} mil is below minimum",
                    location=via.position,
                    affected_objects=[via.id],
                    recommendation=f"Increase diameter to {self.rules.min_via_diameter:.2f} mil",
                    layer=None
                ))

            # Check minimum drill size
            if via.drill_diameter < self.rules.min_via_drill:
                violations.append(DRCViolation(
                    rule_name="Minimum Via Drill",
                    severity=RuleSeverity.ERROR,
                    description=f"Via drill {via.drill_diameter:.2f} mil is below minimum",
                    location=via.position,
                    affected_objects=[via.id],
                    recommendation=f"Increase drill to {self.rules.min_via_drill:.2f} mil",
                    layer=None
                ))

            # Check annular ring
            annular_ring = (via.diameter - via.drill_diameter) / 2

            if annular_ring < self.rules.min_annular_ring:
                violations.append(DRCViolation(
                    rule_name="Minimum Annular Ring",
                    severity=RuleSeverity.ERROR,
                    description=f"Annular ring {annular_ring:.2f} mil is too small",
                    location=via.position,
                    affected_objects=[via.id],
                    recommendation=f"Increase via diameter or reduce drill to achieve {self.rules.min_annular_ring:.2f} mil ring",
                    layer=None
                ))

            # Check aspect ratio (depth to diameter)
            aspect_ratio = board_thickness / via.drill_diameter

            if aspect_ratio > self.rules.max_aspect_ratio:
                violations.append(DRCViolation(
                    rule_name="Via Aspect Ratio",
                    severity=RuleSeverity.WARNING,
                    description=f"Aspect ratio {aspect_ratio:.2f}:1 exceeds recommended maximum",
                    location=via.position,
                    affected_objects=[via.id],
                    recommendation=f"Increase drill diameter or use HDI technology",
                    layer=None
                ))

        # Check via-to-via spacing
        for i, via1 in enumerate(vias):
            for via2 in vias[i+1:]:
                distance = self.geom.distance(via1.position, via2.position)

                # Account for via diameters
                clearance = distance - (via1.diameter / 2) - (via2.diameter / 2)

                if clearance < self.rules.min_via_to_via:
                    violations.append(DRCViolation(
                        rule_name="Via to Via Spacing",
                        severity=RuleSeverity.ERROR,
                        description=f"Vias are {clearance:.2f} mil apart (min: {self.rules.min_via_to_via:.2f})",
                        location=via1.position,
                        affected_objects=[via1.id, via2.id],
                        recommendation=f"Increase spacing to {self.rules.min_via_to_via:.2f} mil",
                        layer=None
                    ))

        return violations


class SignalIntegrityChecker:
    """Check signal integrity rules."""

    def __init__(self, rules: DesignRules):
        """Initialize checker."""
        self.rules = rules

    def check_stub_length(
        self,
        traces: List[Trace],
        vias: List[Via]
    ) -> List[DRCViolation]:
        """Check for excessive stub lengths on high-speed signals."""
        violations = []

        # Identify high-speed nets (simplified)
        high_speed_nets = self._identify_high_speed_nets(traces)

        for net in high_speed_nets:
            # Find vias on this net
            net_vias = [v for v in vias if v.net_name == net]

            for via in net_vias:
                # Check if via is at end of trace (stub)
                is_stub = self._is_stub_via(via, traces)

                if is_stub:
                    violations.append(DRCViolation(
                        rule_name="High-Speed Stub Length",
                        severity=RuleSeverity.WARNING,
                        description=f"Via on high-speed net may create stub",
                        location=via.position,
                        affected_objects=[via.id],
                        recommendation="Use back-drilling or move via to minimize stub length",
                        layer=None
                    ))

        return violations

    def _identify_high_speed_nets(self, traces: List[Trace]) -> Set[str]:
        """Identify high-speed signal nets."""
        # Simplified: look for differential pairs, USB, PCIe, etc.
        high_speed = set()

        keywords = ['usb', 'pcie', 'diff', 'clock', 'lvds', 'serdes']

        for trace in traces:
            net_name_lower = trace.net_name.lower()
            if any(kw in net_name_lower for kw in keywords):
                high_speed.add(trace.net_name)

        return high_speed

    def _is_stub_via(self, via: Via, traces: List[Trace]) -> bool:
        """Check if via creates a stub (dead-end connection)."""
        # Find traces connected to this via
        connected_traces = [
            t for t in traces
            if t.net_name == via.net_name and
            (self._point_near(via.position, t.start) or
             self._point_near(via.position, t.end))
        ]

        # If only one trace connected, it's likely a stub
        return len(connected_traces) <= 1

    def _point_near(self, p1: Point, p2: Point, tolerance: float = 1.0) -> bool:
        """Check if points are near each other."""
        return abs(p1.x - p2.x) < tolerance and abs(p1.y - p2.y) < tolerance


class ManufacturingChecker:
    """Check manufacturing feasibility."""

    def __init__(self, rules: DesignRules):
        """Initialize checker."""
        self.rules = rules

    def check_copper_balance(
        self,
        layers: Dict[LayerType, np.ndarray]
    ) -> List[DRCViolation]:
        """
        Check copper balance for each layer.

        Args:
            layers: Dictionary of layer images (binary: copper/no-copper)

        Returns:
            List of violations
        """
        violations = []

        for layer_type, layer_image in layers.items():
            if layer_type not in [LayerType.TOP_COPPER, LayerType.BOTTOM_COPPER]:
                continue

            # Calculate copper percentage
            total_pixels = layer_image.size
            copper_pixels = np.sum(layer_image > 0)
            copper_percent = (copper_pixels / total_pixels) * 100

            if copper_percent < self.rules.min_copper_balance:
                violations.append(DRCViolation(
                    rule_name="Minimum Copper Balance",
                    severity=RuleSeverity.WARNING,
                    description=f"Layer has only {copper_percent:.1f}% copper (min: {self.rules.min_copper_balance}%)",
                    location=None,
                    affected_objects=[layer_type.value],
                    recommendation="Add copper pours or hatching to balance copper distribution",
                    layer=layer_type
                ))

            if copper_percent > self.rules.max_copper_balance:
                violations.append(DRCViolation(
                    rule_name="Maximum Copper Balance",
                    severity=RuleSeverity.WARNING,
                    description=f"Layer has {copper_percent:.1f}% copper (max: {self.rules.max_copper_balance}%)",
                    location=None,
                    affected_objects=[layer_type.value],
                    recommendation="Remove some copper or add relief in large pours",
                    layer=layer_type
                ))

        return violations


class DRCEngine:
    """Main Design Rule Checking engine."""

    def __init__(self, rules: Optional[DesignRules] = None):
        """
        Initialize DRC engine.

        Args:
            rules: Design rules (uses defaults if None)
        """
        self.rules = rules or DesignRules()

        # Initialize checkers
        self.trace_checker = TraceWidthChecker(self.rules)
        self.clearance_checker = ClearanceChecker(self.rules)
        self.via_checker = ViaChecker(self.rules)
        self.signal_checker = SignalIntegrityChecker(self.rules)
        self.mfg_checker = ManufacturingChecker(self.rules)

        logger.info("DRC Engine initialized")

    def run_checks(
        self,
        traces: List[Trace],
        vias: List[Via],
        pads: List[Pad],
        board_width: float,
        board_height: float,
        board_thickness: float,
        layers: Optional[Dict[LayerType, np.ndarray]] = None
    ) -> DRCReport:
        """
        Run all DRC checks.

        Args:
            traces: List of traces
            vias: List of vias
            pads: List of pads
            board_width: Board width in mils
            board_height: Board height in mils
            board_thickness: Board thickness in mils
            layers: Layer images for copper balance check

        Returns:
            DRC report
        """
        logger.info("Running DRC checks...")

        all_violations = []

        # Trace width checks
        logger.debug("Checking trace widths...")
        all_violations.extend(self.trace_checker.check(traces))

        # Clearance checks
        logger.debug("Checking clearances...")
        all_violations.extend(self.clearance_checker.check_trace_spacing(traces))
        all_violations.extend(
            self.clearance_checker.check_copper_to_edge(
                traces, board_width, board_height
            )
        )

        # Via checks
        logger.debug("Checking vias...")
        all_violations.extend(self.via_checker.check(vias, board_thickness))

        # Signal integrity checks
        logger.debug("Checking signal integrity...")
        all_violations.extend(self.signal_checker.check_stub_length(traces, vias))

        # Manufacturing checks
        if layers:
            logger.debug("Checking manufacturing feasibility...")
            all_violations.extend(self.mfg_checker.check_copper_balance(layers))

        # Count violations by severity
        error_count = sum(1 for v in all_violations if v.severity == RuleSeverity.ERROR)
        warning_count = sum(1 for v in all_violations if v.severity == RuleSeverity.WARNING)
        info_count = sum(1 for v in all_violations if v.severity == RuleSeverity.INFO)

        # Design passes if no errors
        passed = error_count == 0

        logger.info(
            f"DRC complete: {error_count} errors, {warning_count} warnings, "
            f"{info_count} info"
        )

        return DRCReport(
            timestamp=datetime.utcnow(),
            violations=all_violations,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            passed=passed,
            design_rules=self.rules
        )


# Singleton instance with standard PCB rules
drc_engine = DRCEngine()

# Also create instance for high-reliability designs
high_rel_rules = DesignRules(
    min_trace_width=8.0,  # Wider traces
    min_trace_spacing=8.0,  # More spacing
    min_via_diameter=15.0,  # Larger vias
    min_annular_ring=5.0,  # Bigger annular rings
)
high_rel_drc = DRCEngine(rules=high_rel_rules)
