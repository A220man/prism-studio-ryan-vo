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
async def test_graph_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert data["total_nodes"] == 0
    assert data["total_edges"] == 0