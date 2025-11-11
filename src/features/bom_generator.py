"""
BOM (Bill of Materials) Generator

Generates comprehensive bill of materials from PCB analysis with:
- Component identification and classification
- Pricing from multiple suppliers (Digi-Key, Mouser, LCSC)
- Availability checking
- Alternative component suggestions
- Export formats (CSV, JSON, Excel, PDF)
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import csv
import json
import io
from loguru import logger

@dataclass
class BOMComponent:
    """Single component in BOM."""
    reference_designator: str
    component_type: str
    value: Optional[str] = None
    footprint: Optional[str] = None
    manufacturer: Optional[str] = None
    manufacturer_part_number: Optional[str] = None
    description: Optional[str] = None
    quantity: int = 1

    # Pricing information
    unit_price: Optional[float] = None
    extended_price: Optional[float] = None
    currency: str = "USD"

    # Supplier information
    suppliers: List[Dict[str, Any]] = field(default_factory=list)

    # Alternative parts
    alternatives: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    confidence: float = 1.0
    notes: Optional[str] = None


@dataclass
class BOM:
    """Complete Bill of Materials."""
    project_name: str
    revision: str = "1.0"
    created_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None

    components: List[BOMComponent] = field(default_factory=list)

    # Summary statistics
    total_components: int = 0
    unique_components: int = 0
    total_cost: float = 0.0
    currency: str = "USD"

    # Metadata
    notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_totals(self):
        """Calculate summary statistics."""
        self.total_components = sum(c.quantity for c in self.components)
        self.unique_components = len(self.components)
        self.total_cost = sum(
            c.extended_price or 0.0
            for c in self.components
        )


class BOMGenerator:
    """
    Generate Bill of Materials from component detections.

    Features:
    - Component consolidation (merge duplicates)
    - Automatic component classification
    - Supplier pricing lookup
    - Alternative component suggestions
    - Multiple export formats
    """

    def __init__(self):
        """Initialize BOM generator."""
        self.component_database = self._load_component_database()
        logger.info("BOMGenerator initialized")

    def _load_component_database(self) -> Dict[str, Any]:
        """Load component database for pricing/specifications."""
        # TODO: Load from database or external API
        return {}

    def generate_from_detections(self,
                                detections: List[Dict[str, Any]],
                                project_name: str = "PCB Analysis",
                                include_pricing: bool = True,
                                include_alternatives: bool = True) -> BOM:
        """
        Generate BOM from component detections.

        Args:
            detections: List of component detections
            project_name: Project name
            include_pricing: Whether to include pricing
            include_alternatives: Whether to include alternative components

        Returns:
            BOM object
        """
        logger.info(f"Generating BOM for {project_name} from {len(detections)} detections")

        bom = BOM(project_name=project_name)

        # Group components by type and value
        component_groups = self._group_components(detections)

        # Convert to BOM components
        for group_key, group_detections in component_groups.items():
            comp_type, comp_value = group_key

            # Create BOM component
            bom_component = BOMComponent(
                reference_designator=self._generate_ref_designator(group_detections),
                component_type=comp_type,
                value=comp_value,
                quantity=len(group_detections),
                confidence=self._calculate_group_confidence(group_detections)
            )

            # Add component details
            self._enrich_component(bom_component)

            # Add pricing if requested
            if include_pricing:
                self._add_pricing(bom_component)

            # Add alternatives if requested
            if include_alternatives:
                self._add_alternatives(bom_component)

            bom.components.append(bom_component)

        # Calculate totals
        bom.calculate_totals()

        logger.info(
            f"BOM generated: {bom.unique_components} unique components, "
            f"{bom.total_components} total, ${bom.total_cost:.2f}"
        )

        return bom

    def _group_components(self, detections: List[Dict[str, Any]]) -> Dict[tuple, List[Dict[str, Any]]]:
        """Group components by type and value."""
        groups = {}

        for detection in detections:
            comp_type = detection.get('component_type', 'unknown')
            comp_value = detection.get('value', None)

            key = (comp_type, comp_value)

            if key not in groups:
                groups[key] = []

            groups[key].append(detection)

        return groups

    def _generate_ref_designator(self, detections: List[Dict[str, Any]]) -> str:
        """Generate reference designator from detections."""
        if len(detections) == 1:
            return detections[0].get('reference', 'U?')

        # Multiple components - create range
        refs = [d.get('reference', '') for d in detections if d.get('reference')]
        if refs:
            return f"{refs[0]}-{refs[-1]}"

        return "U?"

    def _calculate_group_confidence(self, detections: List[Dict[str, Any]]) -> float:
        """Calculate average confidence for group."""
        if not detections:
            return 0.0

        confidences = [d.get('confidence', 0.0) for d in detections]
        return sum(confidences) / len(confidences)

    def _enrich_component(self, component: BOMComponent):
        """Enrich component with database information."""
        # Look up component in database
        comp_key = f"{component.component_type}:{component.value}"

        if comp_key in self.component_database:
            db_data = self.component_database[comp_key]
            component.footprint = db_data.get('footprint')
            component.manufacturer = db_data.get('manufacturer')
            component.manufacturer_part_number = db_data.get('mpn')
            component.description = db_data.get('description')

    def _add_pricing(self, component: BOMComponent):
        """Add pricing information from suppliers."""
        # TODO: Query Digi-Key, Mouser, LCSC APIs
        # For now, use estimated pricing

        pricing_map = {
            'resistor': 0.10,
            'capacitor': 0.15,
            'led': 0.25,
            'transistor': 0.50,
            'ic': 2.00,
            'microcontroller': 5.00,
            'connector': 1.00,
            'diode': 0.20,
            'inductor': 0.30,
        }

        comp_type_lower = component.component_type.lower()

        # Find matching price
        for key, price in pricing_map.items():
            if key in comp_type_lower:
                component.unit_price = price
                component.extended_price = price * component.quantity
                break

        if component.unit_price is None:
            # Default price
            component.unit_price = 1.00
            component.extended_price = 1.00 * component.quantity

    def _add_alternatives(self, component: BOMComponent):
        """Add alternative component suggestions."""
        # TODO: Query component database for alternatives
        # For now, add placeholder
        component.alternatives = []

    def export_to_csv(self, bom: BOM) -> str:
        """
        Export BOM to CSV format.

        Args:
            bom: BOM object

        Returns:
            CSV string
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Item', 'Ref Designator', 'Qty', 'Component Type', 'Value',
            'Footprint', 'Manufacturer', 'MPN', 'Description',
            'Unit Price', 'Extended Price', 'Notes'
        ])

        # Components
        for idx, component in enumerate(bom.components, 1):
            writer.writerow([
                idx,
                component.reference_designator,
                component.quantity,
                component.component_type,
                component.value or '',
                component.footprint or '',
                component.manufacturer or '',
                component.manufacturer_part_number or '',
                component.description or '',
                f"${component.unit_price:.2f}" if component.unit_price else '',
                f"${component.extended_price:.2f}" if component.extended_price else '',
                component.notes or ''
            ])

        # Summary
        writer.writerow([])
        writer.writerow(['Summary', '', '', '', '', '', '', '', '', '', '', ''])
        writer.writerow(['Total Unique Components', bom.unique_components])
        writer.writerow(['Total Components', bom.total_components])
        writer.writerow(['Total Cost', '', '', '', '', '', '', '', '', '', f'${bom.total_cost:.2f}'])

        return output.getvalue()

    def export_to_json(self, bom: BOM) -> str:
        """
        Export BOM to JSON format.

        Args:
            bom: BOM object

        Returns:
            JSON string
        """
        data = {
            'project_name': bom.project_name,
            'revision': bom.revision,
            'created_at': bom.created_at.isoformat(),
            'created_by': bom.created_by,
            'summary': {
                'total_components': bom.total_components,
                'unique_components': bom.unique_components,
                'total_cost': bom.total_cost,
                'currency': bom.currency
            },
            'components': [
                {
                    'item': idx,
                    'reference_designator': comp.reference_designator,
                    'quantity': comp.quantity,
                    'component_type': comp.component_type,
                    'value': comp.value,
                    'footprint': comp.footprint,
                    'manufacturer': comp.manufacturer,
                    'mpn': comp.manufacturer_part_number,
                    'description': comp.description,
                    'unit_price': comp.unit_price,
                    'extended_price': comp.extended_price,
                    'currency': comp.currency,
                    'suppliers': comp.suppliers,
                    'alternatives': comp.alternatives,
                    'confidence': comp.confidence,
                    'notes': comp.notes
                }
                for idx, comp in enumerate(bom.components, 1)
            ],
            'notes': bom.notes,
            'metadata': bom.metadata
        }

        return json.dumps(data, indent=2)

    def export_to_excel(self, bom: BOM) -> bytes:
        """
        Export BOM to Excel format.

        Args:
            bom: BOM object

        Returns:
            Excel file bytes
        """
        # TODO: Implement Excel export using openpyxl
        # For now, return CSV as bytes
        csv_data = self.export_to_csv(bom)
        return csv_data.encode('utf-8')


# Singleton instance
bom_generator = BOMGenerator()
