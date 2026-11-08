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
def test_lambda_functions():
    """Test parsing lambda functions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
def foo():
    f = lambda x: x + 1
    g = lambda a, b: a * b
    return f, g

class MyClass:
    method = lambda self: "method"
""")

        parser = PythonASTParser(tmpdir)
        result = parser.parse_file(test_file)

        assert len(result.errors) == 0
        lambda_nodes = [n for n in result.nodes if n.type == "lambda"]
        assert len(lambda_nodes) == 3
        # Check metadata
        for ln in lambda_nodes:
            assert "args" in ln.node_metadata
            assert "returns" in ln.node_metadata
        # First lambda: lambda x: x + 1
        assert lambda_nodes[0].node_metadata["args"] == ["x"]
        # Second lambda: lambda a, b: a * b
        assert lambda_nodes[1].node_metadata["args"] == ["a", "b"]
        # Class lambda: lambda self: "method"
        assert lambda_nodes[2].node_metadata["args"] == ["self"]


def test_comprehensions():
    """Test parsing list, set, dict comprehensions and generator expressions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
def foo():
    squares = [x**2 for x in range(10)]
    unique = {x for x in range(5)}
    mapping = {k: v for k, v in zip("ab", [1,2])}
    gen = (y for y in range(5))
    return squares, unique, mapping, gen
""")

        parser = PythonASTParser(tmpdir)
        result = parser.parse_file(test_file)

        assert len(result.errors) == 0
        listcomp_nodes = [n for n in result.nodes if n.type == "listcomp"]
        setcomp_nodes = [n for n in result.nodes if n.type == "setcomp"]
        dictcomp_nodes = [n for n in result.nodes if n.type == "dictcomp"]
        genexp_nodes = [n for n in result.nodes if n.type == "genexp"]

        assert len(listcomp_nodes) == 1
        assert len(setcomp_nodes) == 1
        assert len(dictcomp_nodes) == 1
        assert len(genexp_nodes) == 1

        # Check metadata
        assert "result" in listcomp_nodes[0].node_metadata
        assert "generators" in listcomp_nodes[0].node_metadata
        assert listcomp_nodes[0].node_metadata["generators"] == 1

        assert "result" in dictcomp_nodes[0].node_metadata
        assert "k: v" in dictcomp_nodes[0].node_metadata["result"]

def test_super_calls():
    """Test that super() calls are parsed correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
class Base:
    def method(self):
        return "base"

    def other(self):
        return "other"

class Derived(Base):
    def method(self):
        super().method()
        super().other()

    def call_super_in_nested(self):
        def inner():
            super().method()
        inner()

    def call_super_in_lambda(self):
        func = lambda: super().method()
        func()

    def call_super_in_comp(self):
        return [super().method() for _ in range(3)]
""")

        parser = PythonASTParser(tmpdir)
        result = parser.parse_file(test_file)

        assert len(result.errors) == 0
        
        # Find super call edges
        super_edges = [e for e in result.edges if e.edge_metadata.get("super") is True]
        assert len(super_edges) == 5  # method, other, nested (inner), lambda, comp
        
        # All should call Base.method or Base.other
        for edge in super_edges:
            assert edge.edge_metadata["method"] in ("method", "other")
            # Target should be a function in Base
            target_node = next(n for n in result.nodes if n.id == edge.target_id)
            assert target_node.name in ("method", "other")
            # Source should be the function containing the super() call
            source_node = next(n for n in result.nodes if n.id == edge.source_id)
            assert source_node.name in ("method", "inner", "call_super_in_lambda", "call_super_in_comp") or source_node.name.startswith("<lambda:") or source_node.name.startswith("<listcomp:")


def test_super_multiple_inheritance():
    """Test super() with multiple inheritance picks first base with method."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
class Base1:
    def method(self):
        return "base1"

class Base2:
    def method(self):
        return "base2"

class Derived(Base1, Base2):
    def method(self):
        super().method()
""")

        parser = PythonASTParser(tmpdir)
        result = parser.parse_file(test_file)

        assert len(result.errors) == 0
        
        super_edges = [e for e in result.edges if e.edge_metadata.get("super") is True]
        assert len(super_edges) == 1
        
        # Should call Base1.method (first in MRO)
        target_node = next(n for n in result.nodes if n.id == super_edges[0].target_id)
        assert target_node.name == "method"
        # The target node should be Base1.method (check qualified name in metadata or node_map)
        # Find the Base1 class node and verify the method belongs to it
        base1_nodes = [n for n in result.nodes if n.type == "class" and n.name == "Base1"]
        assert len(base1_nodes) == 1
        base1 = base1_nodes[0]
        # The target method should be contained in Base1
        contains_edges = [e for e in result.edges if e.type == "contains" and e.source_id == base1.id]
        method_ids = [e.target_id for e in contains_edges if next((n for n in result.nodes if n.id == e.target_id), None).type == "function"]
        assert target_node.id in method_ids
