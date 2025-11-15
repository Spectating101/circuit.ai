"""
Parametric 3D Model Generation

Uses CadQuery to generate real 3D models programmatically.
This generates actual STL files that can be 3D printed.

CadQuery installation: pip install cadquery
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import math

try:
    import cadquery as cq
    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False
    print("Warning: CadQuery not installed. Install with: pip install cadquery")


@dataclass
class EnclosureSpec:
    """Enclosure specifications."""
    internal_width: float  # mm
    internal_height: float  # mm
    internal_depth: float  # mm
    wall_thickness: float  # mm
    pcb_standoff_height: float  # mm
    mounting_holes: List[Dict[str, float]]  # [{'x': ..., 'y': ...}, ...]
    connector_cutouts: List[Dict[str, Any]]  # [{'type': ..., 'position': ..., 'size': ...}, ...]
    ventilation: bool
    style: str  # 'minimalist', 'rounded', 'industrial'


class Parametric3DGenerator:
    """Parametric 3D model generator using CadQuery."""

    def __init__(self):
        """Initialize 3D generator."""
        if not CADQUERY_AVAILABLE:
            raise ImportError("CadQuery not installed")

    def generate_enclosure(
        self,
        spec: EnclosureSpec,
        output_base: str,
        output_lid: str
    ) -> Dict[str, Any]:
        """
        Generate electronics enclosure with base and lid.

        Args:
            spec: Enclosure specifications
            output_base: Path for base STL file
            output_lid: Path for lid STL file

        Returns:
            Dict with model info
        """
        # Generate base
        base = self._generate_base(spec)

        # Generate lid
        lid = self._generate_lid(spec)

        # Export STL files
        cq.exporters.export(base, output_base)
        cq.exporters.export(lid, output_lid)

        # Calculate volume and material
        base_volume = self._calculate_volume(base)
        lid_volume = self._calculate_volume(lid)
        total_volume_cm3 = (base_volume + lid_volume) / 1000  # mm³ to cm³

        # Estimate material (PLA density ~1.24 g/cm³)
        material_grams = total_volume_cm3 * 1.24

        # Estimate print time (rough: 15-20mm³/sec extrusion rate)
        extrusion_rate = 17.5  # mm³/sec
        print_time_sec = (base_volume + lid_volume) / extrusion_rate
        print_time_hours = print_time_sec / 3600

        return {
            'base_stl': output_base,
            'lid_stl': output_lid,
            'volume_cm3': total_volume_cm3,
            'estimated_material_grams': material_grams,
            'estimated_print_time_hours': print_time_hours
        }

    def _generate_base(self, spec: EnclosureSpec) -> cq.Workplane:
        """Generate enclosure base."""
        # Calculate outer dimensions
        outer_width = spec.internal_width + 2 * spec.wall_thickness
        outer_height = spec.internal_height + spec.wall_thickness  # No top wall
        outer_depth = spec.internal_depth + 2 * spec.wall_thickness

        # Create outer box
        base = (cq.Workplane("XY")
            .box(outer_width, outer_depth, outer_height)
        )

        # Hollow out interior
        base = (base
            .faces(">Z")
            .workplane(offset=-spec.wall_thickness)
            .rect(spec.internal_width, spec.internal_depth)
            .cutBlind(spec.internal_height)
        )

        # Add PCB standoffs
        for hole in spec.mounting_holes:
            base = self._add_standoff(
                base,
                hole['x'],
                hole['y'],
                spec.pcb_standoff_height,
                outer_width,
                outer_depth
            )

        # Add connector cutouts
        for cutout in spec.connector_cutouts:
            base = self._add_cutout(base, cutout, spec, outer_width, outer_depth, outer_height)

        # Add ventilation if requested
        if spec.ventilation:
            base = self._add_ventilation(base, spec, outer_width, outer_depth)

        # Add styling
        if spec.style == 'rounded':
            base = base.edges("|Z").fillet(2)

        return base

    def _generate_lid(self, spec: EnclosureSpec) -> cq.Workplane:
        """Generate enclosure lid."""
        # Calculate outer dimensions
        outer_width = spec.internal_width + 2 * spec.wall_thickness
        outer_depth = spec.internal_depth + 2 * spec.wall_thickness
        lid_height = spec.wall_thickness + 5  # Extra height for lip

        # Create lid
        lid = (cq.Workplane("XY")
            .box(outer_width, outer_depth, lid_height)
        )

        # Create lip that fits into base
        lip_width = spec.internal_width - 0.4  # Slight clearance
        lip_depth = spec.internal_depth - 0.4
        lip_height = 4

        lip = (cq.Workplane("XY")
            .workplane(offset=-lid_height/2 + spec.wall_thickness)
            .rect(lip_width, lip_depth)
            .extrude(lip_height)
        )

        lid = lid.union(lip)

        # Add screw holes for assembly
        if spec.mounting_holes:
            for hole in spec.mounting_holes[:4]:  # Use up to 4 corner holes
                # Translate to lid coordinate system
                x = hole['x'] - spec.internal_width / 2
                y = hole['y'] - spec.internal_depth / 2

                lid = (lid
                    .faces(">Z")
                    .workplane()
                    .pushPoints([(x, y)])
                    .circle(1.6)  # M3 screw clearance
                    .cutThruAll()
                )

        # Add styling
        if spec.style == 'rounded':
            lid = lid.edges("|Z").fillet(2)

        return lid

    def _add_standoff(
        self,
        base: cq.Workplane,
        x: float,
        y: float,
        height: float,
        outer_width: float,
        outer_depth: float
    ) -> cq.Workplane:
        """Add PCB standoff to base."""
        # Translate to base coordinate system (center is 0,0)
        standoff_x = x - outer_width / 2
        standoff_y = y - outer_depth / 2

        # Create standoff cylinder with screw hole
        standoff = (cq.Workplane("XY")
            .workplane(offset=-outer_width/2)  # Bottom of base
            .pushPoints([(standoff_x, standoff_y)])
            .circle(3)  # 6mm diameter standoff
            .extrude(height)
            .faces(">Z")
            .workplane()
            .pushPoints([(standoff_x, standoff_y)])
            .circle(1.5)  # M3 screw hole
            .cutBlind(height - 2)  # Leave 2mm at bottom
        )

        return base.union(standoff)

    def _add_cutout(
        self,
        base: cq.Workplane,
        cutout: Dict[str, Any],
        spec: EnclosureSpec,
        outer_width: float,
        outer_depth: float,
        outer_height: float
    ) -> cq.Workplane:
        """Add connector cutout to enclosure."""
        position = cutout['position']
        size = cutout['size']
        side = cutout.get('side', 'left')

        # Determine which face to cut
        if side == 'left':
            face_selector = "<X"
            plane_offset = -outer_width / 2
        elif side == 'right':
            face_selector = ">X"
            plane_offset = outer_width / 2
        elif side == 'front':
            face_selector = "<Y"
            plane_offset = -outer_depth / 2
        elif side == 'back':
            face_selector = ">Y"
            plane_offset = outer_depth / 2
        else:
            return base  # Unknown side

        # Create cutout rectangle
        base = (base
            .faces(face_selector)
            .workplane()
            .center(position.get('y', 0), position.get('z', outer_height/2 - 10))
            .rect(size['width'], size['height'])
            .cutThruAll()
        )

        return base

    def _add_ventilation(
        self,
        base: cq.Workplane,
        spec: EnclosureSpec,
        outer_width: float,
        outer_depth: float
    ) -> cq.Workplane:
        """Add ventilation slots to enclosure."""
        # Add slots to sides
        slot_width = 1.0
        slot_length = 10.0
        slot_spacing = 3.0

        num_slots = int((outer_depth - 20) / (slot_width + slot_spacing))

        for i in range(num_slots):
            y_pos = -outer_depth/2 + 10 + i * (slot_width + slot_spacing)

            # Left side
            base = (base
                .faces("<X")
                .workplane()
                .center(y_pos, 5)
                .rect(slot_width, slot_length)
                .cutThruAll()
            )

            # Right side
            base = (base
                .faces(">X")
                .workplane()
                .center(y_pos, 5)
                .rect(slot_width, slot_length)
                .cutThruAll()
            )

        return base

    def _calculate_volume(self, model: cq.Workplane) -> float:
        """Calculate model volume in mm³."""
        # Get the solid
        solid = model.val()

        # Calculate volume using CadQuery's built-in method
        if hasattr(solid, 'Volume'):
            return solid.Volume()
        else:
            # Fallback estimation
            bbox = solid.BoundingBox()
            return bbox.xlen * bbox.ylen * bbox.zlen * 0.3  # Rough estimate

    def generate_bracket(
        self,
        width: float,
        height: float,
        thickness: float,
        hole_diameter: float,
        output_file: str
    ) -> Dict[str, Any]:
        """
        Generate simple mounting bracket.

        Args:
            width: Bracket width (mm)
            height: Bracket height (mm)
            thickness: Bracket thickness (mm)
            hole_diameter: Mounting hole diameter (mm)
            output_file: Output STL file path

        Returns:
            Dict with model info
        """
        # Create bracket
        bracket = (cq.Workplane("XY")
            .rect(width, height)
            .extrude(thickness)
        )

        # Add mounting holes at corners
        hole_inset = 5
        bracket = (bracket
            .faces(">Z")
            .workplane()
            .pushPoints([
                (-width/2 + hole_inset, -height/2 + hole_inset),
                (width/2 - hole_inset, -height/2 + hole_inset),
                (-width/2 + hole_inset, height/2 - hole_inset),
                (width/2 - hole_inset, height/2 - hole_inset)
            ])
            .circle(hole_diameter / 2)
            .cutThruAll()
        )

        # Round edges
        bracket = bracket.edges("|Z").fillet(2)

        # Export
        cq.exporters.export(bracket, output_file)

        volume = self._calculate_volume(bracket)
        material_grams = (volume / 1000) * 1.24

        return {
            'stl': output_file,
            'volume_cm3': volume / 1000,
            'estimated_material_grams': material_grams
        }

    def generate_cable_organizer(
        self,
        num_slots: int,
        slot_width: float,
        slot_depth: float,
        output_file: str
    ) -> Dict[str, Any]:
        """
        Generate cable organizer with slots.

        Args:
            num_slots: Number of cable slots
            slot_width: Width of each slot (mm)
            slot_depth: Depth of each slot (mm)
            output_file: Output STL file path

        Returns:
            Dict with model info
        """
        base_thickness = 3
        wall_thickness = 2
        slot_height = 20

        total_width = num_slots * (slot_width + wall_thickness) + wall_thickness

        # Create base
        organizer = (cq.Workplane("XY")
            .rect(total_width, slot_depth + 2 * wall_thickness)
            .extrude(base_thickness)
        )

        # Add walls to create slots
        for i in range(num_slots + 1):
            x_pos = -total_width/2 + i * (slot_width + wall_thickness)

            wall = (cq.Workplane("XY")
                .workplane(offset=base_thickness/2)
                .center(x_pos, 0)
                .rect(wall_thickness, slot_depth)
                .extrude(slot_height)
            )

            organizer = organizer.union(wall)

        # Export
        cq.exporters.export(organizer, output_file)

        volume = self._calculate_volume(organizer)
        material_grams = (volume / 1000) * 1.24

        return {
            'stl': output_file,
            'volume_cm3': volume / 1000,
            'estimated_material_grams': material_grams
        }


# Helper function for easy use
def generate_electronics_enclosure(
    pcb_width: float,
    pcb_height: float,
    pcb_thickness: float,
    component_height_top: float,
    component_height_bottom: float,
    connectors: List[Dict[str, Any]] = None,
    output_dir: str = "/tmp"
) -> Dict[str, Any]:
    """
    Quick helper to generate electronics enclosure.

    Args:
        pcb_width: PCB width in mm
        pcb_height: PCB height in mm
        pcb_thickness: PCB thickness in mm (typically 1.6)
        component_height_top: Max component height on top side
        component_height_bottom: Max component height on bottom side
        connectors: List of connector cutouts
        output_dir: Output directory for STL files

    Returns:
        Dict with file paths and metadata
    """
    if not CADQUERY_AVAILABLE:
        raise ImportError("CadQuery not installed")

    # Calculate enclosure dimensions
    clearance = 5  # mm
    wall_thickness = 2  # mm
    standoff_height = component_height_bottom + 3  # Extra clearance

    spec = EnclosureSpec(
        internal_width=pcb_width + 2 * clearance,
        internal_height=standoff_height + pcb_thickness + component_height_top + clearance,
        internal_depth=pcb_height + 2 * clearance,
        wall_thickness=wall_thickness,
        pcb_standoff_height=standoff_height,
        mounting_holes=[
            {'x': clearance, 'y': clearance},
            {'x': pcb_width + clearance, 'y': clearance},
            {'x': clearance, 'y': pcb_height + clearance},
            {'x': pcb_width + clearance, 'y': pcb_height + clearance}
        ],
        connector_cutouts=connectors or [],
        ventilation=True,
        style='minimalist'
    )

    generator = Parametric3DGenerator()

    output_base = f"{output_dir}/enclosure_base.stl"
    output_lid = f"{output_dir}/enclosure_lid.stl"

    result = generator.generate_enclosure(spec, output_base, output_lid)

    return result
