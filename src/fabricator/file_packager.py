"""
File Packaging Utilities

Create manufacturing packages with all necessary files.
Generates actual ZIP files ready for distribution.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import zipfile
import json
import csv
from datetime import datetime
import shutil


class ManufacturingPackager:
    """Package manufacturing files into distributable format."""

    def __init__(self):
        """Initialize packager."""
        pass

    def create_fabrication_package(
        self,
        device_id: str,
        circuit_files: Dict[str, str],
        enclosure_files: Dict[str, str],
        bom: List[Dict[str, Any]],
        costs: Dict[str, float],
        metadata: Dict[str, Any],
        output_path: str
    ) -> str:
        """
        Create complete fabrication package ZIP file.

        Args:
            device_id: Unique device ID
            circuit_files: Dict of circuit file paths
            enclosure_files: Dict of enclosure file paths
            bom: Bill of materials
            costs: Cost breakdown
            metadata: Additional metadata
            output_path: Output ZIP file path

        Returns:
            Path to created ZIP file
        """
        # Create temporary directory structure
        temp_dir = f"/tmp/fab_{device_id}"
        Path(temp_dir).mkdir(parents=True, exist_ok=True)

        # Create directory structure
        dirs = {
            'circuit': f"{temp_dir}/circuit",
            'enclosure': f"{temp_dir}/enclosure",
            'bom': f"{temp_dir}/bom",
            'documentation': f"{temp_dir}/documentation"
        }

        for dir_path in dirs.values():
            Path(dir_path).mkdir(parents=True, exist_ok=True)

        # Copy circuit files
        if circuit_files:
            for filename, filepath in circuit_files.items():
                if filepath and Path(filepath).exists():
                    shutil.copy(filepath, f"{dirs['circuit']}/{filename}")

        # Copy enclosure files
        if enclosure_files:
            for filename, filepath in enclosure_files.items():
                if filepath and Path(filepath).exists():
                    shutil.copy(filepath, f"{dirs['enclosure']}/{filename}")

        # Generate BOM files
        self._generate_bom_files(bom, dirs['bom'])

        # Generate cost estimate
        self._generate_cost_estimate(costs, temp_dir)

        # Generate manifest
        self._generate_manifest(device_id, metadata, temp_dir)

        # Generate README
        self._generate_readme(device_id, metadata, temp_dir)

        # Create ZIP file
        zip_path = self._create_zip(temp_dir, output_path)

        # Cleanup temp directory
        shutil.rmtree(temp_dir)

        return zip_path

    def _generate_bom_files(self, bom: List[Dict[str, Any]], output_dir: str):
        """Generate BOM in multiple formats."""
        # CSV format
        csv_path = f"{output_dir}/bill_of_materials.csv"
        with open(csv_path, 'w', newline='') as f:
            if bom:
                writer = csv.DictWriter(f, fieldnames=bom[0].keys())
                writer.writeheader()
                writer.writerows(bom)

        # JSON format
        json_path = f"{output_dir}/bill_of_materials.json"
        with open(json_path, 'w') as f:
            json.dump(bom, f, indent=2)

        # Human-readable text format
        txt_path = f"{output_dir}/bill_of_materials.txt"
        with open(txt_path, 'w') as f:
            f.write("BILL OF MATERIALS\n")
            f.write("=" * 80 + "\n\n")

            for idx, item in enumerate(bom, 1):
                f.write(f"{idx}. {item.get('description', 'Unknown')}\n")
                f.write(f"   Part Number: {item.get('part_number', 'N/A')}\n")
                f.write(f"   Manufacturer: {item.get('manufacturer', 'N/A')}\n")
                f.write(f"   Quantity: {item.get('quantity', 1)}\n")
                f.write(f"   Unit Price: ${item.get('unit_price', 0):.2f}\n")
                f.write(f"   Total Price: ${item.get('total_price', 0):.2f}\n")
                f.write("\n")

            total = sum(item.get('total_price', 0) for item in bom)
            f.write(f"\nTOTAL: ${total:.2f}\n")

    def _generate_cost_estimate(self, costs: Dict[str, float], output_dir: str):
        """Generate cost estimate document."""
        cost_path = f"{output_dir}/cost_estimate.txt"

        with open(cost_path, 'w') as f:
            f.write("COST ESTIMATE\n")
            f.write("=" * 80 + "\n\n")

            categories = [
                ('Electronics Components', costs.get('electronics', 0)),
                ('3D Printing Materials', costs.get('printing', 0)),
                ('Hardware (screws, etc.)', costs.get('hardware', 0)),
                ('PCB Manufacturing', costs.get('pcb_manufacturing', 0)),
                ('Assembly Labor (est.)', costs.get('assembly_labor', 0))
            ]

            for category, cost in categories:
                f.write(f"{category:.<50} ${cost:>8.2f}\n")

            f.write("\n")
            f.write(f"{'TOTAL COST':.<50} ${costs.get('total', 0):>8.2f}\n")
            f.write("\n")

            f.write("Notes:\n")
            f.write("- Electronics pricing based on single-unit quantities\n")
            f.write("- 3D printing cost assumes PLA filament at $20/kg\n")
            f.write("- PCB manufacturing cost for prototype quantities (1-10 units)\n")
            f.write("- Costs will decrease significantly for larger quantities\n")

        # Also save JSON version
        cost_json = f"{output_dir}/cost_estimate.json"
        with open(cost_json, 'w') as f:
            json.dump(costs, f, indent=2)

    def _generate_manifest(self, device_id: str, metadata: Dict[str, Any], output_dir: str):
        """Generate package manifest."""
        manifest = {
            'device_id': device_id,
            'generated_at': datetime.utcnow().isoformat(),
            'generator': 'Circuit.AI Fabricator',
            'version': '1.0',
            'metadata': metadata,
            'contents': {
                'circuit/': 'Circuit design files (schematics, PCB layout, Gerbers)',
                'enclosure/': '3D printable enclosure files (STL format)',
                'bom/': 'Bill of Materials in multiple formats',
                'documentation/': 'Assembly and testing instructions',
                'cost_estimate.txt': 'Detailed cost breakdown',
                'README.txt': 'Package overview and instructions'
            }
        }

        manifest_path = f"{output_dir}/MANIFEST.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

    def _generate_readme(self, device_id: str, metadata: Dict[str, Any], output_dir: str):
        """Generate README file."""
        readme_path = f"{output_dir}/README.txt"

        with open(readme_path, 'w') as f:
            f.write("="*80 + "\n")
            f.write("CIRCUIT.AI FABRICATION PACKAGE\n")
            f.write("="*80 + "\n\n")

            f.write(f"Device ID: {device_id}\n")
            f.write(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            f.write(f"Device Type: {metadata.get('device_type', 'N/A')}\n")
            f.write(f"Description: {metadata.get('description', 'N/A')}\n\n")

            f.write("="*80 + "\n")
            f.write("PACKAGE CONTENTS\n")
            f.write("="*80 + "\n\n")

            f.write("circuit/\n")
            f.write("  - schematic.kicad_sch    Circuit schematic (KiCAD format)\n")
            f.write("  - pcb.kicad_pcb          PCB layout (KiCAD format)\n")
            f.write("  - gerbers/               Gerber files for PCB manufacturing\n\n")

            f.write("enclosure/\n")
            f.write("  - base.stl               Enclosure base (3D printable)\n")
            f.write("  - lid.stl                Enclosure lid (3D printable)\n")
            f.write("  - previews/              Preview images\n\n")

            f.write("bom/\n")
            f.write("  - bill_of_materials.csv  Component list (CSV format)\n")
            f.write("  - bill_of_materials.json Component list (JSON format)\n")
            f.write("  - bill_of_materials.txt  Component list (human-readable)\n\n")

            f.write("documentation/\n")
            f.write("  - assembly_instructions.pdf  Step-by-step assembly guide\n")
            f.write("  - testing_procedures.pdf     Device testing checklist\n")
            f.write("  - user_manual.pdf            End-user documentation\n\n")

            f.write("cost_estimate.txt         Detailed cost breakdown\n")
            f.write("cost_estimate.json        Cost data (machine-readable)\n")
            f.write("MANIFEST.json             Package manifest\n\n")

            f.write("="*80 + "\n")
            f.write("MANUFACTURING STEPS\n")
            f.write("="*80 + "\n\n")

            f.write("1. PCB Manufacturing\n")
            f.write("   - Upload Gerber files to PCB manufacturer (JLCPCB, PCBWay, etc.)\n")
            f.write("   - Typical lead time: 3-7 days\n")
            f.write("   - Cost: $5-20 for prototypes\n\n")

            f.write("2. Component Procurement\n")
            f.write("   - Order components from BOM (Digi-Key, Mouser, etc.)\n")
            f.write("   - Typical lead time: 1-3 days\n")
            f.write("   - See bom/bill_of_materials.csv for part numbers\n\n")

            f.write("3. 3D Printing\n")
            f.write("   - Print base.stl and lid.stl\n")
            f.write("   - Recommended: PLA, 0.2mm layer height, 20% infill\n")
            f.write(f"   - Estimated print time: {metadata.get('print_time_hours', 'N/A')} hours\n")
            f.write(f"   - Estimated material: {metadata.get('material_grams', 'N/A')} grams\n\n")

            f.write("4. Assembly\n")
            f.write("   - Follow assembly_instructions.pdf\n")
            f.write("   - Solder components to PCB\n")
            f.write("   - Install PCB in enclosure\n")
            f.write("   - Test using testing_procedures.pdf\n\n")

            f.write("="*80 + "\n")
            f.write("SUPPORT\n")
            f.write("="*80 + "\n\n")

            f.write("Questions or issues? Contact: support@circuit.ai\n")
            f.write("Documentation: https://docs.circuit.ai/fabricator\n\n")

            f.write("="*80 + "\n")

    def _create_zip(self, source_dir: str, output_path: str) -> str:
        """Create ZIP file from directory."""
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            source_path = Path(source_dir)

            for file_path in source_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_path)
                    zipf.write(file_path, arcname)

        return output_path

    def create_gerber_package(
        self,
        pcb_file: str,
        output_dir: str
    ) -> List[str]:
        """
        Create Gerber files from PCB layout.

        Note: This is a stub - actual implementation would use KiCAD Python API.

        Args:
            pcb_file: KiCAD PCB file path
            output_dir: Output directory for Gerbers

        Returns:
            List of generated Gerber file paths
        """
        # This would use KiCAD Python API:
        # import pcbnew
        # board = pcbnew.LoadBoard(pcb_file)
        # plot_controller = pcbnew.PLOT_CONTROLLER(board)
        # ...

        # For now, return expected file list
        gerber_files = [
            f"{output_dir}/F_Cu.gbr",  # Front copper
            f"{output_dir}/B_Cu.gbr",  # Back copper
            f"{output_dir}/F_Mask.gbr",  # Front soldermask
            f"{output_dir}/B_Mask.gbr",  # Back soldermask
            f"{output_dir}/F_SilkS.gbr",  # Front silkscreen
            f"{output_dir}/B_SilkS.gbr",  # Back silkscreen
            f"{output_dir}/Edge_Cuts.gbr",  # Board outline
            f"{output_dir}/drill.drl"  # Drill file
        ]

        return gerber_files


# Singleton instance
manufacturing_packager = ManufacturingPackager()
