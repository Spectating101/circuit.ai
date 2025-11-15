"""
Electronic Component Database

Common components with specifications, pricing, and footprints.
This is a working database that can be used immediately without external APIs.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class ComponentCategory(Enum):
    """Component categories."""
    MICROCONTROLLER = "microcontroller"
    SENSOR = "sensor"
    POWER = "power"
    PASSIVE = "passive"
    CONNECTOR = "connector"
    DISPLAY = "display"
    WIRELESS = "wireless"
    MEMORY = "memory"
    INTERFACE = "interface"


@dataclass
class Component:
    """Electronic component specification."""
    part_number: str
    manufacturer: str
    category: ComponentCategory
    description: str
    specs: Dict[str, Any]
    footprint: str
    dimensions: Dict[str, float]  # mm
    typical_price: float  # USD
    datasheet_url: Optional[str] = None


# Component Database
COMPONENT_DATABASE: Dict[str, Component] = {
    # Microcontrollers
    "ESP32-WROOM-32": Component(
        part_number="ESP32-WROOM-32",
        manufacturer="Espressif",
        category=ComponentCategory.MICROCONTROLLER,
        description="WiFi + Bluetooth MCU Module",
        specs={
            "cpu": "Xtensa dual-core 32-bit",
            "clock": "240MHz",
            "flash": "4MB",
            "ram": "520KB",
            "wifi": "802.11 b/g/n",
            "bluetooth": "4.2",
            "gpio": 34,
            "voltage": "3.3V",
            "current_active": "160mA",
            "current_sleep": "10uA"
        },
        footprint="Module_ESP32",
        dimensions={"width": 18, "length": 25.5, "height": 3.1},
        typical_price=4.50
    ),

    "ATMEGA328P-PU": Component(
        part_number="ATMEGA328P-PU",
        manufacturer="Microchip",
        category=ComponentCategory.MICROCONTROLLER,
        description="8-bit AVR Microcontroller (Arduino compatible)",
        specs={
            "cpu": "AVR 8-bit",
            "clock": "20MHz",
            "flash": "32KB",
            "ram": "2KB",
            "eeprom": "1KB",
            "gpio": 23,
            "voltage": "5V",
            "current_active": "15mA"
        },
        footprint="DIP-28",
        dimensions={"width": 7.62, "length": 35.56, "height": 4.5},
        typical_price=2.80
    ),

    "STM32F103C8T6": Component(
        part_number="STM32F103C8T6",
        manufacturer="STMicroelectronics",
        category=ComponentCategory.MICROCONTROLLER,
        description="ARM Cortex-M3 MCU (Blue Pill)",
        specs={
            "cpu": "ARM Cortex-M3",
            "clock": "72MHz",
            "flash": "64KB",
            "ram": "20KB",
            "gpio": 37,
            "voltage": "3.3V",
            "current_active": "27mA"
        },
        footprint="LQFP-48",
        dimensions={"width": 7, "length": 7, "height": 1.4},
        typical_price=3.20
    ),

    # Sensors
    "DHT22": Component(
        part_number="DHT22",
        manufacturer="Aosong",
        category=ComponentCategory.SENSOR,
        description="Temperature & Humidity Sensor",
        specs={
            "temp_range": "-40 to 80°C",
            "temp_accuracy": "±0.5°C",
            "humidity_range": "0-100% RH",
            "humidity_accuracy": "±2% RH",
            "voltage": "3.3-5V",
            "current": "1.5mA",
            "protocol": "1-wire"
        },
        footprint="DHT22",
        dimensions={"width": 15.1, "length": 25, "height": 7.7},
        typical_price=3.20
    ),

    "BMP280": Component(
        part_number="BMP280",
        manufacturer="Bosch",
        category=ComponentCategory.SENSOR,
        description="Barometric Pressure & Temperature Sensor",
        specs={
            "pressure_range": "300-1100 hPa",
            "pressure_accuracy": "±1 hPa",
            "temp_range": "-40 to 85°C",
            "voltage": "1.8-3.6V",
            "current": "2.7uA",
            "interface": "I2C, SPI"
        },
        footprint="LGA-8",
        dimensions={"width": 2.0, "length": 2.5, "height": 0.93},
        typical_price=2.50
    ),

    "MPU6050": Component(
        part_number="MPU6050",
        manufacturer="InvenSense",
        category=ComponentCategory.SENSOR,
        description="6-Axis Gyroscope & Accelerometer",
        specs={
            "gyro_range": "±250 to ±2000 °/s",
            "accel_range": "±2 to ±16g",
            "voltage": "2.375-3.46V",
            "current": "3.9mA",
            "interface": "I2C"
        },
        footprint="QFN-24",
        dimensions={"width": 4, "length": 4, "height": 0.9},
        typical_price=1.80
    ),

    # Power Components
    "LM7805": Component(
        part_number="LM7805",
        manufacturer="Texas Instruments",
        category=ComponentCategory.POWER,
        description="5V Linear Voltage Regulator",
        specs={
            "v_in_max": 35,
            "v_out": 5.0,
            "i_max": 1.5,
            "dropout": 2.0,
            "tolerance": "±4%"
        },
        footprint="TO-220",
        dimensions={"width": 10.16, "length": 4.7, "height": 15.9},
        typical_price=0.50
    ),

    "AMS1117-3.3": Component(
        part_number="AMS1117-3.3",
        manufacturer="Advanced Monolithic Systems",
        category=ComponentCategory.POWER,
        description="3.3V Linear Voltage Regulator",
        specs={
            "v_in_max": 15,
            "v_out": 3.3,
            "i_max": 1.0,
            "dropout": 1.1,
            "tolerance": "±1%"
        },
        footprint="SOT-223",
        dimensions={"width": 3.5, "length": 6.5, "height": 1.8},
        typical_price=0.35
    ),

    "LM2596": Component(
        part_number="LM2596",
        manufacturer="Texas Instruments",
        category=ComponentCategory.POWER,
        description="Buck Switching Regulator",
        specs={
            "v_in_max": 40,
            "v_out_min": 1.25,
            "v_out_max": 37,
            "i_max": 3.0,
            "efficiency": 0.85,
            "frequency": "150kHz"
        },
        footprint="TO-220-5",
        dimensions={"width": 10.16, "length": 4.7, "height": 15.9},
        typical_price=1.20
    ),

    # Passive Components
    "RES-10K-0805": Component(
        part_number="RC0805FR-0710KL",
        manufacturer="Yageo",
        category=ComponentCategory.PASSIVE,
        description="10K Ohm Resistor 0805",
        specs={
            "resistance": 10000,
            "tolerance": "1%",
            "power": 0.125,
            "package": "0805"
        },
        footprint="R_0805",
        dimensions={"width": 1.25, "length": 2.0, "height": 0.6},
        typical_price=0.01
    ),

    "CAP-100UF-16V": Component(
        part_number="UWT1C101MCL1GS",
        manufacturer="Nichicon",
        category=ComponentCategory.PASSIVE,
        description="100uF 16V Electrolytic Capacitor",
        specs={
            "capacitance": 100e-6,
            "voltage": 16,
            "tolerance": "20%",
            "esr": 0.5
        },
        footprint="CP_Radial_D5.0mm_P2.00mm",
        dimensions={"diameter": 5.0, "height": 11},
        typical_price=0.15
    ),

    "CAP-0.1UF-0805": Component(
        part_number="CL21B104KBCNNNC",
        manufacturer="Samsung",
        category=ComponentCategory.PASSIVE,
        description="0.1uF 50V Ceramic Capacitor 0805",
        specs={
            "capacitance": 0.1e-6,
            "voltage": 50,
            "tolerance": "10%",
            "package": "0805"
        },
        footprint="C_0805",
        dimensions={"width": 1.25, "length": 2.0, "height": 0.6},
        typical_price=0.02
    ),

    # Displays
    "SSD1306-0.96": Component(
        part_number="SSD1306",
        manufacturer="Solomon Systech",
        category=ComponentCategory.DISPLAY,
        description="0.96\" OLED Display 128x64 I2C",
        specs={
            "resolution": "128x64",
            "size": 0.96,
            "interface": "I2C",
            "voltage": "3.3-5V",
            "current": "20mA",
            "colors": "monochrome"
        },
        footprint="OLED_0.96",
        dimensions={"width": 27, "length": 27, "height": 4},
        typical_price=5.00
    ),

    "LCD1602-I2C": Component(
        part_number="LCD1602A",
        manufacturer="Generic",
        category=ComponentCategory.DISPLAY,
        description="16x2 Character LCD with I2C",
        specs={
            "chars": "16x2",
            "interface": "I2C",
            "voltage": "5V",
            "current": "50mA",
            "backlight": "LED"
        },
        footprint="LCD_16x2",
        dimensions={"width": 36, "length": 80, "height": 13.5},
        typical_price=3.50
    ),

    # Connectors
    "USB-C-RECEPTACLE": Component(
        part_number="USB4105-GF-A",
        manufacturer="GCT",
        category=ComponentCategory.CONNECTOR,
        description="USB Type-C Receptacle",
        specs={
            "type": "USB-C",
            "pins": 16,
            "current_rating": 3.0,
            "mounting": "SMD"
        },
        footprint="USB_C_Receptacle",
        dimensions={"width": 8.94, "length": 7.35, "height": 3.16},
        typical_price=0.80
    ),

    "BARREL-JACK-5.5x2.1": Component(
        part_number="PJ-002AH",
        manufacturer="CUI Devices",
        category=ComponentCategory.CONNECTOR,
        description="DC Barrel Jack 5.5x2.1mm",
        specs={
            "outer_diameter": 5.5,
            "inner_diameter": 2.1,
            "voltage_rating": 24,
            "current_rating": 5.0,
            "mounting": "THT"
        },
        footprint="BarrelJack_Horizontal",
        dimensions={"width": 14, "length": 14, "height": 11},
        typical_price=0.40
    ),

    # Memory
    "24LC256": Component(
        part_number="24LC256-I/P",
        manufacturer="Microchip",
        category=ComponentCategory.MEMORY,
        description="256K I2C EEPROM",
        specs={
            "capacity": "256Kbit",
            "interface": "I2C",
            "voltage": "2.5-5.5V",
            "speed": "400kHz",
            "endurance": "1M cycles"
        },
        footprint="DIP-8",
        dimensions={"width": 7.62, "length": 9.27, "height": 4.5},
        typical_price=0.75
    ),
}


class ComponentDatabase:
    """Component database with search and selection capabilities."""

    def __init__(self):
        """Initialize component database."""
        self.components = COMPONENT_DATABASE

    def search_by_category(self, category: ComponentCategory) -> List[Component]:
        """Search components by category."""
        return [
            comp for comp in self.components.values()
            if comp.category == category
        ]

    def search_by_specs(
        self,
        category: Optional[ComponentCategory] = None,
        **specs
    ) -> List[Component]:
        """
        Search components by specifications.

        Example:
            search_by_specs(
                category=ComponentCategory.POWER,
                v_out=5.0,
                i_max_min=1.0
            )
        """
        results = []

        for comp in self.components.values():
            # Filter by category
            if category and comp.category != category:
                continue

            # Filter by specs
            match = True
            for key, value in specs.items():
                # Handle min/max suffixes
                if key.endswith('_min'):
                    base_key = key[:-4]
                    if base_key in comp.specs and comp.specs[base_key] < value:
                        match = False
                        break
                elif key.endswith('_max'):
                    base_key = key[:-4]
                    if base_key in comp.specs and comp.specs[base_key] > value:
                        match = False
                        break
                else:
                    if key in comp.specs and comp.specs[key] != value:
                        match = False
                        break

            if match:
                results.append(comp)

        return results

    def get_component(self, part_number: str) -> Optional[Component]:
        """Get component by part number."""
        return self.components.get(part_number)

    def select_voltage_regulator(
        self,
        v_in: float,
        v_out: float,
        i_out: float
    ) -> Optional[Component]:
        """
        Select appropriate voltage regulator.

        Args:
            v_in: Input voltage
            v_out: Desired output voltage
            i_out: Output current requirement

        Returns:
            Best matching voltage regulator
        """
        regulators = self.search_by_category(ComponentCategory.POWER)

        # Filter suitable regulators
        suitable = []
        for reg in regulators:
            specs = reg.specs

            # Check input voltage
            if v_in > specs.get('v_in_max', 0):
                continue

            # Check output voltage (allow 10% tolerance)
            if 'v_out' in specs:
                if abs(specs['v_out'] - v_out) / v_out > 0.1:
                    continue

            # Check current capability
            if i_out > specs.get('i_max', 0):
                continue

            suitable.append(reg)

        # Sort by efficiency (prefer switching over linear)
        suitable.sort(
            key=lambda r: r.specs.get('efficiency', 0),
            reverse=True
        )

        return suitable[0] if suitable else None

    def select_microcontroller(
        self,
        requirements: Dict[str, Any]
    ) -> Optional[Component]:
        """
        Select appropriate microcontroller.

        Args:
            requirements: Dict with keys like:
                - wifi: bool
                - bluetooth: bool
                - min_flash: int (KB)
                - min_ram: int (KB)
                - min_gpio: int

        Returns:
            Best matching microcontroller
        """
        mcus = self.search_by_category(ComponentCategory.MICROCONTROLLER)

        suitable = []
        for mcu in mcus:
            specs = mcu.specs

            # Check WiFi
            if requirements.get('wifi') and 'wifi' not in specs:
                continue

            # Check Bluetooth
            if requirements.get('bluetooth') and 'bluetooth' not in specs:
                continue

            # Check flash memory
            if 'min_flash' in requirements:
                flash_kb = self._parse_memory(specs.get('flash', '0'))
                if flash_kb < requirements['min_flash']:
                    continue

            # Check RAM
            if 'min_ram' in requirements:
                ram_kb = self._parse_memory(specs.get('ram', '0'))
                if ram_kb < requirements['min_ram']:
                    continue

            # Check GPIO
            if 'min_gpio' in requirements:
                if specs.get('gpio', 0) < requirements['min_gpio']:
                    continue

            suitable.append(mcu)

        # Sort by price (prefer cheaper if multiple match)
        suitable.sort(key=lambda m: m.typical_price)

        return suitable[0] if suitable else None

    def _parse_memory(self, mem_str: str) -> int:
        """Parse memory string to KB."""
        if isinstance(mem_str, (int, float)):
            return int(mem_str)

        mem_str = str(mem_str).upper()

        if 'MB' in mem_str:
            return int(mem_str.replace('MB', '')) * 1024
        elif 'KB' in mem_str:
            return int(mem_str.replace('KB', ''))
        else:
            # Assume KB
            return int(''.join(filter(str.isdigit, mem_str)))

    def estimate_bom_cost(self, components: List[str], quantities: Dict[str, int] = None) -> float:
        """
        Estimate total BOM cost.

        Args:
            components: List of part numbers
            quantities: Dict mapping part number to quantity (default: 1 each)

        Returns:
            Total cost in USD
        """
        if quantities is None:
            quantities = {part: 1 for part in components}

        total = 0.0
        for part_number in components:
            comp = self.get_component(part_number)
            if comp:
                qty = quantities.get(part_number, 1)
                total += comp.typical_price * qty

        return total


# Singleton instance
component_db = ComponentDatabase()
