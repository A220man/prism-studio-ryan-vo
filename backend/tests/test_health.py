import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.main import create_app
from app.core.config import settings
from app.models.graph import Base


@pytest.fixture(scope="function")
def client():
    # Create a fresh in-memory database for each test
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)

    import asyncio
    asyncio.run(_create_tables(test_engine))

    # Override the database module
    import app.core.database as db_module
    original_engine = db_module.engine
    original_session_maker = db_module.async_session_maker
    db_module.engine = test_engine
    db_module.async_session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    app = create_app()
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    yield client
    asyncio.run(client.aclose())

    # Restore original
    db_module.engine = original_engine
    db_module.async_session_maker = original_session_maker


async def _create_tables(eng):
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_readiness_endpoint(client: AsyncClient):
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_parse_endpoint(client: AsyncClient):
    """Test parsing a codebase via the API."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
def hello():
    print("Hello")

class Greeter:
    def greet(self, name: str) -> str:
        return f"Hello {name}"
""")
        response = await client.post("/api/v1/graph/parse", json={"path": tmpdir})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "job_id" in data
        assert "path" in data
        assert "message" in data
        assert "Parsed 1 files" in data["message"]
        assert "4 nodes" in data["message"]
        assert "3 edges" in data["message"]


@pytest.mark.asyncio
async def test_graph_query_after_parse(client: AsyncClient):
    """Test querying graph after parsing."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
def hello():
    print("Hello")

class Greeter:
    def greet(self, name: str) -> str:
        return f"Hello {name}"
""")
        await client.post("/api/v1/graph/parse", json={"path": tmpdir})

        # Query all nodes
        response = await client.get("/api/v1/graph")
        assert response.status_code == 200
        data = response.json()
        assert data["total_nodes"] == 4
        assert len(data["nodes"]) == 4
        assert len(data["edges"]) == 3

        # Filter by node type
        response = await client.get("/api/v1/graph?node_type=function")
        assert response.status_code == 200
        data = response.json()
        assert data["total_nodes"] == 2  # hello + greet
        assert all(n["type"] == "function" for n in data["nodes"])

        # Filter by file path
        response = await client.get("/api/v1/graph?file_path=test.py")
        assert response.status_code == 200
        data = response.json()
        assert data["total_nodes"] == 4

        # Pagination
        response = await client.get("/api/v1/graph?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) == 2
        assert data["total_nodes"] == 4

        response = await client.get("/api/v1/graph?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) == 2


@pytest.mark.asyncio
async def test_export_json(client: AsyncClient):
    """Test exporting graph as JSON."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
def hello():
    print("Hello")
""")
        await client.post("/api/v1/graph/parse", json={"path": tmpdir})

        response = await client.get("/api/v1/graph/export?format=json")
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "json"
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 2  # module + function
        assert len(data["edges"]) == 1  # contains


@pytest.mark.asyncio
async def test_export_graphml(client: AsyncClient):
    """Test exporting graph as GraphML."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
def hello():
    print("Hello")
""")
        await client.post("/api/v1/graph/parse", json={"path": tmpdir})

        response = await client.get("/api/v1/graph/export?format=graphml")
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "graphml"
        assert "data" in data
        assert "<graphml" in data["data"]
        assert "<node" in data["data"]
        assert "<edge" in data["data"]

@pytest.mark.asyncio
async def test_graph_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert data["total_nodes"] == 0
    assert data["total_edges"] == 0