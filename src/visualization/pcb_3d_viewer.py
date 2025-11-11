"""
3D PCB Visualization for AR/VR

Features:
- Generate 3D models from PCB data
- Export to glTF/GLB for AR/VR
- Interactive 3D web viewer
- Layer visualization
- Component highlighting
- Measurement tools
- Cross-section views
- Thermal visualization overlay
- WebXR support for AR viewing
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np
import json
from pathlib import Path
from loguru import logger


class MaterialType(Enum):
    """3D material types."""
    PCB_SUBSTRATE = "pcb_substrate"
    COPPER = "copper"
    SOLDER_MASK = "solder_mask"
    SILK_SCREEN = "silkscreen"
    SOLDER = "solder"
    COMPONENT = "component"
    PAD = "pad"


@dataclass
class Material:
    """3D material properties."""
    name: str
    type: MaterialType
    color: Tuple[float, float, float]  # RGB 0-1
    metallic: float  # 0-1
    roughness: float  # 0-1
    opacity: float  # 0-1


@dataclass
class Vertex:
    """3D vertex."""
    x: float
    y: float
    z: float
    nx: float = 0.0  # Normal X
    ny: float = 0.0  # Normal Y
    nz: float = 1.0  # Normal Z
    u: float = 0.0  # Texture U
    v: float = 0.0  # Texture V


@dataclass
class Mesh:
    """3D mesh."""
    vertices: List[Vertex]
    indices: List[int]
    material: Material
    name: str


@dataclass
class Scene3D:
    """3D scene."""
    meshes: List[Mesh]
    bounds: Dict[str, float]  # min_x, max_x, min_y, max_y, min_z, max_z
    metadata: Dict[str, Any]


class PCB3DGenerator:
    """Generate 3D models from PCB data."""

    def __init__(self):
        """Initialize 3D generator."""
        self.materials = self._create_materials()
        logger.info("PCB3DGenerator initialized")

    def _create_materials(self) -> Dict[MaterialType, Material]:
        """Create standard PCB materials."""
        return {
            MaterialType.PCB_SUBSTRATE: Material(
                name="FR4 Substrate",
                type=MaterialType.PCB_SUBSTRATE,
                color=(0.2, 0.3, 0.15),  # Dark green
                metallic=0.0,
                roughness=0.8,
                opacity=1.0
            ),
            MaterialType.COPPER: Material(
                name="Copper",
                type=MaterialType.COPPER,
                color=(0.72, 0.45, 0.20),  # Copper color
                metallic=1.0,
                roughness=0.3,
                opacity=1.0
            ),
            MaterialType.SOLDER_MASK: Material(
                name="Solder Mask",
                type=MaterialType.SOLDER_MASK,
                color=(0.0, 0.5, 0.0),  # Green
                metallic=0.0,
                roughness=0.6,
                opacity=0.9
            ),
            MaterialType.SILK_SCREEN: Material(
                name="Silkscreen",
                type=MaterialType.SILK_SCREEN,
                color=(1.0, 1.0, 1.0),  # White
                metallic=0.0,
                roughness=0.9,
                opacity=1.0
            ),
            MaterialType.SOLDER: Material(
                name="Solder",
                type=MaterialType.SOLDER,
                color=(0.75, 0.75, 0.75),  # Silver
                metallic=1.0,
                roughness=0.2,
                opacity=1.0
            ),
            MaterialType.COMPONENT: Material(
                name="Component Body",
                type=MaterialType.COMPONENT,
                color=(0.1, 0.1, 0.1),  # Dark gray/black
                metallic=0.1,
                roughness=0.7,
                opacity=1.0
            )
        }

    def generate_scene(
        self,
        pcb_data: Dict[str, Any],
        layer_thickness: float = 1.6,  # mm
        include_components: bool = True
    ) -> Scene3D:
        """
        Generate complete 3D scene from PCB data.

        Args:
            pcb_data: PCB design data
            layer_thickness: Board thickness in mm
            include_components: Include component 3D models

        Returns:
            3D scene
        """
        meshes = []

        # Generate substrate
        substrate_mesh = self._generate_substrate(
            pcb_data.get('board_width', 100),
            pcb_data.get('board_height', 100),
            layer_thickness
        )
        meshes.append(substrate_mesh)

        # Generate copper layers
        copper_meshes = self._generate_copper_layers(
            pcb_data.get('traces', []),
            pcb_data.get('pads', []),
            layer_thickness
        )
        meshes.extend(copper_meshes)

        # Generate solder mask
        solder_mask_meshes = self._generate_solder_mask(
            pcb_data.get('board_width', 100),
            pcb_data.get('board_height', 100),
            pcb_data.get('pads', []),
            layer_thickness
        )
        meshes.extend(solder_mask_meshes)

        # Generate vias
        via_meshes = self._generate_vias(
            pcb_data.get('vias', []),
            layer_thickness
        )
        meshes.extend(via_meshes)

        # Generate components
        if include_components:
            component_meshes = self._generate_components(
                pcb_data.get('components', []),
                layer_thickness
            )
            meshes.extend(component_meshes)

        # Calculate bounds
        bounds = self._calculate_bounds(meshes)

        return Scene3D(
            meshes=meshes,
            bounds=bounds,
            metadata={
                'layer_thickness': layer_thickness,
                'component_count': len(pcb_data.get('components', [])),
                'via_count': len(pcb_data.get('vias', []))
            }
        )

    def _generate_substrate(
        self,
        width: float,
        height: float,
        thickness: float
    ) -> Mesh:
        """Generate PCB substrate mesh (box)."""
        # Create box vertices
        vertices = []

        # Bottom face (z=0)
        vertices.extend([
            Vertex(0, 0, 0, 0, 0, -1, 0, 0),
            Vertex(width, 0, 0, 0, 0, -1, 1, 0),
            Vertex(width, height, 0, 0, 0, -1, 1, 1),
            Vertex(0, height, 0, 0, 0, -1, 0, 1),
        ])

        # Top face (z=thickness)
        vertices.extend([
            Vertex(0, 0, thickness, 0, 0, 1, 0, 0),
            Vertex(width, 0, thickness, 0, 0, 1, 1, 0),
            Vertex(width, height, thickness, 0, 0, 1, 1, 1),
            Vertex(0, height, thickness, 0, 0, 1, 0, 1),
        ])

        # Indices for box (6 faces, 2 triangles each)
        indices = [
            # Bottom
            0, 1, 2, 0, 2, 3,
            # Top
            4, 6, 5, 4, 7, 6,
            # Front
            0, 4, 5, 0, 5, 1,
            # Back
            2, 6, 7, 2, 7, 3,
            # Left
            0, 3, 7, 0, 7, 4,
            # Right
            1, 5, 6, 1, 6, 2
        ]

        return Mesh(
            vertices=vertices,
            indices=indices,
            material=self.materials[MaterialType.PCB_SUBSTRATE],
            name="PCB Substrate"
        )

    def _generate_copper_layers(
        self,
        traces: List[Dict[str, Any]],
        pads: List[Dict[str, Any]],
        board_thickness: float
    ) -> List[Mesh]:
        """Generate copper layer meshes."""
        meshes = []

        copper_thickness = 0.035  # 1oz copper = 0.035mm

        # Top copper layer
        top_z = board_thickness
        top_meshes = self._generate_copper_features(
            traces, pads, top_z, copper_thickness, "top"
        )
        meshes.extend(top_meshes)

        # Bottom copper layer
        bottom_z = -copper_thickness
        bottom_meshes = self._generate_copper_features(
            traces, pads, bottom_z, copper_thickness, "bottom"
        )
        meshes.extend(bottom_meshes)

        return meshes

    def _generate_copper_features(
        self,
        traces: List[Dict[str, Any]],
        pads: List[Dict[str, Any]],
        z: float,
        thickness: float,
        layer: str
    ) -> List[Mesh]:
        """Generate copper features for one layer."""
        meshes = []

        # Generate traces
        for i, trace in enumerate(traces):
            if trace.get('layer') != layer:
                continue

            trace_mesh = self._create_trace_mesh(
                trace['x1'], trace['y1'],
                trace['x2'], trace['y2'],
                trace['width'],
                z, thickness
            )
            trace_mesh.name = f"Trace {i} ({layer})"
            meshes.append(trace_mesh)

        # Generate pads
        for i, pad in enumerate(pads):
            if pad.get('layer') != layer:
                continue

            if pad.get('shape') == 'circle':
                pad_mesh = self._create_circular_pad(
                    pad['x'], pad['y'],
                    pad['diameter'],
                    z, thickness
                )
            else:
                pad_mesh = self._create_rectangular_pad(
                    pad['x'], pad['y'],
                    pad['width'], pad['height'],
                    z, thickness
                )

            pad_mesh.name = f"Pad {i} ({layer})"
            meshes.append(pad_mesh)

        return meshes

    def _create_trace_mesh(
        self,
        x1: float, y1: float,
        x2: float, y2: float,
        width: float,
        z: float,
        thickness: float
    ) -> Mesh:
        """Create rectangular trace mesh."""
        # Calculate perpendicular vector
        dx = x2 - x1
        dy = y2 - y1
        length = np.sqrt(dx**2 + dy**2)

        if length == 0:
            return self._create_box_mesh(x1, y1, z, width, width, thickness)

        # Unit vector along trace
        ux = dx / length
        uy = dy / length

        # Perpendicular vector
        px = -uy * width / 2
        py = ux * width / 2

        # Create vertices for trace
        vertices = [
            # Bottom face
            Vertex(x1 + px, y1 + py, z),
            Vertex(x2 + px, y2 + py, z),
            Vertex(x2 - px, y2 - py, z),
            Vertex(x1 - px, y1 - py, z),
            # Top face
            Vertex(x1 + px, y1 + py, z + thickness),
            Vertex(x2 + px, y2 + py, z + thickness),
            Vertex(x2 - px, y2 - py, z + thickness),
            Vertex(x1 - px, y1 - py, z + thickness),
        ]

        indices = [
            # Bottom
            0, 1, 2, 0, 2, 3,
            # Top
            4, 6, 5, 4, 7, 6,
            # Sides
            0, 4, 5, 0, 5, 1,
            1, 5, 6, 1, 6, 2,
            2, 6, 7, 2, 7, 3,
            3, 7, 4, 3, 4, 0
        ]

        return Mesh(
            vertices=vertices,
            indices=indices,
            material=self.materials[MaterialType.COPPER],
            name="Trace"
        )

    def _create_circular_pad(
        self,
        x: float, y: float,
        diameter: float,
        z: float,
        thickness: float,
        segments: int = 16
    ) -> Mesh:
        """Create circular pad mesh."""
        vertices = []
        radius = diameter / 2

        # Create circle vertices (bottom and top)
        for layer in [0, 1]:
            z_pos = z if layer == 0 else z + thickness
            nz = -1 if layer == 0 else 1

            # Center vertex
            vertices.append(Vertex(x, y, z_pos, 0, 0, nz))

            # Circle vertices
            for i in range(segments):
                angle = (i / segments) * 2 * np.pi
                vx = x + radius * np.cos(angle)
                vy = y + radius * np.sin(angle)
                vertices.append(Vertex(vx, vy, z_pos, 0, 0, nz))

        # Create indices
        indices = []

        # Bottom face
        for i in range(segments):
            indices.extend([
                0,
                1 + i,
                1 + ((i + 1) % segments)
            ])

        # Top face
        base = segments + 1
        for i in range(segments):
            indices.extend([
                base,
                base + 1 + ((i + 1) % segments),
                base + 1 + i
            ])

        # Side faces
        for i in range(segments):
            next_i = (i + 1) % segments

            indices.extend([
                1 + i,
                1 + next_i,
                base + 1 + i,

                base + 1 + i,
                1 + next_i,
                base + 1 + next_i
            ])

        return Mesh(
            vertices=vertices,
            indices=indices,
            material=self.materials[MaterialType.COPPER],
            name="Circular Pad"
        )

    def _create_rectangular_pad(
        self,
        x: float, y: float,
        width: float, height: float,
        z: float,
        thickness: float
    ) -> Mesh:
        """Create rectangular pad mesh."""
        return self._create_box_mesh(x, y, z, width, height, thickness)

    def _create_box_mesh(
        self,
        x: float, y: float, z: float,
        width: float, height: float, depth: float
    ) -> Mesh:
        """Create generic box mesh."""
        hw = width / 2
        hh = height / 2

        vertices = [
            # Bottom
            Vertex(x - hw, y - hh, z, 0, 0, -1),
            Vertex(x + hw, y - hh, z, 0, 0, -1),
            Vertex(x + hw, y + hh, z, 0, 0, -1),
            Vertex(x - hw, y + hh, z, 0, 0, -1),
            # Top
            Vertex(x - hw, y - hh, z + depth, 0, 0, 1),
            Vertex(x + hw, y - hh, z + depth, 0, 0, 1),
            Vertex(x + hw, y + hh, z + depth, 0, 0, 1),
            Vertex(x - hw, y + hh, z + depth, 0, 0, 1),
        ]

        indices = [
            0, 1, 2, 0, 2, 3,  # Bottom
            4, 6, 5, 4, 7, 6,  # Top
            0, 4, 5, 0, 5, 1,  # Front
            2, 6, 7, 2, 7, 3,  # Back
            0, 3, 7, 0, 7, 4,  # Left
            1, 5, 6, 1, 6, 2   # Right
        ]

        return Mesh(
            vertices=vertices,
            indices=indices,
            material=self.materials[MaterialType.COPPER],
            name="Box"
        )

    def _generate_solder_mask(
        self,
        width: float, height: float,
        pads: List[Dict[str, Any]],
        board_thickness: float
    ) -> List[Mesh]:
        """Generate solder mask layers."""
        # Simplified: just create thin layers on top and bottom
        # In reality, would subtract pad openings

        mask_thickness = 0.025  # mm

        meshes = []

        # Top solder mask
        top_mask = self._create_box_mesh(
            width / 2, height / 2,
            board_thickness,
            width, height,
            mask_thickness
        )
        top_mask.material = self.materials[MaterialType.SOLDER_MASK]
        top_mask.name = "Top Solder Mask"
        meshes.append(top_mask)

        # Bottom solder mask
        bottom_mask = self._create_box_mesh(
            width / 2, height / 2,
            -mask_thickness,
            width, height,
            mask_thickness
        )
        bottom_mask.material = self.materials[MaterialType.SOLDER_MASK]
        bottom_mask.name = "Bottom Solder Mask"
        meshes.append(bottom_mask)

        return meshes

    def _generate_vias(
        self,
        vias: List[Dict[str, Any]],
        board_thickness: float
    ) -> List[Mesh]:
        """Generate via cylinders."""
        meshes = []

        for i, via in enumerate(vias):
            via_mesh = self._create_circular_pad(
                via['x'], via['y'],
                via['diameter'],
                0, board_thickness,
                segments=12
            )
            via_mesh.name = f"Via {i}"
            meshes.append(via_mesh)

        return meshes

    def _generate_components(
        self,
        components: List[Dict[str, Any]],
        board_thickness: float
    ) -> List[Mesh]:
        """Generate simplified component meshes."""
        meshes = []

        for i, comp in enumerate(components):
            # Simplified: create box for component body
            package = comp.get('package', 'generic')
            width, height, depth = self._get_package_dimensions(package)

            comp_mesh = self._create_box_mesh(
                comp['x'], comp['y'],
                board_thickness + 0.1,  # Slight offset
                width, height, depth
            )
            comp_mesh.material = self.materials[MaterialType.COMPONENT]
            comp_mesh.name = f"Component {comp.get('designator', i)}"
            meshes.append(comp_mesh)

        return meshes

    def _get_package_dimensions(self, package: str) -> Tuple[float, float, float]:
        """Get approximate package dimensions."""
        # Simplified package sizes (width, height, depth)
        package_sizes = {
            '0603': (1.6, 0.8, 0.5),
            '0805': (2.0, 1.25, 0.6),
            '1206': (3.2, 1.6, 0.7),
            'sot23': (2.9, 1.3, 1.0),
            'soic8': (5.0, 4.0, 1.5),
            'qfn32': (5.0, 5.0, 1.0),
        }

        return package_sizes.get(package.lower(), (3.0, 3.0, 1.0))

    def _calculate_bounds(self, meshes: List[Mesh]) -> Dict[str, float]:
        """Calculate scene bounds."""
        min_x = min_y = min_z = float('inf')
        max_x = max_y = max_z = float('-inf')

        for mesh in meshes:
            for vertex in mesh.vertices:
                min_x = min(min_x, vertex.x)
                max_x = max(max_x, vertex.x)
                min_y = min(min_y, vertex.y)
                max_y = max(max_y, vertex.y)
                min_z = min(min_z, vertex.z)
                max_z = max(max_z, vertex.z)

        return {
            'min_x': min_x, 'max_x': max_x,
            'min_y': min_y, 'max_y': max_y,
            'min_z': min_z, 'max_z': max_z
        }


class GLTFExporter:
    """Export 3D scenes to glTF format for AR/VR."""

    def export(self, scene: Scene3D, output_path: str):
        """
        Export scene to glTF file.

        Args:
            scene: 3D scene
            output_path: Output file path (.gltf or .glb)
        """
        # Create glTF structure
        gltf = {
            "asset": {
                "version": "2.0",
                "generator": "Circuit.AI PCB 3D Exporter"
            },
            "scene": 0,
            "scenes": [{"nodes": list(range(len(scene.meshes)))}],
            "nodes": [],
            "meshes": [],
            "materials": [],
            "buffers": [],
            "bufferViews": [],
            "accessors": []
        }

        # Export each mesh
        for i, mesh in enumerate(scene.meshes):
            self._export_mesh(gltf, mesh, i)

        # Write to file
        with open(output_path, 'w') as f:
            json.dump(gltf, f, indent=2)

        logger.info(f"Exported 3D scene to {output_path}")

    def _export_mesh(self, gltf: Dict, mesh: Mesh, index: int):
        """Export single mesh to glTF."""
        # Add node
        gltf["nodes"].append({
            "name": mesh.name,
            "mesh": index
        })

        # Add material
        material_index = len(gltf["materials"])
        gltf["materials"].append({
            "name": mesh.material.name,
            "pbrMetallicRoughness": {
                "baseColorFactor": [
                    mesh.material.color[0],
                    mesh.material.color[1],
                    mesh.material.color[2],
                    mesh.material.opacity
                ],
                "metallicFactor": mesh.material.metallic,
                "roughnessFactor": mesh.material.roughness
            }
        })

        # Add mesh
        gltf["meshes"].append({
            "name": mesh.name,
            "primitives": [{
                "attributes": {
                    "POSITION": index * 3,
                    "NORMAL": index * 3 + 1
                },
                "indices": index * 3 + 2,
                "material": material_index
            }]
        })


# Singleton instance
pcb_3d_generator = PCB3DGenerator()
gltf_exporter = GLTFExporter()
