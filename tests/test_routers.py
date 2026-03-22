import pytest
from fastapi import status
from datetime import datetime, timedelta, timezone


# ==================== БАЗОВЫЕ ТЕСТЫ ====================

@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Тест корневого эндпоинта"""
    response = await client.get("/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["message"] == "Short Link App"
    assert data["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_health_check(client):
    """Тест эндпоинта здоровья"""
    response = await client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_404_not_found(client):
    """Тест несуществующего эндпоинта"""
    response = await client.get("/nonexistent")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ==================== ТЕСТЫ СОЗДАНИЯ ССЫЛОК ====================

@pytest.mark.asyncio
async def test_create_short_link(client):
    """Тест создания короткой ссылки"""
    response = await client.post("/links/shorten", json={
        "original_url": "https://google.com"
    })
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["original_url"] in ["https://google.com", "https://google.com/"]
    assert "short_code" in data
    assert len(data["short_code"]) == 6
    assert data["clicks"] == 0


@pytest.mark.asyncio
async def test_create_short_link_with_trailing_slash(client):
    """Тест создания ссылки с URL, содержащим слеш в конце"""
    response = await client.post("/links/shorten", json={
        "original_url": "https://google.com/"
    })
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["original_url"] == "https://google.com/"


@pytest.mark.asyncio
async def test_create_link_with_custom_alias(client):
    """Тест создания ссылки с кастомным алиасом"""
    response = await client.post("/links/shorten", json={
        "original_url": "https://google.com",
        "custom_alias": "google"
    })
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["short_code"] == "google"
    assert data["custom_alias"] == "google"


@pytest.mark.asyncio
async def test_create_link_with_expiration(client):
    """Тест создания ссылки с датой истечения"""
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    response = await client.post("/links/shorten", json={
        "original_url": "https://google.com",
        "expires_at": expires_at
    })
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["original_url"] in ["https://google.com", "https://google.com/"]
    assert data["expires_at"] is not None


@pytest.mark.asyncio
async def test_create_duplicate_alias(client):
    """Тест на дубликат алиаса"""
    await client.post("/links/shorten", json={
        "original_url": "https://google.com",
        "custom_alias": "duplicate"
    })
    
    response = await client.post("/links/shorten", json={
        "original_url": "https://yandex.ru",
        "custom_alias": "duplicate"
    })
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_link_with_invalid_url(client):
    """Тест создания ссылки с невалидным URL"""
    response = await client.post("/links/shorten", json={
        "original_url": "not-a-url"
    })
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_create_link_with_empty_url(client):
    """Тест создания ссылки с пустым URL"""
    response = await client.post("/links/shorten", json={
        "original_url": ""
    })
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ==================== ТЕСТЫ РЕДИРЕКТА ====================

@pytest.mark.asyncio
async def test_redirect_success(client, db_session, test_link):
    """Тест успешного редиректа"""
    await db_session.refresh(test_link)
    
    response = await client.get(f"/links/{test_link.short_code}", follow_redirects=False)
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["original_url"] == test_link.original_url


@pytest.mark.asyncio
async def test_redirect_increments_clicks(client, db_session, test_link):
    """Тест увеличения счетчика кликов при редиректе"""
    await db_session.refresh(test_link)
    clicks_before = test_link.clicks
    
    await client.get(f"/links/{test_link.short_code}", follow_redirects=False)
    
    await db_session.refresh(test_link)
    assert test_link.clicks == clicks_before + 1


@pytest.mark.asyncio
async def test_redirect_not_found(client):
    """Тест редиректа по несуществующей ссылке"""
    response = await client.get("/links/nonexistent123")
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Link not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_redirect_expired_link(client, db_session):
    """Тест редиректа на истекшую ссылку"""
    from api import models
    
    expired_link = models.Link(
        original_url="https://expired.com",
        short_code="expired",
        is_active=True,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    db_session.add(expired_link)
    await db_session.commit()
    
    response = await client.get("/links/expired")
    assert response.status_code == status.HTTP_410_GONE
    assert "Link has expired" in response.json()["detail"]


# ==================== ТЕСТЫ СТАТИСТИКИ ====================

@pytest.mark.asyncio
async def test_get_link_stats(client, db_session, test_link):
    """Тест получения статистики ссылки"""
    await db_session.refresh(test_link)
    
    for _ in range(3):
        await client.get(f"/links/{test_link.short_code}")
    
    await db_session.refresh(test_link)
    
    response = await client.get(f"/links/{test_link.short_code}/stats")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["clicks"] == 3
    assert data["short_code"] == test_link.short_code
    assert data["original_url"] in [test_link.original_url, f"{test_link.original_url}/"]
    if "is_active" in data:
        assert data["is_active"] is True


@pytest.mark.asyncio
async def test_get_stats_not_found(client):
    """Тест получения статистики несуществующей ссылки"""
    response = await client.get("/links/nonexistent123/stats")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_multiple_redirects_stats(client, db_session, test_link):
    """Тест статистики после множественных переходов"""
    await db_session.refresh(test_link)
    
    for _ in range(5):
        await client.get(f"/links/{test_link.short_code}")
    
    await db_session.refresh(test_link)
    
    response = await client.get(f"/links/{test_link.short_code}/stats")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["clicks"] == 5
    assert data["last_accessed_at"] is not None


# ==================== ТЕСТЫ УДАЛЕНИЯ ====================

@pytest.mark.asyncio
async def test_delete_link(client, db_session, test_link):
    """Тест удаления ссылки"""
    await db_session.refresh(test_link)
    
    delete_response = await client.delete(f"/links/{test_link.short_code}")
    assert delete_response.status_code == status.HTTP_200_OK
    assert delete_response.json()["message"] == "Link deleted successfully"
    
    get_response = await client.get(f"/links/{test_link.short_code}")
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_delete_link_not_found(client):
    """Тест удаления несуществующей ссылки"""
    response = await client.delete("/links/nonexistent123")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ==================== ТЕСТЫ ОБНОВЛЕНИЯ ====================

@pytest.mark.asyncio
async def test_update_link(client, db_session, test_link):
    """Тест обновления ссылки"""
    await db_session.refresh(test_link)
    
    new_url = "https://updated-example.com"
    response = await client.put(f"/links/{test_link.short_code}", json={
        "original_url": new_url
    })
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["original_url"] in [new_url, f"{new_url}/"]


@pytest.mark.asyncio
async def test_update_link_with_expiration(client, db_session, test_link):
    """Тест обновления ссылки с датой истечения"""
    await db_session.refresh(test_link)
    
    new_expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    response = await client.put(f"/links/{test_link.short_code}", json={
        "expires_at": new_expires_at
    })
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["expires_at"] is not None


@pytest.mark.asyncio
async def test_update_link_not_found(client):
    """Тест обновления несуществующей ссылки"""
    response = await client.put("/links/nonexistent123", json={
        "original_url": "https://example.com"
    })
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_update_link_with_same_url(client, db_session, test_link):
    """Тест обновления ссылки тем же URL"""
    await db_session.refresh(test_link)
    
    response = await client.put(f"/links/{test_link.short_code}", json={
        "original_url": test_link.original_url
    })
    assert response.status_code == status.HTTP_200_OK


# ==================== ТЕСТЫ ОЧИСТКИ ====================

@pytest.mark.asyncio
async def test_cleanup_expired_links(client, db_session):
    """Тест очистки истекших ссылок"""
    from api import models
    
    expired_link = models.Link(
        original_url="https://expired.com",
        short_code="expired_clean",
        is_active=True,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    db_session.add(expired_link)
    await db_session.commit()
    
    response = await client.post("/links/cleanup")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "Cleaned up" in data["message"]
    
    check_response = await client.get("/links/expired_clean")
    assert check_response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_410_GONE]
