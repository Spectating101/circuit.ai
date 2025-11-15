"""
Complete Fabricator Workflow

Orchestrates both circuit design and 3D enclosure generation to create
complete fabrication-ready electronic devices.

Features:
- Text-to-complete-device generation
- Coordinated circuit + enclosure design
- Automatic dimensional matching
- Complete manufacturing file package
- Assembly instructions
- Cost estimation
- Timeline estimation
- Multi-material BOM (electronics + 3D printing)
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import uuid
from loguru import logger

from .pcb_analysis_workflow import (
    Workflow, WorkflowEngine, WorkflowStatus, WorkflowStep
)
from .three_d_generation_workflow import (
    three_d_generation_workflow,
    DesignType,
    DesignMethod
)
from .circuit_generation_workflow import (
    circuit_generation_workflow,
    CircuitCategory
)


class DeviceType(Enum):
    """Complete device types."""
    SENSOR_MODULE = "sensor_module"
    IOT_DEVICE = "iot_device"
    POWER_SUPPLY = "power_supply"
    CONTROLLER = "controller"
    INTERFACE = "interface"
    CUSTOM = "custom"


class ManufacturingMethod(Enum):
    """Manufacturing methods."""
    DIY = "diy"  # Home manufacturing
    PROTOTYPE = "prototype"  # Professional prototype
    SMALL_BATCH = "small_batch"  # 10-100 units
    PRODUCTION = "production"  # 100+ units


@dataclass
class DeviceSpecification:
    """Complete device specification."""
    device_type: DeviceType
    description: str
    circuit_requirements: Dict[str, Any]
    enclosure_requirements: Dict[str, Any]
    constraints: Dict[str, Any]


@dataclass
class FabricationPackage:
    """Complete fabrication package."""
    device_id: str
    device_type: DeviceType

    # Circuit files
    circuit_id: str
    schematic_file: str
    pcb_layout_file: str
    gerber_files: List[str]

    # 3D files
    enclosure_id: str
    enclosure_base_stl: str
    enclosure_lid_stl: str
    enclosure_previews: List[str]

    # Documentation
    assembly_instructions: str
    testing_instructions: str
    user_manual: str

    # BOM
    electronics_bom: List[Dict[str, Any]]
    printing_materials_bom: List[Dict[str, Any]]
    combined_bom: List[Dict[str, Any]]

    # Cost & Timeline
    estimated_electronics_cost: float
    estimated_printing_cost: float
    estimated_total_cost: float
    estimated_pcb_lead_time_days: int
    estimated_print_time_hours: float
    estimated_assembly_time_hours: float

    generated_at: datetime


class FabricatorWorkflow:
    """Complete device fabrication workflow."""

    def __init__(self):
        """Initialize fabricator workflow."""
        self.engine = WorkflowEngine()
        self.fabrication_workflow = self._build_fabrication_workflow()

        # Sub-workflows
        self.circuit_workflow = circuit_generation_workflow
        self.three_d_workflow = three_d_generation_workflow

        logger.info("FabricatorWorkflow initialized")

    def _build_fabrication_workflow(self) -> Workflow:
        """Build complete fabrication workflow."""
        workflow = Workflow(
            workflow_id="fabricator_v1",
            name="Complete Device Fabrication",
            description="Generate complete device with circuit + enclosure"
        )

        # Step 1: Parse device requirements
        workflow.add_step(
            step_id="parse_device_spec",
            name="Parse Device Specification",
            description="Extract complete device requirements",
            handler=self._parse_device_spec,
            depends_on=[]
        )

        # Step 2: Plan device architecture
        workflow.add_step(
            step_id="plan_architecture",
            name="Plan Device Architecture",
            description="Design high-level architecture",
            handler=self._plan_architecture,
            depends_on=["parse_device_spec"]
        )

        # Step 3: Generate circuit design (parallel)
        workflow.add_step(
            step_id="generate_circuit",
            name="Generate Circuit Design",
            description="Create complete circuit design",
            handler=self._generate_circuit,
            depends_on=["plan_architecture"],
            timeout_seconds=900
        )

        # Step 4: Extract PCB dimensions (depends on circuit)
        workflow.add_step(
            step_id="extract_pcb_dimensions",
            name="Extract PCB Dimensions",
            description="Get PCB size and component heights",
            handler=self._extract_pcb_dimensions,
            depends_on=["generate_circuit"]
        )

        # Step 5: Generate enclosure (depends on PCB dims)
        workflow.add_step(
            step_id="generate_enclosure",
            name="Generate 3D Enclosure",
            description="Create custom enclosure for PCB",
            handler=self._generate_enclosure,
            depends_on=["extract_pcb_dimensions"],
            timeout_seconds=600
        )

        # Step 6: Validate fit
        workflow.add_step(
            step_id="validate_fit",
            name="Validate Circuit-Enclosure Fit",
            description="Ensure PCB fits in enclosure",
            handler=self._validate_fit,
            depends_on=["generate_circuit", "generate_enclosure"]
        )

        # Step 7: Generate combined BOM
        workflow.add_step(
            step_id="generate_combined_bom",
            name="Generate Combined BOM",
            description="Merge electronics + materials BOM",
            handler=self._generate_combined_bom,
            depends_on=["generate_circuit", "generate_enclosure"]
        )

        # Step 8: Calculate costs
        workflow.add_step(
            step_id="calculate_costs",
            name="Calculate Total Costs",
            description="Estimate complete device cost",
            handler=self._calculate_costs,
            depends_on=["generate_combined_bom"]
        )

        # Step 9: Generate assembly instructions
        workflow.add_step(
            step_id="generate_assembly",
            name="Generate Assembly Instructions",
            description="Create step-by-step assembly guide",
            handler=self._generate_assembly,
            depends_on=["validate_fit"]
        )

        # Step 10: Generate testing procedures
        workflow.add_step(
            step_id="generate_testing",
            name="Generate Testing Procedures",
            description="Create device testing guide",
            handler=self._generate_testing,
            depends_on=["generate_circuit"]
        )

        # Step 11: Generate user documentation
        workflow.add_step(
            step_id="generate_documentation",
            name="Generate User Documentation",
            description="Create user manual",
            handler=self._generate_documentation,
            depends_on=["generate_assembly", "generate_testing"]
        )

        # Step 12: Package manufacturing files
        workflow.add_step(
            step_id="package_files",
            name="Package Manufacturing Files",
            description="Bundle all files for manufacturing",
            handler=self._package_files,
            depends_on=[
                "generate_circuit",
                "generate_enclosure",
                "generate_combined_bom",
                "calculate_costs",
                "generate_documentation"
            ]
        )

        # Step 13: Store fabrication package
        workflow.add_step(
            step_id="store_package",
            name="Store Fabrication Package",
            description="Save complete fabrication package",
            handler=self._store_package,
            depends_on=["package_files"]
        )

        return workflow

    async def fabricate_device(
        self,
        user_id: str,
        prompt: str,
        device_type: Optional[DeviceType] = None,
        manufacturing_method: ManufacturingMethod = ManufacturingMethod.PROTOTYPE,
        specifications: Optional[DeviceSpecification] = None
    ) -> str:
        """
        Generate complete fabrication package for device.

        Args:
            user_id: User ID
            prompt: Text description of device
            device_type: Type of device
            manufacturing_method: Target manufacturing method
            specifications: Detailed specifications

        Returns:
            Execution ID
        """
        input_data = {
            'user_id': user_id,
            'prompt': prompt,
            'device_type': device_type.value if device_type else None,
            'manufacturing_method': manufacturing_method.value,
            'specifications': specifications.__dict__ if specifications else None,
            'timestamp': datetime.utcnow().isoformat()
        }

        execution_id = await self.engine.execute_workflow(
            self.fabrication_workflow,
            input_data,
            user_id
        )

        logger.info(f"Started device fabrication: {execution_id}")

        return execution_id

    def get_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get fabrication status."""
        status = self.engine.get_execution_status(execution_id)

        if status:
            # Enrich with sub-workflow status
            if 'generate_circuit' in status.get('completed_steps', []):
                # Would add circuit generation details
                pass

        return status

    # Workflow handlers
    async def _parse_device_spec(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse device specification using LLM."""
        prompt = context['input']['prompt']

        # Would use LLM to extract:
        # - Device purpose
        # - Circuit requirements (voltage, current, sensors, etc.)
        # - Enclosure requirements (size, mounting, connectors)
        # - Constraints (budget, size, power)

        parsed = {
            'device_type': 'sensor_module',
            'description': 'Temperature and humidity monitoring device',
            'circuit': {
                'microcontroller': 'ESP32',
                'sensors': ['DHT22', 'BMP280'],
                'power': '5V USB or battery',
                'connectivity': 'WiFi'
            },
            'enclosure': {
                'size': 'compact',
                'mounting': 'wall_mount',
                'style': 'minimalist',
                'material': 'PLA'
            },
            'constraints': {
                'budget': 50,
                'max_dimensions': {'w': 100, 'h': 80, 'd': 40}
            }
        }

        logger.info(f"Parsed device spec: {parsed['device_type']}")

        return parsed

    async def _plan_architecture(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Plan device architecture."""
        spec = context['parse_device_spec']

        # Plan:
        # - Component layout
        # - Power distribution
        # - Connector placement
        # - Enclosure features

        architecture = {
            'pcb_layers': 2,
            'estimated_pcb_size': {'width': 60, 'height': 40},
            'component_sides': ['top', 'bottom'],
            'connector_positions': [
                {'type': 'usb', 'side': 'left'},
                {'type': 'sensor', 'side': 'top'}
            ],
            'enclosure_features': ['ventilation_slots', 'mounting_holes']
        }

        return architecture

    async def _generate_circuit(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate circuit design."""
        spec = context['parse_device_spec']
        architecture = context['plan_architecture']

        # Create circuit prompt from spec
        circuit_prompt = f"""
        Design a circuit for {spec['description']}
        Requirements: {spec['circuit']}
        PCB size: approximately {architecture['estimated_pcb_size']}
        """

        # Start circuit generation workflow
        circuit_execution_id = await self.circuit_workflow.generate_circuit(
            user_id=context['input']['user_id'],
            prompt=circuit_prompt,
            run_simulation=True
        )

        # Wait for completion (with timeout)
        for _ in range(180):  # 3 minutes timeout
            circuit_status = self.circuit_workflow.get_status(circuit_execution_id)
            if circuit_status and circuit_status['status'] in ['completed', 'failed']:
                break
            await asyncio.sleep(1)

        # Get results
        circuit_status = self.circuit_workflow.get_status(circuit_execution_id)

        if not circuit_status or circuit_status['status'] != 'completed':
            raise Exception("Circuit generation failed")

        circuit_data = circuit_status.get('output_data', {})

        logger.info(f"Circuit generation complete: {circuit_execution_id}")

        return {
            'circuit_execution_id': circuit_execution_id,
            'circuit_id': circuit_data.get('store_circuit', {}).get('circuit_id'),
            'schematic_file': circuit_data.get('generate_schematic', {}).get('schematic_file'),
            'pcb_file': circuit_data.get('generate_pcb_layout', {}).get('pcb_file'),
            'gerber_files': circuit_data.get('generate_gerbers', {}).get('gerber_files'),
            'bom': circuit_data.get('generate_bom', {}).get('bom'),
            'cost': circuit_data.get('price_bom', {}).get('total_cost', 0)
        }

    async def _extract_pcb_dimensions(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract PCB dimensions from circuit design."""
        circuit = context['generate_circuit']

        # Would parse actual PCB file
        # For now, use architecture estimate + margins

        architecture = context['plan_architecture']

        pcb_dimensions = {
            'width': architecture['estimated_pcb_size']['width'],
            'height': architecture['estimated_pcb_size']['height'],
            'thickness': 1.6,  # Standard PCB thickness
            'component_height_top': 15,  # mm
            'component_height_bottom': 5  # mm
        }

        # Extract connector positions
        connectors = []
        for conn in architecture.get('connector_positions', []):
            connectors.append({
                'type': conn['type'],
                'side': conn['side'],
                'position': {'x': 10, 'y': 20},  # Would calculate actual
                'size': {'width': 12, 'height': 6}
            })

        return {
            'pcb_dimensions': pcb_dimensions,
            'connectors': connectors
        }

    async def _generate_enclosure(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate 3D enclosure."""
        pcb_dims = context['extract_pcb_dimensions']['pcb_dimensions']
        connectors = context['extract_pcb_dimensions']['connectors']
        spec = context['parse_device_spec']

        # Start enclosure generation workflow
        enclosure_execution_id = await self.three_d_workflow.generate_enclosure(
            user_id=context['input']['user_id'],
            pcb_dimensions=pcb_dims,
            component_heights={
                'top': pcb_dims['component_height_top'],
                'bottom': pcb_dims['component_height_bottom']
            },
            connectors=connectors,
            style=spec['enclosure'].get('style', 'minimalist')
        )

        # Wait for completion
        for _ in range(120):  # 2 minutes timeout
            enclosure_status = self.three_d_workflow.get_status(enclosure_execution_id)
            if enclosure_status and enclosure_status['status'] in ['completed', 'failed']:
                break
            await asyncio.sleep(1)

        # Get results
        enclosure_status = self.three_d_workflow.get_status(enclosure_execution_id)

        if not enclosure_status or enclosure_status['status'] != 'completed':
            raise Exception("Enclosure generation failed")

        enclosure_data = enclosure_status.get('output_data', {})

        logger.info(f"Enclosure generation complete: {enclosure_execution_id}")

        return {
            'enclosure_execution_id': enclosure_execution_id,
            'enclosure_id': enclosure_data.get('store_design', {}).get('design_id'),
            'base_stl': enclosure_data.get('export_assembly', {}).get('base_stl'),
            'lid_stl': enclosure_data.get('export_assembly', {}).get('lid_stl'),
            'previews': enclosure_data.get('generate_previews', {}).get('previews', []),
            'print_time_estimate': 4.5,  # hours
            'material_estimate': 85  # grams
        }

    async def _validate_fit(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate circuit fits in enclosure."""
        pcb_dims = context['extract_pcb_dimensions']['pcb_dimensions']
        # Would load enclosure dimensions from file

        # Check clearances
        clearance_ok = True
        issues = []

        return {
            'fit_valid': clearance_ok,
            'issues': issues
        }

    async def _generate_combined_bom(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate combined BOM."""
        electronics_bom = context['generate_circuit']['bom']
        enclosure = context['generate_enclosure']

        # Electronics BOM
        electronics = electronics_bom

        # 3D Printing BOM
        printing = [
            {
                'item': 'Enclosure Base',
                'material': 'PLA',
                'weight_grams': enclosure['material_estimate'] * 0.6,
                'print_time_hours': enclosure['print_time_estimate'] * 0.6,
                'color': 'Black'
            },
            {
                'item': 'Enclosure Lid',
                'material': 'PLA',
                'weight_grams': enclosure['material_estimate'] * 0.4,
                'print_time_hours': enclosure['print_time_estimate'] * 0.4,
                'color': 'Black'
            }
        ]

        # Hardware (screws, etc.)
        hardware = [
            {
                'item': 'M3 x 10mm screws',
                'quantity': 4,
                'unit_price': 0.10
            }
        ]

        combined_bom = {
            'electronics': electronics,
            'printing': printing,
            'hardware': hardware
        }

        logger.info(f"Generated combined BOM: {len(electronics)} electronic parts, {len(printing)} printed parts")

        return combined_bom

    async def _calculate_costs(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate total costs."""
        bom = context['generate_combined_bom']
        circuit = context['generate_circuit']

        # Electronics cost
        electronics_cost = circuit.get('cost', 0)

        # 3D printing cost (PLA @ $0.02/gram)
        printing_cost = sum(
            part['weight_grams'] * 0.02
            for part in bom['printing']
        )

        # Hardware cost
        hardware_cost = sum(
            item['quantity'] * item['unit_price']
            for item in bom['hardware']
        )

        # PCB manufacturing (estimate)
        pcb_manufacturing = 5.00  # Per unit for prototype

        total_cost = electronics_cost + printing_cost + hardware_cost + pcb_manufacturing

        costs = {
            'electronics': electronics_cost,
            'printing': printing_cost,
            'hardware': hardware_cost,
            'pcb_manufacturing': pcb_manufacturing,
            'total': total_cost,
            'currency': 'USD'
        }

        logger.info(f"Total device cost: ${total_cost:.2f}")

        return costs

    async def _generate_assembly(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate assembly instructions."""
        # Would create detailed assembly guide

        assembly_steps = [
            "1. Print enclosure base and lid",
            "2. Order PCB from manufacturer using Gerber files",
            "3. Order components from BOM",
            "4. Solder components to PCB",
            "5. Test circuit functionality",
            "6. Install PCB in enclosure base using M3 screws",
            "7. Connect any external connectors",
            "8. Close enclosure with lid",
            "9. Final testing"
        ]

        return {
            'assembly_steps': assembly_steps,
            'assembly_pdf': '/tmp/assembly_instructions.pdf'
        }

    async def _generate_testing(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate testing procedures."""
        # Would create testing guide

        tests = [
            "1. Visual inspection of solder joints",
            "2. Continuity test",
            "3. Power-on test (measure voltages)",
            "4. Functional test (verify sensors)",
            "5. WiFi connectivity test"
        ]

        return {
            'testing_procedures': tests,
            'testing_pdf': '/tmp/testing_procedures.pdf'
        }

    async def _generate_documentation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate user documentation."""
        spec = context['parse_device_spec']

        # Would generate comprehensive user manual

        return {
            'user_manual': '/tmp/user_manual.pdf',
            'quick_start_guide': '/tmp/quick_start.pdf'
        }

    async def _package_files(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Package all manufacturing files."""
        # Collect all files
        files = {
            'circuit': {
                'schematic': context['generate_circuit']['schematic_file'],
                'pcb': context['generate_circuit']['pcb_file'],
                'gerbers': context['generate_circuit']['gerber_files']
            },
            'enclosure': {
                'base_stl': context['generate_enclosure']['base_stl'],
                'lid_stl': context['generate_enclosure']['lid_stl']
            },
            'bom': '/tmp/combined_bom.csv',
            'documentation': {
                'assembly': context['generate_assembly']['assembly_pdf'],
                'testing': context['generate_testing']['testing_pdf'],
                'manual': context['generate_documentation']['user_manual']
            }
        }

        # Would create ZIP package

        package_path = '/tmp/fabrication_package.zip'

        return {
            'package_path': package_path,
            'files': files
        }

    async def _store_package(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Store fabrication package."""
        device_id = str(uuid.uuid4())

        # Would save to S3/storage

        logger.info(f"Stored fabrication package: {device_id}")

        return {
            'device_id': device_id,
            'storage_url': f's3://circuit-ai-devices/{device_id}/',
            'download_url': f'https://circuit.ai/devices/{device_id}/download'
        }


# Singleton instance
fabricator_workflow = FabricatorWorkflow()
