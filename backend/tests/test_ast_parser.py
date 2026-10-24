"""Tests for the Python AST parser."""
import tempfile
import os
from pathlib import Path

import pytest
from app.services.ast_parser import parse_codebase, PythonASTParser


@pytest.fixture
def sample_python_project():
    """Create a temporary Python project for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a simple Python file
        main_py = Path(tmpdir) / "main.py"
        main_py.write_text("""
def hello():
    print("Hello")

class Greeter:
    def greet(self, name: str) -> str:
        return f"Hello {name}"

    def call_hello(self):
        hello()

if __name__ == "__main__":
    g = Greeter()
    g.greet("World")
""")

        # Create a submodule
        subdir = Path(tmpdir) / "subpkg"
        subdir.mkdir()
        init_py = subdir / "__init__.py"
        init_py.write_text("")

        utils_py = subdir / "utils.py"
        utils_py.write_text("""
from main import hello

def utility():
    hello()
    return "done"
""")

        yield tmpdir


def test_parse_codebase(sample_python_project):
    """Test parsing a codebase."""
    result = parse_codebase(sample_python_project)

    assert len(result.errors) == 0
    assert len(result.nodes) > 0
    assert len(result.edges) > 0

    # Check for expected node types
    node_types = {n.type for n in result.nodes}
    assert "module" in node_types
    assert "function" in node_types
    assert "class" in node_types
    assert "import" in node_types or "import_from" in node_types

    # Check for expected edge types
    edge_types = {e.type for e in result.edges}
    assert "contains" in edge_types
    assert "calls" in edge_types or "imports" in edge_types


def test_parse_single_file():
    """Test parsing a single file with known structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
import os
from typing import List

class BaseClass:
    pass

class DerivedClass(BaseClass):
    def method(self):
        pass

def standalone():
    d = DerivedClass()
    d.method()
    return os.path.join("a", "b")
""")

        parser = PythonASTParser(tmpdir)
        result = parser.parse_file(test_file)

        assert len(result.errors) == 0

        # Check nodes
        nodes_by_type = {}
        for node in result.nodes:
            nodes_by_type.setdefault(node.type, []).append(node)

        assert len(nodes_by_type.get("module", [])) == 1
        assert len(nodes_by_type.get("class", [])) == 2  # BaseClass, DerivedClass
        assert len(nodes_by_type.get("function", [])) >= 2  # method, standalone
        assert len(nodes_by_type.get("import", [])) >= 1  # import os
        assert len(nodes_by_type.get("import_from", [])) >= 1  # from typing import List

        # Check edges
        edges_by_type = {}
        for edge in result.edges:
            edges_by_type.setdefault(edge.type, []).append(edge)

        assert "contains" in edges_by_type
        assert "inherits" in edges_by_type  # DerivedClass -> BaseClass
        assert "calls" in edges_by_type  # standalone calls DerivedClass.method and os.path.join


def test_inheritance_edge():
    """Test that inheritance edges are created correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
class Parent:
    pass

class Child(Parent):
    pass
""")

        parser = PythonASTParser(tmpdir)
        result = parser.parse_file(test_file)

        inherits_edges = [e for e in result.edges if e.type == "inherits"]
        assert len(inherits_edges) == 1
        # Child inherits from Parent
        edge = inherits_edges[0]
        assert "Child" in edge.edge_metadata.get("base", "") or "Parent" in edge.edge_metadata.get("base", "")

def test_import_edges():
    """Test that import edges are created."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
import json
from collections import defaultdict
""")

        parser = PythonASTParser(tmpdir)
        result = parser.parse_file(test_file)

        imports_edges = [e for e in result.edges if e.type == "imports"]
        assert len(imports_edges) >= 2


def test_async_function():
    """Test parsing async functions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
async def async_func():
    pass

def sync_func():
    async_func()
""")

        parser = PythonASTParser(tmpdir)
        result = parser.parse_file(test_file)

        func_nodes = [n for n in result.nodes if n.type == "function"]
        async_funcs = [n for n in func_nodes if n.node_metadata.get("is_async")]
        assert len(async_funcs) == 1
        assert async_funcs[0].name == "async_func"


def test_decorators():
    """Test that decorators are captured in metadata."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
@property
def decorated():
    return 1
""")

        parser = PythonASTParser(tmpdir)
        result = parser.parse_file(test_file)

        func_nodes = [n for n in result.nodes if n.type == "function"]
        assert len(func_nodes) == 1
        decorators = func_nodes[0].node_metadata.get("decorators", [])
        assert "@property" in decorators[0] or "property" in decorators[0]


def test_syntax_error():
    """Test that syntax errors are captured."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
def broken(
    pass
""")

        parser = PythonASTParser(tmpdir)
        result = parser.parse_file(test_file)

        assert len(result.errors) > 0
        assert "Syntax error" in result.errors[0]


def test_empty_file():
    """Test parsing an empty file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("")

        parser = PythonASTParser(tmpdir)
        result = parser.parse_file(test_file)

        assert len(result.errors) == 0
        assert len(result.nodes) == 1  # module node
        assert result.nodes[0].type == "module"


def test_relative_imports():
    """Test relative import parsing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create package structure
        pkg = Path(tmpdir) / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")

        sub = pkg / "sub.py"
        sub.write_text("""
from . import something
from .. import parent
""")

        parser = PythonASTParser(tmpdir)
        result = parser.parse_file(sub)

        import_from_nodes = [n for n in result.nodes if n.type == "import_from"]
        assert len(import_from_nodes) >= 2
        # Check relative import levels
        levels = [n.node_metadata.get("level") for n in import_from_nodes]
        assert 1 in levels  # from . import
        assert 2 in levels  # from .. import