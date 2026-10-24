"""
Deterministic AST parser for Python files.

Extracts typed nodes (functions, classes, imports) and edges (calls, imports, inheritance)
from source code without relying on vector embeddings or LLMs.
"""
import ast
import hashlib
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from app.models.graph import GraphNode, GraphEdge


@dataclass
class ParseResult:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class PythonASTParser:
    """Parse Python source files into a knowledge graph using AST."""

    NODE_TYPES = {
        "function": "function",
        "class": "class",
        "import": "import",
        "import_from": "import_from",
        "module": "module",
    }

    EDGE_TYPES = {
        "calls": "calls",
        "imports": "imports",
        "inherits": "inherits",
        "contains": "contains",
        "references": "references",
    }

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self.result = ParseResult()
        self._node_map: dict[str, GraphNode] = {}  # qualified name -> node
        self._current_module: Optional[GraphNode] = None
        self._current_class: Optional[GraphNode] = None
        self._import_aliases: dict[str, str] = {}  # alias -> full name

    def _make_id(self, *parts: str) -> str:
        """Generate deterministic ID from parts."""
        content = "|".join(parts)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _rel_path(self, path: Path) -> str:
        """Get path relative to root."""
        try:
            return str(path.relative_to(self.root_path))
        except ValueError:
            return str(path)

    def _add_node(
        self,
        node_type: str,
        name: str,
        file_path: str,
        line_start: int,
        line_end: int,
        metadata: dict | None = None,
        qualified_name: str | None = None,
    ) -> GraphNode:
        """Create and register a node."""
        node_id = self._make_id(file_path, node_type, name, str(line_start))
        node = GraphNode(
            id=node_id,
            type=node_type,
            name=name,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            node_metadata=metadata or {},
        )
        self.result.nodes.append(node)
        if qualified_name:
            self._node_map[qualified_name] = node
        return node

    def _add_edge(
        self,
        source: GraphNode,
        target: GraphNode,
        edge_type: str,
        metadata: dict | None = None,
    ) -> None:
        """Create an edge between two nodes."""
        edge_id = self._make_id(source.id, target.id, edge_type)
        edge = GraphEdge(
            id=edge_id,
            source_id=source.id,
            target_id=target.id,
            type=edge_type,
            edge_metadata=metadata or {},
        )
        self.result.edges.append(edge)

    def parse_file(self, file_path: Path) -> ParseResult:
        """Parse a single Python file."""
        rel_path = self._rel_path(file_path)
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as e:
            self.result.errors.append(f"{rel_path}:{e.lineno}: Syntax error: {e.msg}")
            return self.result
        except Exception as e:
            self.result.errors.append(f"{rel_path}: Failed to read/parse: {e}")
            return self.result

        # Create module node
        module_name = rel_path.replace("/", ".").replace(".py", "")
        self._current_module = self._add_node(
            node_type="module",
            name=module_name,
            file_path=rel_path,
            line_start=1,
            line_end=len(source.splitlines()),
            qualified_name=module_name,
        )

        # Visit the AST
        self._import_aliases = {}
        self._visit(tree)

        return self.result

    def _visit(self, node: ast.AST) -> None:
        """Dispatch to appropriate visitor method."""
        method_name = f"_visit_{node.__class__.__name__}"
        visitor = getattr(self, method_name, self._generic_visit)
        visitor(node)

    def _generic_visit(self, node: ast.AST) -> None:
        """Default visitor - recurse into children."""
        for child in ast.iter_child_nodes(node):
            self._visit(child)

    def _visit_Module(self, node: ast.Module) -> None:
        for child in node.body:
            self._visit(child)

    def _visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node, is_async=False)

    def _visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node, is_async=True)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool) -> None:
        qualified_name = self._get_qualified_name(node.name)
        func_node = self._add_node(
            node_type="function",
            name=node.name,
            file_path=self._current_module.file_path if self._current_module else "",
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            metadata={
                "is_async": is_async,
                "args": [arg.arg for arg in node.args.args],
                "returns": ast.unparse(node.returns) if node.returns else None,
                "decorators": [ast.unparse(d) for d in node.decorator_list],
            },
            qualified_name=qualified_name,
        )

        # Edge: module/class contains function
        container = self._current_class or self._current_module
        if container:
            self._add_edge(container, func_node, "contains")

        # Visit function body for calls
        old_class = self._current_class
        self._current_class = func_node  # Track for nested functions
        for child in node.body:
            self._visit(child)
        self._current_class = old_class

    def _visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualified_name = self._get_qualified_name(node.name)
        class_node = self._add_node(
            node_type="class",
            name=node.name,
            file_path=self._current_module.file_path if self._current_module else "",
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            metadata={
                "bases": [ast.unparse(b) for b in node.bases],
                "decorators": [ast.unparse(d) for d in node.decorator_list],
                "keywords": [ast.unparse(k) for k in node.keywords],
            },
            qualified_name=qualified_name,
        )

        # Edge: module contains class
        if self._current_module:
            self._add_edge(self._current_module, class_node, "contains")

        # Edges: inheritance
        for base in node.bases:
            base_name = ast.unparse(base)
            # Try to find the base class in our node map
            # First try qualified name (module.Class), then just class name
            base_node = self._node_map.get(base_name) or self._node_map.get(
                base_name.split(".")[-1]
            )
            # Also try with current module prefix
            if not base_node and self._current_module:
                qualified_base = f"{self._current_module.name}.{base_name}"
                base_node = self._node_map.get(qualified_base) or self._node_map.get(
                    qualified_base.split(".")[-1]
                )
            if base_node:
                self._add_edge(class_node, base_node, "inherits", {"base": base_name})

        old_class = self._current_class
        self._current_class = class_node
        for child in node.body:
            self._visit(child)
        self._current_class = old_class

    def _visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            import_name = alias.name
            alias_name = alias.asname or alias.name.split(".")[-1]
            self._import_aliases[alias_name] = import_name

            import_node = self._add_node(
                node_type="import",
                name=alias_name,
                file_path=self._current_module.file_path if self._current_module else "",
                line_start=node.lineno,
                line_end=node.end_lineno or node.lineno,
                metadata={
                    "full_name": import_name,
                    "alias": alias.asname,
                },
                qualified_name=f"{self._current_module.name}.{alias_name}" if self._current_module else alias_name,
            )

            if self._current_module:
                self._add_edge(self._current_module, import_node, "contains")
                self._add_edge(self._current_module, import_node, "imports", {"import": import_name})

    def _visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        level = node.level  # 0 = absolute, >0 = relative

        for alias in node.names:
            import_name = f"{module}.{alias.name}" if module else alias.name
            if level > 0:
                # Relative import - resolve relative to current module
                if self._current_module:
                    parts = self._current_module.name.split(".")
                    base = ".".join(parts[:-level]) if level <= len(parts) else ""
                    import_name = f"{base}.{module}.{alias.name}" if module and base else f"{base}.{alias.name}" if base else f"{'.' * level}{module}.{alias.name}"
            alias_name = alias.asname or alias.name
            self._import_aliases[alias_name] = import_name

            import_node = self._add_node(
                node_type="import_from",
                name=alias_name,
                file_path=self._current_module.file_path if self._current_module else "",
                line_start=node.lineno,
                line_end=node.end_lineno or node.lineno,
                metadata={
                    "full_name": import_name,
                    "module": module,
                    "level": level,
                    "alias": alias.asname,
                },
                qualified_name=f"{self._current_module.name}.{alias_name}" if self._current_module else alias_name,
            )

            if self._current_module:
                self._add_edge(self._current_module, import_node, "contains")
                self._add_edge(self._current_module, import_node, "imports", {"import": import_name, "from": module, "level": level})

    def _visit_Call(self, node: ast.Call) -> None:
        """Extract function calls."""
        caller = self._current_class or self._current_module
        if not caller:
            self._generic_visit(node)
            return

        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            # Try to find the called function/class
            # Check qualified name first, then simple name
            target = self._node_map.get(func_name)
            if not target and self._current_module:
                target = self._node_map.get(f"{self._current_module.name}.{func_name}")
            if not target:
                target = self._node_map.get(func_name.split(".")[-1])
            if target and target.type in ("function", "class"):
                self._add_edge(caller, target, "calls", {"function": func_name})

        elif isinstance(node.func, ast.Attribute):
            # Method call: obj.method()
            attr_name = node.func.attr
            # Try to find the method in the current class or module
            target = None
            if self._current_class and self._current_class.type == "class":
                qualified_method = f"{self._current_module.name}.{self._current_class.name}.{attr_name}" if self._current_module else f"{self._current_class.name}.{attr_name}"
                target = self._node_map.get(qualified_method)
            if not target:
                target = self._node_map.get(attr_name)
            if target and target.type == "function":
                self._add_edge(caller, target, "calls", {"method": attr_name})

        self._generic_visit(node)

    def _visit_Name(self, node: ast.Name) -> None:
        """Track variable references (limited)."""
        self._generic_visit(node)

    def _get_qualified_name(self, name: str) -> str:
        """Build qualified name from current context."""
        parts = []
        if self._current_module:
            parts.append(self._current_module.name)
        if self._current_class and self._current_class.type == "class":
            parts.append(self._current_class.name)
        parts.append(name)
        return ".".join(parts)


def parse_codebase(root_path: str) -> ParseResult:
    """Parse all Python files in a codebase."""
    parser = PythonASTParser(root_path)
    root = Path(root_path).resolve()

    if not root.exists():
        parser.result.errors.append(f"Path does not exist: {root_path}")
        return parser.result

    python_files = list(root.rglob("*.py"))
    parser.result.errors = []

    for py_file in python_files:
        # Skip hidden directories and __pycache__
        if any(part.startswith(".") or part == "__pycache__" for part in py_file.parts):
            continue
        parser.parse_file(py_file)

    return parser.result