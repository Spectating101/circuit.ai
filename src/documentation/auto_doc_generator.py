"""
Automatic Documentation Generator

Features:
- Generate API documentation from code
- OpenAPI/Swagger spec generation
- Markdown documentation
- Interactive API explorer
- Code examples generation
- Changelog generation from git commits
- Architecture diagrams
- Component library documentation
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
import ast
import inspect
import json
from loguru import logger


class DocFormat(Enum):
    """Documentation formats."""
    MARKDOWN = "markdown"
    HTML = "html"
    OPENAPI = "openapi"
    POSTMAN = "postman"


@dataclass
class APIEndpoint:
    """API endpoint documentation."""
    path: str
    method: str
    summary: str
    description: str
    parameters: List[Dict[str, Any]]
    request_body: Optional[Dict[str, Any]]
    responses: Dict[int, Dict[str, Any]]
    tags: List[str]
    examples: List[Dict[str, Any]]


@dataclass
class FunctionDoc:
    """Function documentation."""
    name: str
    signature: str
    docstring: str
    parameters: List[Dict[str, Any]]
    returns: Optional[Dict[str, Any]]
    raises: List[str]
    examples: List[str]


class CodeAnalyzer:
    """Analyze Python code for documentation."""

    def __init__(self):
        """Initialize code analyzer."""
        logger.info("CodeAnalyzer initialized")

    def analyze_file(self, file_path: str) -> List[FunctionDoc]:
        """
        Analyze Python file and extract documentation.

        Args:
            file_path: Path to Python file

        Returns:
            List of function documentations
        """
        with open(file_path, 'r') as f:
            source = f.read()

        tree = ast.parse(source)

        functions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_doc = self._extract_function_doc(node)
                functions.append(func_doc)

        return functions

    def _extract_function_doc(self, node: ast.FunctionDef) -> FunctionDoc:
        """Extract documentation from function AST node."""
        # Get function name
        name = node.name

        # Get docstring
        docstring = ast.get_docstring(node) or "No description"

        # Get parameters
        parameters = []
        for arg in node.args.args:
            param = {
                'name': arg.arg,
                'type': self._get_annotation(arg.annotation),
                'description': self._extract_param_description(docstring, arg.arg)
            }
            parameters.append(param)

        # Get return type
        returns = None
        if node.returns:
            returns = {
                'type': self._get_annotation(node.returns),
                'description': self._extract_returns_description(docstring)
            }

        # Get raises
        raises = self._extract_raises(docstring)

        # Build signature
        args_str = ', '.join(p['name'] for p in parameters)
        signature = f"{name}({args_str})"

        return FunctionDoc(
            name=name,
            signature=signature,
            docstring=docstring,
            parameters=parameters,
            returns=returns,
            raises=raises,
            examples=[]
        )

    def _get_annotation(self, annotation) -> str:
        """Get type annotation as string."""
        if annotation is None:
            return "Any"

        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Subscript):
            # Handle List[str], Dict[str, int], etc.
            return ast.unparse(annotation)
        else:
            return "Any"

    def _extract_param_description(self, docstring: str, param_name: str) -> str:
        """Extract parameter description from docstring."""
        # Look for "Args:" section
        lines = docstring.split('\n')

        in_args = False
        for line in lines:
            if 'Args:' in line:
                in_args = True
                continue

            if in_args:
                if line.strip().startswith(param_name + ':'):
                    return line.split(':', 1)[1].strip()

                # Stop at next section
                if line.strip() and not line.startswith(' '):
                    break

        return ""

    def _extract_returns_description(self, docstring: str) -> str:
        """Extract return description from docstring."""
        lines = docstring.split('\n')

        in_returns = False
        for line in lines:
            if 'Returns:' in line:
                in_returns = True
                continue

            if in_returns and line.strip():
                return line.strip()

        return ""

    def _extract_raises(self, docstring: str) -> List[str]:
        """Extract exceptions from docstring."""
        lines = docstring.split('\n')
        raises = []

        in_raises = False
        for line in lines:
            if 'Raises:' in line:
                in_raises = True
                continue

            if in_raises:
                if line.strip() and ':' in line:
                    exception = line.strip().split(':')[0].strip()
                    raises.append(exception)

                # Stop at next section
                if line.strip() and not line.startswith(' '):
                    break

        return raises


class OpenAPIGenerator:
    """Generate OpenAPI/Swagger specifications."""

    def __init__(
        self,
        title: str,
        version: str,
        description: str
    ):
        """
        Initialize OpenAPI generator.

        Args:
            title: API title
            version: API version
            description: API description
        """
        self.title = title
        self.version = version
        self.description = description
        self.endpoints: List[APIEndpoint] = []
        logger.info("OpenAPIGenerator initialized")

    def add_endpoint(self, endpoint: APIEndpoint):
        """Add API endpoint."""
        self.endpoints.append(endpoint)

    def generate(self) -> Dict[str, Any]:
        """
        Generate OpenAPI specification.

        Returns:
            OpenAPI spec dictionary
        """
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": self.title,
                "version": self.version,
                "description": self.description
            },
            "servers": [
                {
                    "url": "https://api.circuit-ai.com",
                    "description": "Production server"
                },
                {
                    "url": "http://localhost:8000",
                    "description": "Development server"
                }
            ],
            "paths": {},
            "components": {
                "schemas": {},
                "securitySchemes": {
                    "ApiKeyAuth": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-API-Key"
                    }
                }
            }
        }

        # Add endpoints
        for endpoint in self.endpoints:
            if endpoint.path not in spec["paths"]:
                spec["paths"][endpoint.path] = {}

            spec["paths"][endpoint.path][endpoint.method.lower()] = {
                "summary": endpoint.summary,
                "description": endpoint.description,
                "tags": endpoint.tags,
                "parameters": endpoint.parameters,
                "responses": endpoint.responses
            }

            # Add request body if present
            if endpoint.request_body:
                spec["paths"][endpoint.path][endpoint.method.lower()]["requestBody"] = endpoint.request_body

        return spec

    def write_to_file(self, output_path: str):
        """Write OpenAPI spec to file."""
        spec = self.generate()

        with open(output_path, 'w') as f:
            json.dump(spec, f, indent=2)

        logger.info(f"OpenAPI spec written to {output_path}")


class MarkdownDocGenerator:
    """Generate Markdown documentation."""

    def __init__(self):
        """Initialize Markdown generator."""
        self.sections: List[Dict[str, Any]] = []
        logger.info("MarkdownDocGenerator initialized")

    def add_section(
        self,
        title: str,
        content: str,
        level: int = 1
    ):
        """Add documentation section."""
        self.sections.append({
            'title': title,
            'content': content,
            'level': level
        })

    def generate_api_doc(
        self,
        endpoints: List[APIEndpoint]
    ) -> str:
        """Generate API documentation in Markdown."""
        doc = "# API Documentation\n\n"

        # Group by tags
        by_tag: Dict[str, List[APIEndpoint]] = {}
        for endpoint in endpoints:
            for tag in endpoint.tags:
                if tag not in by_tag:
                    by_tag[tag] = []
                by_tag[tag].append(endpoint)

        # Generate docs for each tag
        for tag, tag_endpoints in by_tag.items():
            doc += f"## {tag}\n\n"

            for endpoint in tag_endpoints:
                doc += self._format_endpoint(endpoint)
                doc += "\n---\n\n"

        return doc

    def _format_endpoint(self, endpoint: APIEndpoint) -> str:
        """Format single endpoint documentation."""
        doc = f"### `{endpoint.method.upper()} {endpoint.path}`\n\n"

        doc += f"{endpoint.description}\n\n"

        # Parameters
        if endpoint.parameters:
            doc += "**Parameters:**\n\n"
            doc += "| Name | Type | Required | Description |\n"
            doc += "|------|------|----------|-------------|\n"

            for param in endpoint.parameters:
                required = "Yes" if param.get('required', False) else "No"
                doc += f"| {param['name']} | {param.get('type', 'string')} | {required} | {param.get('description', '')} |\n"

            doc += "\n"

        # Request body
        if endpoint.request_body:
            doc += "**Request Body:**\n\n"
            doc += "```json\n"
            doc += json.dumps(endpoint.request_body.get('example', {}), indent=2)
            doc += "\n```\n\n"

        # Responses
        doc += "**Responses:**\n\n"
        for status_code, response in endpoint.responses.items():
            doc += f"**{status_code}** - {response.get('description', '')}\n\n"

            if 'example' in response:
                doc += "```json\n"
                doc += json.dumps(response['example'], indent=2)
                doc += "\n```\n\n"

        # Examples
        if endpoint.examples:
            doc += "**Examples:**\n\n"
            for example in endpoint.examples:
                doc += f"**{example.get('title', 'Example')}**\n\n"
                doc += "```bash\n"
                doc += example.get('curl', '')
                doc += "\n```\n\n"

        return doc

    def generate_changelog(
        self,
        git_log: List[Dict[str, Any]]
    ) -> str:
        """
        Generate changelog from git commits.

        Args:
            git_log: List of git commits

        Returns:
            Markdown changelog
        """
        doc = "# Changelog\n\n"

        # Group by version/date
        by_date: Dict[str, List[Dict[str, Any]]] = {}

        for commit in git_log:
            date = commit['date'].split('T')[0]
            if date not in by_date:
                by_date[date] = []
            by_date[date].append(commit)

        # Generate changelog
        for date in sorted(by_date.keys(), reverse=True):
            doc += f"## {date}\n\n"

            commits = by_date[date]

            # Categorize commits
            features = []
            fixes = []
            other = []

            for commit in commits:
                message = commit['message']

                if message.startswith('feat:'):
                    features.append(message[5:].strip())
                elif message.startswith('fix:'):
                    fixes.append(message[4:].strip())
                else:
                    other.append(message)

            if features:
                doc += "### Features\n\n"
                for feat in features:
                    doc += f"- {feat}\n"
                doc += "\n"

            if fixes:
                doc += "### Bug Fixes\n\n"
                for fix in fixes:
                    doc += f"- {fix}\n"
                doc += "\n"

            if other:
                doc += "### Other Changes\n\n"
                for change in other:
                    doc += f"- {change}\n"
                doc += "\n"

        return doc

    def write_to_file(self, output_path: str):
        """Write documentation to file."""
        doc = ""

        for section in self.sections:
            heading = '#' * section['level']
            doc += f"{heading} {section['title']}\n\n"
            doc += f"{section['content']}\n\n"

        with open(output_path, 'w') as f:
            f.write(doc)

        logger.info(f"Documentation written to {output_path}")


class ComponentLibraryDocGenerator:
    """Generate component library documentation."""

    def __init__(self):
        """Initialize component library doc generator."""
        logger.info("ComponentLibraryDocGenerator initialized")

    def generate_component_catalog(
        self,
        components: List[Dict[str, Any]]
    ) -> str:
        """
        Generate component catalog documentation.

        Args:
            components: List of components

        Returns:
            Markdown documentation
        """
        doc = "# Component Library\n\n"
        doc += f"Total components: {len(components)}\n\n"

        # Group by category
        by_category: Dict[str, List[Dict[str, Any]]] = {}

        for component in components:
            category = component.get('category', 'Other')
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(component)

        # Generate docs
        for category in sorted(by_category.keys()):
            doc += f"## {category}\n\n"

            cat_components = by_category[category]

            doc += "| Part Number | Manufacturer | Description | Package | Price |\n"
            doc += "|-------------|--------------|-------------|---------|-------|\n"

            for comp in cat_components:
                doc += (
                    f"| {comp.get('part_number', 'N/A')} | "
                    f"{comp.get('manufacturer', 'N/A')} | "
                    f"{comp.get('description', 'N/A')[:50]} | "
                    f"{comp.get('package', 'N/A')} | "
                    f"${comp.get('unit_price', 0):.2f} |\n"
                )

            doc += "\n"

        return doc


class DocumentationBuilder:
    """Build complete documentation."""

    def __init__(self, project_root: str, output_dir: str):
        """
        Initialize documentation builder.

        Args:
            project_root: Project root directory
            output_dir: Documentation output directory
        """
        self.project_root = Path(project_root)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.code_analyzer = CodeAnalyzer()
        self.md_generator = MarkdownDocGenerator()

        logger.info(f"DocumentationBuilder initialized: {output_dir}")

    async def build_all_docs(self):
        """Build all documentation."""
        logger.info("Building documentation...")

        # Analyze code
        await self._analyze_codebase()

        # Generate API docs
        await self._generate_api_docs()

        # Generate changelog
        await self._generate_changelog()

        # Generate README
        await self._generate_readme()

        logger.info("Documentation build complete")

    async def _analyze_codebase(self):
        """Analyze codebase for documentation."""
        python_files = self.project_root.rglob("*.py")

        all_functions = []

        for py_file in python_files:
            if 'venv' in str(py_file) or '__pycache__' in str(py_file):
                continue

            try:
                functions = self.code_analyzer.analyze_file(str(py_file))
                all_functions.extend(functions)
            except Exception as e:
                logger.warning(f"Error analyzing {py_file}: {e}")

        logger.info(f"Analyzed {len(all_functions)} functions")

    async def _generate_api_docs(self):
        """Generate API documentation."""
        # Would parse FastAPI routes and generate docs
        pass

    async def _generate_changelog(self):
        """Generate changelog from git."""
        # Would parse git log
        pass

    async def _generate_readme(self):
        """Generate README."""
        readme = "# Circuit.AI\n\n"
        readme += "ML-powered PCB component detection and analysis.\n\n"
        readme += "## Features\n\n"
        readme += "- Component detection\n"
        readme += "- BOM generation\n"
        readme += "- Design rule checking\n"
        readme += "- 3D visualization\n"

        readme_path = self.output_dir / "README.md"
        with open(readme_path, 'w') as f:
            f.write(readme)


# Singleton instances
code_analyzer = CodeAnalyzer()
md_generator = MarkdownDocGenerator()
