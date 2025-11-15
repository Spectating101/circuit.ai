"""
Circuit Design Utilities

Helper functions for circuit design, component selection, and validation.
These are working implementations that don't require external APIs.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import math

from .component_database import component_db, ComponentCategory, Component


@dataclass
class CircuitRequirements:
    """Circuit design requirements."""
    input_voltage: Optional[float]
    output_voltage: Optional[float]
    current_rating: float
    features: List[str]  # ['wifi', 'bluetooth', 'display', etc.]
    sensors: List[str]  # ['temperature', 'humidity', 'pressure', etc.]
    constraints: Dict[str, Any]


class ComponentSelector:
    """Intelligent component selection based on requirements."""

    def __init__(self):
        """Initialize component selector."""
        self.db = component_db

    def select_power_supply_components(
        self,
        v_in: float,
        v_out: float,
        i_out: float
    ) -> List[Component]:
        """
        Select components for power supply circuit.

        Args:
            v_in: Input voltage
            v_out: Output voltage
            i_out: Output current

        Returns:
            List of selected components
        """
        components = []

        # Select voltage regulator
        regulator = self.db.select_voltage_regulator(v_in, v_out, i_out)
        if regulator:
            components.append(regulator)

            # Add input capacitor (typically 100uF electrolytic)
            components.append(self.db.get_component("CAP-100UF-16V"))

            # Add output capacitor (typically 100uF electrolytic)
            components.append(self.db.get_component("CAP-100UF-16V"))

            # Add ceramic bypass capacitors (0.1uF)
            components.append(self.db.get_component("CAP-0.1UF-0805"))
            components.append(self.db.get_component("CAP-0.1UF-0805"))

            # If it's a switching regulator, might need inductor and diode
            if regulator.specs.get('type') == 'switching':
                # Would add inductor and diode here
                pass

        return components

    def select_microcontroller_system(
        self,
        requirements: Dict[str, Any]
    ) -> List[Component]:
        """
        Select microcontroller and supporting components.

        Args:
            requirements: Requirements dict with wifi, bluetooth, sensors, etc.

        Returns:
            List of selected components
        """
        components = []

        # Select microcontroller
        mcu = self.db.select_microcontroller(requirements)
        if mcu:
            components.append(mcu)

            # Add crystal/oscillator if needed
            # (ESP32 has internal crystal, Arduino needs external)
            if 'ATMEGA' in mcu.part_number:
                # Would add 16MHz crystal and load capacitors
                pass

            # Add voltage regulator for 3.3V if needed
            if mcu.specs.get('voltage') == '3.3V':
                reg_3v3 = self.db.get_component("AMS1117-3.3")
                if reg_3v3:
                    components.append(reg_3v3)
                    # Add bypass capacitors
                    components.append(self.db.get_component("CAP-100UF-16V"))
                    components.append(self.db.get_component("CAP-0.1UF-0805"))

            # Add reset circuit
            # Pull-up resistor for reset
            components.append(self.db.get_component("RES-10K-0805"))
            # Reset button capacitor
            components.append(self.db.get_component("CAP-0.1UF-0805"))

        return components

    def select_sensor_components(
        self,
        sensor_types: List[str]
    ) -> List[Component]:
        """
        Select sensors based on requirements.

        Args:
            sensor_types: List of sensor types needed

        Returns:
            List of selected sensor components
        """
        components = []

        sensor_map = {
            'temperature': 'DHT22',
            'humidity': 'DHT22',  # DHT22 does both
            'pressure': 'BMP280',
            'altitude': 'BMP280',  # BMP280 does both
            'accelerometer': 'MPU6050',
            'gyroscope': 'MPU6050'  # MPU6050 does both
        }

        # Track which sensors we've already added
        added = set()

        for sensor_type in sensor_types:
            part_number = sensor_map.get(sensor_type.lower())
            if part_number and part_number not in added:
                sensor = self.db.get_component(part_number)
                if sensor:
                    components.append(sensor)
                    added.add(part_number)

                    # Add pull-up resistors for I2C sensors
                    if sensor.specs.get('interface') in ['I2C', 'i2c']:
                        # 4.7K pull-ups for SDA and SCL
                        # (Would add actual 4.7K resistors from db)
                        pass

        return components

    def select_display_component(
        self,
        display_type: str
    ) -> Optional[Component]:
        """
        Select display component.

        Args:
            display_type: Display type (oled, lcd, etc.)

        Returns:
            Selected display component
        """
        display_map = {
            'oled': 'SSD1306-0.96',
            'lcd': 'LCD1602-I2C',
            '0.96': 'SSD1306-0.96',
            '16x2': 'LCD1602-I2C'
        }

        part_number = display_map.get(display_type.lower())
        if part_number:
            return self.db.get_component(part_number)

        return None

    def design_complete_circuit(
        self,
        requirements: CircuitRequirements
    ) -> Dict[str, Any]:
        """
        Design complete circuit based on requirements.

        Args:
            requirements: Circuit requirements

        Returns:
            Dict with selected components and circuit design
        """
        all_components = []

        # Power supply section
        if requirements.input_voltage and requirements.output_voltage:
            power_components = self.select_power_supply_components(
                requirements.input_voltage,
                requirements.output_voltage,
                requirements.current_rating
            )
            all_components.extend(power_components)

        # Microcontroller section
        mcu_requirements = {
            'wifi': 'wifi' in requirements.features,
            'bluetooth': 'bluetooth' in requirements.features,
            'min_flash': 32,  # KB
            'min_ram': 2,  # KB
            'min_gpio': len(requirements.sensors) * 2 + 5  # Estimate
        }
        mcu_components = self.select_microcontroller_system(mcu_requirements)
        all_components.extend(mcu_components)

        # Sensor section
        if requirements.sensors:
            sensor_components = self.select_sensor_components(requirements.sensors)
            all_components.extend(sensor_components)

        # Display section
        if 'display' in requirements.features:
            display = self.select_display_component('oled')
            if display:
                all_components.append(display)

        # Connectors
        if 'usb' in requirements.features or 'usb-c' in requirements.features:
            usb = self.db.get_component("USB-C-RECEPTACLE")
            if usb:
                all_components.append(usb)

        # Generate BOM
        bom = self._generate_bom(all_components)

        # Calculate estimated cost
        total_cost = sum(item['total_price'] for item in bom)

        # Estimate PCB dimensions based on components
        pcb_dims = self._estimate_pcb_dimensions(all_components)

        return {
            'components': all_components,
            'bom': bom,
            'estimated_cost': total_cost,
            'pcb_dimensions': pcb_dims,
            'component_count': len(all_components)
        }

    def _generate_bom(self, components: List[Component]) -> List[Dict[str, Any]]:
        """Generate Bill of Materials."""
        # Count component quantities
        component_counts = {}
        for comp in components:
            part_num = comp.part_number
            if part_num in component_counts:
                component_counts[part_num]['quantity'] += 1
            else:
                component_counts[part_num] = {
                    'part_number': comp.part_number,
                    'manufacturer': comp.manufacturer,
                    'description': comp.description,
                    'quantity': 1,
                    'unit_price': comp.typical_price,
                    'total_price': comp.typical_price,
                    'footprint': comp.footprint
                }

        # Update total prices
        for item in component_counts.values():
            item['total_price'] = item['unit_price'] * item['quantity']

        # Convert to list sorted by total price (most expensive first)
        bom = sorted(
            component_counts.values(),
            key=lambda x: x['total_price'],
            reverse=True
        )

        return bom

    def _estimate_pcb_dimensions(self, components: List[Component]) -> Dict[str, float]:
        """Estimate PCB dimensions based on components."""
        # Calculate total component area
        total_area = 0.0
        max_height = 0.0

        for comp in components:
            dims = comp.dimensions
            comp_area = dims.get('width', 5) * dims.get('length', 5)
            total_area += comp_area

            comp_height = dims.get('height', 0)
            max_height = max(max_height, comp_height)

        # Add 50% extra space for routing and margins
        effective_area = total_area * 1.5

        # Assume aspect ratio of 1.5:1 (rectangular)
        width = math.sqrt(effective_area * 1.5)
        height = effective_area / width

        # Round up to nearest 5mm
        width = math.ceil(width / 5) * 5
        height = math.ceil(height / 5) * 5

        return {
            'width': width,
            'height': height,
            'thickness': 1.6,  # Standard PCB thickness
            'max_component_height': max_height
        }


class CircuitValidator:
    """Validate circuit designs."""

    def validate_power_supply(
        self,
        v_in: float,
        v_out: float,
        i_out: float,
        regulator: Component
    ) -> Tuple[bool, List[str]]:
        """
        Validate power supply design.

        Returns:
            (valid, list of issues)
        """
        issues = []

        specs = regulator.specs

        # Check input voltage
        if v_in > specs.get('v_in_max', float('inf')):
            issues.append(
                f"Input voltage {v_in}V exceeds regulator max {specs.get('v_in_max')}V"
            )

        # Check output current
        if i_out > specs.get('i_max', 0):
            issues.append(
                f"Output current {i_out}A exceeds regulator max {specs.get('i_max')}A"
            )

        # Check dropout voltage (for linear regulators)
        if 'dropout' in specs:
            dropout = specs['dropout']
            if (v_in - v_out) < dropout:
                issues.append(
                    f"Insufficient headroom: {v_in - v_out}V < {dropout}V dropout"
                )

        # Calculate power dissipation
        power_dissipation = (v_in - v_out) * i_out

        # Check if heatsink needed (rule of thumb: > 1W needs heatsink)
        if power_dissipation > 1.0:
            issues.append(
                f"High power dissipation ({power_dissipation:.1f}W) - heatsink recommended"
            )

        return len(issues) == 0, issues

    def validate_i2c_bus(
        self,
        devices: List[Component],
        pull_up_value: float = 4700  # ohms
    ) -> Tuple[bool, List[str]]:
        """
        Validate I2C bus design.

        Args:
            devices: List of I2C devices on bus
            pull_up_value: Pull-up resistor value in ohms

        Returns:
            (valid, list of issues)
        """
        issues = []

        # Check number of devices (I2C supports up to 127 devices theoretically)
        if len(devices) > 8:
            issues.append(
                f"Large number of I2C devices ({len(devices)}) may cause bus issues"
            )

        # Check total bus capacitance
        # Standard mode: max 400pF
        # Fast mode: max 400pF
        # Each device adds ~10pF, each cm of trace adds ~1pF
        estimated_capacitance = len(devices) * 10 + 20  # Add 20pF for traces

        if estimated_capacitance > 400:
            issues.append(
                f"Bus capacitance ({estimated_capacitance}pF) may exceed 400pF limit"
            )

        # Validate pull-up resistor value
        # For 3.3V with 400pF: R_min = rise_time / (0.8473 * C_bus)
        # For 400kHz (fast mode): rise_time < 300ns
        if pull_up_value < 1000:
            issues.append("Pull-up resistor too small (< 1K)")
        if pull_up_value > 10000:
            issues.append("Pull-up resistor too large (> 10K)")

        return len(issues) == 0, issues


# Helper functions
def calculate_resistor_divider(v_in: float, v_out: float, i_load: float = 0.001) -> Tuple[float, float]:
    """
    Calculate resistor divider values.

    Args:
        v_in: Input voltage
        v_out: Desired output voltage
        i_load: Load current (default 1mA for low current draw)

    Returns:
        (R1, R2) resistor values in ohms
    """
    # R2 / (R1 + R2) = v_out / v_in
    # Choose R2 based on desired current
    R2 = v_out / i_load

    # Calculate R1
    R1 = R2 * ((v_in / v_out) - 1)

    return R1, R2


def calculate_led_resistor(v_supply: float, v_led: float, i_led: float) -> float:
    """
    Calculate LED current-limiting resistor.

    Args:
        v_supply: Supply voltage
        v_led: LED forward voltage
        i_led: Desired LED current (typically 0.02 A = 20mA)

    Returns:
        Resistor value in ohms
    """
    return (v_supply - v_led) / i_led


def estimate_trace_width(current: float, copper_thickness_oz: float = 1.0, temp_rise: float = 10.0) -> float:
    """
    Estimate required PCB trace width.

    Args:
        current: Current in amps
        copper_thickness_oz: Copper thickness in oz (1oz = 35um)
        temp_rise: Acceptable temperature rise in °C

    Returns:
        Trace width in mm
    """
    # Using IPC-2221 formula
    # Area [mils²] = (Current [A] / (k * (Temp_rise [°C])^0.44))^(1/0.725)
    # where k = 0.048 for external layers, 0.024 for internal

    k = 0.048  # External layer
    area_mils_sq = (current / (k * (temp_rise ** 0.44))) ** (1 / 0.725)

    # Width = Area / thickness
    # 1 oz copper = 1.378 mils thick
    thickness_mils = copper_thickness_oz * 1.378
    width_mils = area_mils_sq / thickness_mils

    # Convert mils to mm
    width_mm = width_mils * 0.0254

    # Round up to nearest 0.1mm
    return math.ceil(width_mm * 10) / 10


# Singleton instances
component_selector = ComponentSelector()
circuit_validator = CircuitValidator()
