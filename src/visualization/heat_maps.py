"""
Advanced Heat Map Visualization

Generates heat maps for:
- Component density
- Thermal analysis
- Power distribution
- Signal frequency
- Trace congestion
- Manufacturing complexity
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import cv2
from scipy import ndimage
from scipy.interpolate import griddata
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
from matplotlib.colors import LinearSegmentedColormap
import io
from loguru import logger


class HeatMapGenerator:
    """Advanced heat map visualization generator."""

    def __init__(self):
        """Initialize heat map generator."""
        self.resolution = (1024, 1024)
        logger.info("HeatMapGenerator initialized")

    async def generate_component_density_map(
        self,
        pcb_image: np.ndarray,
        components: List[Dict[str, Any]],
        colormap: str = "hot"
    ) -> np.ndarray:
        """
        Generate component density heat map.

        Args:
            pcb_image: PCB image
            components: List of detected components
            colormap: Matplotlib colormap name

        Returns:
            Heat map image
        """
        height, width = pcb_image.shape[:2]

        # Create density map
        density_map = np.zeros((height, width), dtype=np.float32)

        for comp in components:
            bbox = comp.get('bounding_box', {})
            x = int(bbox.get('x', 0))
            y = int(bbox.get('y', 0))
            w = int(bbox.get('width', 50))
            h = int(bbox.get('height', 50))

            # Add Gaussian blur around component location
            sigma = max(w, h) * 2
            y_grid, x_grid = np.ogrid[-y:height-y, -x:width-x]
            mask = np.exp(-(x_grid**2 + y_grid**2) / (2 * sigma**2))

            density_map += mask

        # Normalize
        if density_map.max() > 0:
            density_map = density_map / density_map.max()

        # Apply colormap
        heat_map = self._apply_colormap(density_map, colormap)

        # Blend with original image
        alpha = 0.6
        result = cv2.addWeighted(pcb_image, 1-alpha, heat_map, alpha, 0)

        return result

    async def generate_thermal_map(
        self,
        pcb_image: np.ndarray,
        components: List[Dict[str, Any]],
        ambient_temp: float = 25.0
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Generate thermal heat map based on component power ratings.

        Args:
            pcb_image: PCB image
            components: List of components with power ratings
            ambient_temp: Ambient temperature in Celsius

        Returns:
            (Heat map image, thermal analysis data)
        """
        height, width = pcb_image.shape[:2]

        # Create temperature map
        temp_map = np.full((height, width), ambient_temp, dtype=np.float32)

        hotspots = []

        for comp in components:
            power_rating = comp.get('power_rating', 0)

            if power_rating == 0:
                continue

            bbox = comp.get('bounding_box', {})
            x = int(bbox.get('x', 0))
            y = int(bbox.get('y', 0))
            w = int(bbox.get('width', 50))
            h = int(bbox.get('height', 50))

            # Calculate temperature rise (simplified model)
            # ΔT ≈ Power × Thermal Resistance
            # Assume average thermal resistance of 50°C/W for air cooling
            thermal_resistance = 50.0
            temp_rise = power_rating * thermal_resistance

            max_temp = ambient_temp + temp_rise

            # Create temperature distribution around component
            sigma = max(w, h) * 1.5
            y_grid, x_grid = np.ogrid[-y:height-y, -x:width-x]
            dist = np.sqrt(x_grid**2 + y_grid**2)

            # Temperature falls off with distance
            temp_distribution = ambient_temp + temp_rise * np.exp(-dist**2 / (2 * sigma**2))

            # Update temperature map (max of existing or new)
            temp_map = np.maximum(temp_map, temp_distribution)

            # Record hotspot
            if max_temp > 60:  # Threshold for concern
                hotspots.append({
                    'component_id': comp.get('id', ''),
                    'component_type': comp.get('type', 'unknown'),
                    'power_rating': power_rating,
                    'estimated_temp': max_temp,
                    'location': (x, y),
                    'severity': 'high' if max_temp > 80 else 'medium'
                })

        # Normalize temperature to 0-1 range for visualization
        temp_min = ambient_temp
        temp_max = temp_map.max()

        if temp_max > temp_min:
            temp_normalized = (temp_map - temp_min) / (temp_max - temp_min)
        else:
            temp_normalized = np.zeros_like(temp_map)

        # Apply thermal colormap (blue -> green -> yellow -> red)
        colors = ['#0000FF', '#00FF00', '#FFFF00', '#FF0000']
        n_bins = 100
        thermal_cmap = LinearSegmentedColormap.from_list('thermal', colors, N=n_bins)

        heat_map = self._apply_colormap(temp_normalized, thermal_cmap)

        # Blend with original
        alpha = 0.5
        result = cv2.addWeighted(pcb_image, 1-alpha, heat_map, alpha, 0)

        # Add temperature scale overlay
        result = self._add_temperature_scale(result, temp_min, temp_max)

        # Thermal analysis summary
        analysis = {
            'max_temperature': float(temp_max),
            'min_temperature': float(temp_min),
            'avg_temperature': float(temp_map.mean()),
            'hotspot_count': len(hotspots),
            'hotspots': hotspots,
            'thermal_warning': temp_max > 80,
            'recommendation': self._get_thermal_recommendation(temp_max, len(hotspots))
        }

        return result, analysis

    async def generate_power_distribution_map(
        self,
        pcb_image: np.ndarray,
        components: List[Dict[str, Any]]
    ) -> np.ndarray:
        """
        Generate power distribution heat map.

        Shows current flow and voltage drop across the PCB.

        Args:
            pcb_image: PCB image
            components: List of components

        Returns:
            Power distribution heat map
        """
        height, width = pcb_image.shape[:2]

        # Create power density map
        power_map = np.zeros((height, width), dtype=np.float32)

        for comp in components:
            power = comp.get('power_rating', 0)
            current = comp.get('current_rating', 0)

            if power == 0 and current == 0:
                continue

            bbox = comp.get('bounding_box', {})
            x = int(bbox.get('x', 0))
            y = int(bbox.get('y', 0))
            w = int(bbox.get('width', 50))
            h = int(bbox.get('height', 50))

            # Power consumption indicator
            power_value = max(power, current * 5.0)  # Approximate voltage

            # Create power distribution
            sigma = max(w, h)
            y_grid, x_grid = np.ogrid[-y:height-y, -x:width-x]
            power_distribution = power_value * np.exp(-(x_grid**2 + y_grid**2) / (2 * sigma**2))

            power_map += power_distribution

        # Normalize
        if power_map.max() > 0:
            power_map = power_map / power_map.max()

        # Apply electric colormap
        colors = ['#000033', '#0066FF', '#00FFFF', '#FFFF00', '#FF0000']
        power_cmap = LinearSegmentedColormap.from_list('power', colors)

        heat_map = self._apply_colormap(power_map, power_cmap)

        # Blend
        alpha = 0.6
        result = cv2.addWeighted(pcb_image, 1-alpha, heat_map, alpha, 0)

        return result

    async def generate_trace_congestion_map(
        self,
        pcb_image: np.ndarray,
        trace_analysis: Optional[Dict[str, Any]] = None
    ) -> np.ndarray:
        """
        Generate trace congestion heat map.

        Shows areas with high trace density.

        Args:
            pcb_image: PCB image
            trace_analysis: Optional trace analysis data

        Returns:
            Trace congestion heat map
        """
        # Convert to grayscale
        if len(pcb_image.shape) == 3:
            gray = cv2.cvtColor(pcb_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = pcb_image.copy()

        # Detect edges (traces)
        edges = cv2.Canny(gray, 50, 150)

        # Create density map using convolution
        kernel_size = 51
        kernel = np.ones((kernel_size, kernel_size), np.float32) / (kernel_size ** 2)
        congestion_map = cv2.filter2D(edges.astype(np.float32), -1, kernel)

        # Normalize
        if congestion_map.max() > 0:
            congestion_map = congestion_map / congestion_map.max()

        # Apply colormap
        heat_map = self._apply_colormap(congestion_map, 'YlOrRd')

        # Blend
        alpha = 0.5
        result = cv2.addWeighted(pcb_image, 1-alpha, heat_map, alpha, 0)

        return result

    async def generate_manufacturing_complexity_map(
        self,
        pcb_image: np.ndarray,
        components: List[Dict[str, Any]]
    ) -> np.ndarray:
        """
        Generate manufacturing complexity heat map.

        Shows areas that are difficult to manufacture/assemble.

        Args:
            pcb_image: PCB image
            components: List of components

        Returns:
            Manufacturing complexity heat map
        """
        height, width = pcb_image.shape[:2]

        complexity_map = np.zeros((height, width), dtype=np.float32)

        for comp in components:
            bbox = comp.get('bounding_box', {})
            x = int(bbox.get('x', 0))
            y = int(bbox.get('y', 0))
            w = int(bbox.get('width', 50))
            h = int(bbox.get('height', 50))

            # Complexity factors
            complexity = 1.0

            # Small components are harder to place
            if w < 20 or h < 20:
                complexity += 2.0

            # High pin count increases complexity
            pin_count = len(comp.get('pins', []))
            if pin_count > 20:
                complexity += 1.5
            elif pin_count > 10:
                complexity += 1.0

            # BGA/QFN packages are more complex
            package = comp.get('package', '').lower()
            if 'bga' in package or 'qfn' in package:
                complexity += 2.0

            # Add to map
            sigma = max(w, h)
            y_grid, x_grid = np.ogrid[-y:height-y, -x:width-x]
            distribution = complexity * np.exp(-(x_grid**2 + y_grid**2) / (2 * sigma**2))

            complexity_map += distribution

        # Normalize
        if complexity_map.max() > 0:
            complexity_map = complexity_map / complexity_map.max()

        # Apply colormap
        heat_map = self._apply_colormap(complexity_map, 'RdYlGn_r')

        # Blend
        alpha = 0.6
        result = cv2.addWeighted(pcb_image, 1-alpha, heat_map, alpha, 0)

        return result

    def _apply_colormap(
        self,
        data: np.ndarray,
        colormap: Any
    ) -> np.ndarray:
        """
        Apply colormap to data.

        Args:
            data: Normalized data (0-1)
            colormap: Colormap name or object

        Returns:
            Colored image
        """
        if isinstance(colormap, str):
            cmap = plt.get_cmap(colormap)
        else:
            cmap = colormap

        # Apply colormap
        colored = cmap(data)

        # Convert to BGR for OpenCV (0-255)
        colored_bgr = (colored[:, :, [2, 1, 0]] * 255).astype(np.uint8)

        return colored_bgr

    def _add_temperature_scale(
        self,
        image: np.ndarray,
        temp_min: float,
        temp_max: float
    ) -> np.ndarray:
        """Add temperature scale legend to image."""
        height, width = image.shape[:2]

        # Create scale bar
        scale_height = height - 100
        scale_width = 30
        scale_x = width - 60
        scale_y = 50

        # Create temperature gradient
        gradient = np.linspace(1, 0, scale_height).reshape(-1, 1)
        gradient = np.repeat(gradient, scale_width, axis=1)

        # Apply thermal colormap
        colors = ['#0000FF', '#00FF00', '#FFFF00', '#FF0000']
        thermal_cmap = LinearSegmentedColormap.from_list('thermal', colors)

        scale_colored = self._apply_colormap(gradient, thermal_cmap)

        # Place on image
        image[scale_y:scale_y+scale_height, scale_x:scale_x+scale_width] = scale_colored

        # Add border
        cv2.rectangle(image, (scale_x, scale_y), (scale_x+scale_width, scale_y+scale_height),
                     (255, 255, 255), 2)

        # Add temperature labels
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        color = (255, 255, 255)
        thickness = 1

        # Max temp (top)
        cv2.putText(image, f"{temp_max:.0f}°C", (scale_x + scale_width + 5, scale_y + 15),
                   font, font_scale, color, thickness)

        # Mid temp
        mid_temp = (temp_max + temp_min) / 2
        mid_y = scale_y + scale_height // 2
        cv2.putText(image, f"{mid_temp:.0f}°C", (scale_x + scale_width + 5, mid_y),
                   font, font_scale, color, thickness)

        # Min temp (bottom)
        cv2.putText(image, f"{temp_min:.0f}°C", (scale_x + scale_width + 5, scale_y + scale_height),
                   font, font_scale, color, thickness)

        return image

    def _get_thermal_recommendation(
        self,
        max_temp: float,
        hotspot_count: int
    ) -> str:
        """Get thermal management recommendation."""
        if max_temp > 100:
            return "CRITICAL: Add active cooling (fan) or heatsinks immediately. Consider component derating."
        elif max_temp > 80:
            return "Add heatsinks to high-power components. Improve airflow. Consider thermal vias."
        elif max_temp > 60:
            return "Monitor temperature during operation. Consider adding thermal vias under hot components."
        else:
            return "Thermal profile is acceptable. No immediate action required."


# Singleton instance
heat_map_generator = HeatMapGenerator()
