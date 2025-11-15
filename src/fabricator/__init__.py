"""
Fabricator Module

Working implementations of circuit design and 3D generation utilities.

This module provides:
- Component database with common electronics parts
- Component selection algorithms
- Parametric 3D model generation using CadQuery
- Circuit design utilities
- Manufacturing file packaging

These are working implementations that don't require external APIs.
"""

from .component_database import (
    component_db,
    Component,
    ComponentCategory,
    ComponentDatabase
)

from .circuit_utils import (
    component_selector,
    circuit_validator,
    ComponentSelector,
    CircuitValidator,
    CircuitRequirements,
    calculate_resistor_divider,
    calculate_led_resistor,
    estimate_trace_width
)

from .file_packager import (
    manufacturing_packager,
    ManufacturingPackager
)

# Only import parametric_3d if CadQuery is available
try:
    from .parametric_3d import (
        Parametric3DGenerator,
        EnclosureSpec,
        generate_electronics_enclosure,
        CADQUERY_AVAILABLE
    )
except ImportError:
    CADQUERY_AVAILABLE = False
    Parametric3DGenerator = None
    EnclosureSpec = None
    generate_electronics_enclosure = None


__all__ = [
    # Component database
    'component_db',
    'Component',
    'ComponentCategory',
    'ComponentDatabase',

    # Circuit utilities
    'component_selector',
    'circuit_validator',
    'ComponentSelector',
    'CircuitValidator',
    'CircuitRequirements',
    'calculate_resistor_divider',
    'calculate_led_resistor',
    'estimate_trace_width',

    # File packaging
    'manufacturing_packager',
    'ManufacturingPackager',

    # 3D generation (if available)
    'Parametric3DGenerator',
    'EnclosureSpec',
    'generate_electronics_enclosure',
    'CADQUERY_AVAILABLE',
]
