import pytest
from httpx import AsyncClient, ASGITransport
from app.main import create_app
from app.core.config import settings
from app.core.database import engine, async_session_maker


@pytest.fixture(scope="session", autouse=True)
def override_db_url():
    settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    # Recreate engine with in-memory DB
    from sqlalchemy.ext.asyncio import create_async_engine
    import app.core.database as db_module
    db_module.engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
    db_module.async_session_maker = db_module.async_session_maker.__class__(db_module.engine, class_=db_module.AsyncSession, expire_on_commit=False)
@pytest.fixture(scope="session")
def client():
    app = create_app()
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    yield client
    import asyncio
    asyncio.run(client.aclose())


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