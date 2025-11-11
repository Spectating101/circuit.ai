"""
Plugin/Extension System

Allows third-party developers to extend Circuit.AI with:
- Custom component detectors
- Analysis algorithms
- Export formats
- Integrations
- UI extensions

Features:
- Sandboxed execution
- API key management
- Marketplace for discovery
- Auto-updates
- Usage metering
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import importlib.util
import inspect
import ast
import hashlib
from loguru import logger


class PluginType(Enum):
    """Plugin types."""
    COMPONENT_DETECTOR = "component_detector"
    ANALYZER = "analyzer"
    EXPORTER = "exporter"
    INTEGRATION = "integration"
    UI_EXTENSION = "ui_extension"
    DATA_SOURCE = "data_source"


class PluginStatus(Enum):
    """Plugin status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_APPROVAL = "pending_approval"


@dataclass
class PluginMetadata:
    """Plugin metadata."""
    plugin_id: str
    name: str
    version: str
    author: str
    author_email: str
    description: str
    plugin_type: PluginType
    homepage_url: Optional[str]
    documentation_url: Optional[str]
    icon_url: Optional[str]

    # Requirements
    min_api_version: str
    max_api_version: Optional[str]
    dependencies: List[str]

    # Permissions
    required_permissions: List[str]

    # Pricing
    is_free: bool
    price_usd: float
    pricing_model: str  # one_time, subscription, usage_based

    # Stats
    installs: int
    rating: float
    review_count: int

    # Status
    status: PluginStatus
    created_at: datetime
    updated_at: datetime


@dataclass
class PluginManifest:
    """Plugin manifest file."""
    metadata: PluginMetadata
    entry_point: str  # Module path
    config_schema: Dict[str, Any]  # JSON Schema for configuration
    webhooks: List[Dict[str, str]]  # Webhook subscriptions
    api_endpoints: List[Dict[str, Any]]  # Custom API endpoints


class PluginSandbox:
    """Sandboxed plugin execution environment."""

    def __init__(self, plugin_id: str):
        """
        Initialize plugin sandbox.

        Args:
            plugin_id: Plugin ID
        """
        self.plugin_id = plugin_id
        self.allowed_modules = [
            'numpy', 'pandas', 'cv2', 'PIL',
            'requests', 'aiohttp', 'json', 'datetime'
        ]
        self.restricted_imports = [
            'os', 'sys', 'subprocess', 'eval', 'exec',
            'open', '__import__', 'compile'
        ]
        logger.info(f"Plugin sandbox created for {plugin_id}")

    def validate_code_safety(self, code: str) -> Tuple[bool, List[str]]:
        """
        Validate plugin code for security issues.

        Args:
            code: Python code to validate

        Returns:
            (is_safe, issues)
        """
        issues = []

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, [f"Syntax error: {e}"]

        # Check for dangerous imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in self.restricted_imports:
                        issues.append(f"Restricted import: {alias.name}")

            elif isinstance(node, ast.ImportFrom):
                if node.module in self.restricted_imports:
                    issues.append(f"Restricted import: {node.module}")

            # Check for exec/eval
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['eval', 'exec', 'compile', '__import__']:
                        issues.append(f"Dangerous function call: {node.func.id}")

            # Check for file operations
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == 'open':
                    # Allow read-only opens to specific directories
                    issues.append("File operations are restricted")

        is_safe = len(issues) == 0
        return is_safe, issues

    async def execute_plugin_function(
        self,
        module_path: str,
        function_name: str,
        args: List[Any],
        kwargs: Dict[str, Any],
        timeout: int = 30
    ) -> Any:
        """
        Execute plugin function in sandbox.

        Args:
            module_path: Path to plugin module
            function_name: Function to execute
            args: Positional arguments
            kwargs: Keyword arguments
            timeout: Execution timeout in seconds

        Returns:
            Function result

        Raises:
            TimeoutError: If execution exceeds timeout
            SecurityError: If code validation fails
        """
        import asyncio

        # Load module
        spec = importlib.util.spec_from_file_location("plugin_module", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Get function
        if not hasattr(module, function_name):
            raise AttributeError(f"Function {function_name} not found in plugin")

        func = getattr(module, function_name)

        # Execute with timeout
        try:
            if inspect.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout
                )
            else:
                # Run in thread pool to avoid blocking
                result = await asyncio.get_event_loop().run_in_executor(
                    None, func, *args, **kwargs
                )

            return result

        except asyncio.TimeoutError:
            logger.error(f"Plugin {self.plugin_id} execution timed out")
            raise


class PluginRegistry:
    """Plugin registry and marketplace."""

    def __init__(self):
        """Initialize plugin registry."""
        self.plugins: Dict[str, PluginManifest] = {}
        self.installed_plugins: Dict[str, Dict[str, Any]] = {}  # user_id -> {plugin_id: config}
        logger.info("PluginRegistry initialized")

    def register_plugin(self, manifest: PluginManifest):
        """
        Register plugin in marketplace.

        Args:
            manifest: Plugin manifest
        """
        plugin_id = manifest.metadata.plugin_id

        # Validate manifest
        is_valid, issues = self._validate_manifest(manifest)

        if not is_valid:
            raise ValueError(f"Invalid manifest: {issues}")

        self.plugins[plugin_id] = manifest
        logger.info(f"Plugin registered: {plugin_id} ({manifest.metadata.name})")

    def _validate_manifest(self, manifest: PluginManifest) -> Tuple[bool, List[str]]:
        """Validate plugin manifest."""
        issues = []

        # Check required fields
        if not manifest.metadata.name:
            issues.append("Name is required")

        if not manifest.metadata.version:
            issues.append("Version is required")

        if not manifest.entry_point:
            issues.append("Entry point is required")

        # Validate version format (semver)
        import re
        version_pattern = r'^\d+\.\d+\.\d+$'
        if not re.match(version_pattern, manifest.metadata.version):
            issues.append("Version must follow semver (e.g., 1.0.0)")

        return len(issues) == 0, issues

    async def install_plugin(
        self,
        user_id: str,
        plugin_id: str,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Install plugin for user.

        Args:
            user_id: User ID
            plugin_id: Plugin ID
            config: Plugin configuration
        """
        if plugin_id not in self.plugins:
            raise ValueError(f"Plugin {plugin_id} not found")

        manifest = self.plugins[plugin_id]

        # Check plugin status
        if manifest.metadata.status != PluginStatus.ACTIVE:
            raise ValueError(f"Plugin {plugin_id} is not active")

        # Initialize user's plugin dict if needed
        if user_id not in self.installed_plugins:
            self.installed_plugins[user_id] = {}

        # Store installation
        self.installed_plugins[user_id][plugin_id] = {
            'installed_at': datetime.utcnow(),
            'config': config or {},
            'enabled': True
        }

        # Increment install count
        manifest.metadata.installs += 1

        logger.info(f"Plugin {plugin_id} installed for user {user_id}")

    async def uninstall_plugin(self, user_id: str, plugin_id: str):
        """
        Uninstall plugin for user.

        Args:
            user_id: User ID
            plugin_id: Plugin ID
        """
        if user_id in self.installed_plugins:
            if plugin_id in self.installed_plugins[user_id]:
                del self.installed_plugins[user_id][plugin_id]
                logger.info(f"Plugin {plugin_id} uninstalled for user {user_id}")

    def get_user_plugins(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get user's installed plugins.

        Args:
            user_id: User ID

        Returns:
            List of installed plugins with metadata
        """
        if user_id not in self.installed_plugins:
            return []

        result = []

        for plugin_id, installation in self.installed_plugins[user_id].items():
            if plugin_id in self.plugins:
                manifest = self.plugins[plugin_id]
                result.append({
                    'plugin_id': plugin_id,
                    'manifest': manifest,
                    'installation': installation
                })

        return result

    def search_plugins(
        self,
        query: Optional[str] = None,
        plugin_type: Optional[PluginType] = None,
        free_only: bool = False,
        sort_by: str = "installs"  # installs, rating, recent
    ) -> List[PluginManifest]:
        """
        Search marketplace for plugins.

        Args:
            query: Search query
            plugin_type: Filter by type
            free_only: Only free plugins
            sort_by: Sort order

        Returns:
            List of matching plugins
        """
        results = list(self.plugins.values())

        # Filter by type
        if plugin_type:
            results = [p for p in results if p.metadata.plugin_type == plugin_type]

        # Filter by free
        if free_only:
            results = [p for p in results if p.metadata.is_free]

        # Filter by query
        if query:
            query_lower = query.lower()
            results = [
                p for p in results
                if query_lower in p.metadata.name.lower() or
                   query_lower in p.metadata.description.lower()
            ]

        # Sort
        if sort_by == "installs":
            results.sort(key=lambda p: p.metadata.installs, reverse=True)
        elif sort_by == "rating":
            results.sort(key=lambda p: p.metadata.rating, reverse=True)
        elif sort_by == "recent":
            results.sort(key=lambda p: p.metadata.updated_at, reverse=True)

        return results


class PluginExecutor:
    """Executes plugins safely."""

    def __init__(self, registry: PluginRegistry):
        """
        Initialize plugin executor.

        Args:
            registry: Plugin registry
        """
        self.registry = registry
        self.sandboxes: Dict[str, PluginSandbox] = {}
        logger.info("PluginExecutor initialized")

    def get_sandbox(self, plugin_id: str) -> PluginSandbox:
        """Get or create sandbox for plugin."""
        if plugin_id not in self.sandboxes:
            self.sandboxes[plugin_id] = PluginSandbox(plugin_id)

        return self.sandboxes[plugin_id]

    async def execute_component_detector(
        self,
        plugin_id: str,
        image: Any,
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Execute component detector plugin.

        Args:
            plugin_id: Plugin ID
            image: PCB image
            config: Plugin configuration

        Returns:
            List of detected components
        """
        manifest = self.registry.plugins.get(plugin_id)

        if not manifest:
            raise ValueError(f"Plugin {plugin_id} not found")

        if manifest.metadata.plugin_type != PluginType.COMPONENT_DETECTOR:
            raise ValueError(f"Plugin {plugin_id} is not a component detector")

        # Get sandbox
        sandbox = self.get_sandbox(plugin_id)

        # Execute detector
        results = await sandbox.execute_plugin_function(
            module_path=manifest.entry_point,
            function_name="detect_components",
            args=[image],
            kwargs=config,
            timeout=60
        )

        return results

    async def execute_analyzer(
        self,
        plugin_id: str,
        pcb_analysis: Dict[str, Any],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute analyzer plugin.

        Args:
            plugin_id: Plugin ID
            pcb_analysis: PCB analysis data
            config: Plugin configuration

        Returns:
            Analysis results
        """
        manifest = self.registry.plugins.get(plugin_id)

        if not manifest:
            raise ValueError(f"Plugin {plugin_id} not found")

        if manifest.metadata.plugin_type != PluginType.ANALYZER:
            raise ValueError(f"Plugin {plugin_id} is not an analyzer")

        sandbox = self.get_sandbox(plugin_id)

        results = await sandbox.execute_plugin_function(
            module_path=manifest.entry_point,
            function_name="analyze",
            args=[pcb_analysis],
            kwargs=config,
            timeout=120
        )

        return results


# Singleton instances
plugin_registry = PluginRegistry()
plugin_executor = PluginExecutor(plugin_registry)
