import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from api.database import Base, get_db
from api.models import Link


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Создает сессию БД для теста с expire_on_commit=False"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # expire_on_commit=False предотвращает проблему MissingGreenlet
    async_session = async_sessionmaker(
        engine, 
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    """Тестовый клиент с моками Redis"""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Мокаем Redis функции
    with patch('api.redis.cache_link', new=AsyncMock()), \
         patch('api.redis.get_cached_link', new=AsyncMock(return_value=None)), \
         patch('api.redis.delete_cached_link', new=AsyncMock()):
        
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_link(db_session):
    """Тестовая ссылка"""
    link = Link(
        original_url="https://example.com",
        short_code="abc123",
        clicks=0,
        created_at=datetime.now(timezone.utc),
        is_active=True
    )
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(link)
    return link