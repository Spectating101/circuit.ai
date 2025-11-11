/**
 * 3D PCB Viewer Component
 *
 * Interactive 3D visualization of PCB with detected components using Three.js
 * Features:
 * - 3D board rendering
 * - Component highlighting
 * - Interactive camera controls
 * - Component labels
 * - Click to inspect components
 */

'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { CSS2DRenderer, CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer';
import { ZoomIn, ZoomOut, RotateCcw, Eye, EyeOff } from 'lucide-react';

interface Component {
  id: string;
  type: string;
  position: { x: number; y: number };
  dimensions: { width: number; height: number };
  value?: string;
  confidence: number;
}

interface PCB3DViewerProps {
  boardImage: string;
  components: Component[];
  onComponentClick?: (component: Component) => void;
  width?: number;
  height?: number;
}

export function PCB3DViewer({
  boardImage,
  components,
  onComponentClick,
  width = 800,
  height = 600
}: PCB3DViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const labelRendererRef = useRef<CSS2DRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const componentMeshesRef = useRef<Map<string, THREE.Mesh>>(new Map());
  const raycasterRef = useRef<THREE.Raycaster>(new THREE.Raycaster());
  const mouseRef = useRef<THREE.Vector2>(new THREE.Vector2());

  const [showLabels, setShowLabels] = useState(true);
  const [hoveredComponent, setHoveredComponent] = useState<Component | null>(null);

  // Initialize Three.js scene
  useEffect(() => {
    if (!containerRef.current) return;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf0f0f0);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(
      75,
      width / height,
      0.1,
      1000
    );
    camera.position.set(0, 5, 10);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    containerRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Label Renderer
    const labelRenderer = new CSS2DRenderer();
    labelRenderer.setSize(width, height);
    labelRenderer.domElement.style.position = 'absolute';
    labelRenderer.domElement.style.top = '0';
    labelRenderer.domElement.style.pointerEvents = 'none';
    containerRef.current.appendChild(labelRenderer.domElement);
    labelRendererRef.current = labelRenderer;

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 3;
    controls.maxDistance = 30;
    controlsRef.current = controls;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(5, 10, 5);
    directionalLight.castShadow = true;
    directionalLight.shadow.camera.near = 0.1;
    directionalLight.shadow.camera.far = 50;
    directionalLight.shadow.mapSize.width = 2048;
    directionalLight.shadow.mapSize.height = 2048;
    scene.add(directionalLight);

    // PCB Board
    const textureLoader = new THREE.TextureLoader();
    textureLoader.load(boardImage, (texture) => {
      const boardGeometry = new THREE.BoxGeometry(10, 0.2, 8);
      const boardMaterial = new THREE.MeshStandardMaterial({
        map: texture,
        color: 0x1a5f1a,
        roughness: 0.7,
        metalness: 0.3
      });

      const board = new THREE.Mesh(boardGeometry, boardMaterial);
      board.receiveShadow = true;
      board.castShadow = true;
      scene.add(board);
    });

    // Grid helper
    const gridHelper = new THREE.GridHelper(20, 20, 0x888888, 0xcccccc);
    gridHelper.position.y = -0.11;
    scene.add(gridHelper);

    // Animation loop
    function animate() {
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
      labelRenderer.render(scene, camera);
    }
    animate();

    // Cleanup
    return () => {
      renderer.dispose();
      if (containerRef.current) {
        containerRef.current.removeChild(renderer.domElement);
        containerRef.current.removeChild(labelRenderer.domElement);
      }
    };
  }, [boardImage, width, height]);

  // Add components to scene
  useEffect(() => {
    if (!sceneRef.current) return;

    // Clear existing component meshes
    componentMeshesRef.current.forEach((mesh) => {
      sceneRef.current?.remove(mesh);
      mesh.geometry.dispose();
      if (Array.isArray(mesh.material)) {
        mesh.material.forEach(m => m.dispose());
      } else {
        mesh.material.dispose();
      }
    });
    componentMeshesRef.current.clear();

    // Add new components
    components.forEach((component) => {
      const { x, y } = component.position;
      const { width: w, height: h } = component.dimensions;

      // Component geometry (box)
      const geometry = new THREE.BoxGeometry(w / 100, 0.3, h / 100);

      // Component color based on type
      const color = getComponentColor(component.type);
      const material = new THREE.MeshStandardMaterial({
        color,
        roughness: 0.5,
        metalness: 0.5,
        emissive: color,
        emissiveIntensity: 0.2
      });

      const mesh = new THREE.Mesh(geometry, material);

      // Position on board
      mesh.position.set(
        (x - 50) / 50 * 5,  // Map to board coordinates
        0.25,
        (y - 50) / 50 * 4
      );

      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.userData = { component };

      sceneRef.current.add(mesh);
      componentMeshesRef.current.set(component.id, mesh);

      // Add label
      if (showLabels) {
        const labelDiv = document.createElement('div');
        labelDiv.className = 'component-label';
        labelDiv.textContent = `${component.type}${component.value ? `: ${component.value}` : ''}`;
        labelDiv.style.cssText = `
          background: rgba(0, 0, 0, 0.8);
          color: white;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          white-space: nowrap;
        `;

        const label = new CSS2DObject(labelDiv);
        label.position.set(0, 0.5, 0);
        mesh.add(label);
      }
    });
  }, [components, showLabels]);

  // Mouse interaction
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !rendererRef.current || !cameraRef.current) return;

    const handleMouseMove = (event: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      mouseRef.current.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouseRef.current.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      // Raycast
      raycasterRef.current.setFromCamera(mouseRef.current, cameraRef.current!);
      const intersects = raycasterRef.current.intersectObjects(
        Array.from(componentMeshesRef.current.values())
      );

      if (intersects.length > 0) {
        const mesh = intersects[0].object as THREE.Mesh;
        const component = mesh.userData.component as Component;

        // Highlight
        if (mesh.material instanceof THREE.MeshStandardMaterial) {
          componentMeshesRef.current.forEach((m) => {
            if (m.material instanceof THREE.MeshStandardMaterial) {
              m.material.emissiveIntensity = m === mesh ? 0.5 : 0.2;
            }
          });
        }

        setHoveredComponent(component);
        container.style.cursor = 'pointer';
      } else {
        // Reset all
        componentMeshesRef.current.forEach((m) => {
          if (m.material instanceof THREE.MeshStandardMaterial) {
            m.material.emissiveIntensity = 0.2;
          }
        });

        setHoveredComponent(null);
        container.style.cursor = 'default';
      }
    };

    const handleClick = () => {
      if (hoveredComponent && onComponentClick) {
        onComponentClick(hoveredComponent);
      }
    };

    container.addEventListener('mousemove', handleMouseMove);
    container.addEventListener('click', handleClick);

    return () => {
      container.removeEventListener('mousemove', handleMouseMove);
      container.removeEventListener('click', handleClick);
    };
  }, [hoveredComponent, onComponentClick]);

  // Control functions
  const handleZoomIn = useCallback(() => {
    if (cameraRef.current && controlsRef.current) {
      const direction = new THREE.Vector3();
      cameraRef.current.getWorldDirection(direction);
      cameraRef.current.position.addScaledVector(direction, 1);
      controlsRef.current.update();
    }
  }, []);

  const handleZoomOut = useCallback(() => {
    if (cameraRef.current && controlsRef.current) {
      const direction = new THREE.Vector3();
      cameraRef.current.getWorldDirection(direction);
      cameraRef.current.position.addScaledVector(direction, -1);
      controlsRef.current.update();
    }
  }, []);

  const handleReset = useCallback(() => {
    if (cameraRef.current && controlsRef.current) {
      cameraRef.current.position.set(0, 5, 10);
      controlsRef.current.reset();
    }
  }, []);

  const toggleLabels = useCallback(() => {
    setShowLabels(!showLabels);
  }, [showLabels]);

  return (
    <div className="relative">
      <div ref={containerRef} className="rounded-lg overflow-hidden border border-gray-300" />

      {/* Controls */}
      <div className="absolute top-4 right-4 flex flex-col gap-2">
        <button
          onClick={handleZoomIn}
          className="p-2 bg-white rounded-lg shadow-lg hover:bg-gray-100 transition-colors"
          title="Zoom In"
        >
          <ZoomIn className="w-5 h-5" />
        </button>
        <button
          onClick={handleZoomOut}
          className="p-2 bg-white rounded-lg shadow-lg hover:bg-gray-100 transition-colors"
          title="Zoom Out"
        >
          <ZoomOut className="w-5 h-5" />
        </button>
        <button
          onClick={handleReset}
          className="p-2 bg-white rounded-lg shadow-lg hover:bg-gray-100 transition-colors"
          title="Reset View"
        >
          <RotateCcw className="w-5 h-5" />
        </button>
        <button
          onClick={toggleLabels}
          className="p-2 bg-white rounded-lg shadow-lg hover:bg-gray-100 transition-colors"
          title={showLabels ? 'Hide Labels' : 'Show Labels'}
        >
          {showLabels ? <Eye className="w-5 h-5" /> : <EyeOff className="w-5 h-5" />}
        </button>
      </div>

      {/* Hover tooltip */}
      {hoveredComponent && (
        <div className="absolute bottom-4 left-4 bg-white rounded-lg shadow-xl p-4 max-w-xs">
          <h3 className="font-semibold text-lg mb-2">{hoveredComponent.type}</h3>
          {hoveredComponent.value && (
            <p className="text-sm text-gray-600 mb-1">Value: {hoveredComponent.value}</p>
          )}
          <p className="text-sm text-gray-600">
            Confidence: {(hoveredComponent.confidence * 100).toFixed(1)}%
          </p>
        </div>
      )}
    </div>
  );
}

function getComponentColor(type: string): number {
  const colorMap: Record<string, number> = {
    resistor: 0x8B4513,
    capacitor: 0x4169E1,
    led: 0xFF4500,
    ic: 0x2F4F4F,
    transistor: 0x DAA520,
    diode: 0x8B0000,
    connector: 0x696969,
    inductor: 0x9370DB,
  };

  const normalizedType = type.toLowerCase();
  for (const [key, color] of Object.entries(colorMap)) {
    if (normalizedType.includes(key)) {
      return color;
    }
  }

  return 0x808080; // Default gray
}

export default PCB3DViewer;
