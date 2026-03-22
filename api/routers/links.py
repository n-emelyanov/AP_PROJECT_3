from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, update
from datetime import datetime, timezone
from typing import Optional, List
from datetime import datetime
import secrets
import string

from api.database import get_db
from api import models, schemas
from api.redis import cache_link, get_cached_link, delete_cached_link

router = APIRouter(tags=["Links"])

def generate_short_code(length: int = 6) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

@router.post("/shorten", response_model=schemas.LinkResponse)
async def create_short_link(
    link_data: schemas.LinkCreate,
    db: AsyncSession = Depends(get_db)  # AsyncSession
):
    """Создание короткой ссылки"""
    # Проверяем custom_alias если указан
    if link_data.custom_alias:
        query = select(models.Link).where(
            or_(
                models.Link.short_code == link_data.custom_alias,
                models.Link.custom_alias == link_data.custom_alias
            )
        )
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom alias already exists"
            )
        short_code = link_data.custom_alias
    else:
        # Генерируем уникальный код
        while True:
            short_code = generate_short_code()
            query = select(models.Link).where(models.Link.short_code == short_code)
            result = await db.execute(query)
            existing = result.scalar_one_or_none()
            if not existing:
                break
    
    # Создаем ссылку
    db_link = models.Link(
        original_url=str(link_data.original_url),
        short_code=short_code,
        custom_alias=link_data.custom_alias,
        expires_at=link_data.expires_at
    )
    
    db.add(db_link)
    await db.commit()
    await db.refresh(db_link)
    
    # Кэшируем
    await cache_link(short_code, str(link_data.original_url))
    
    return db_link

@router.get("/{short_code}")
async def redirect_to_url(
    short_code: str,
    db: AsyncSession = Depends(get_db)
):
    """Перенаправление на оригинальный URL"""
    # Проверяем кэш
    cached_url = await get_cached_link(short_code)
    if cached_url:
        # Асинхронно обновляем статистику
        stmt = update(models.Link).where(
            or_(
                models.Link.short_code == short_code,
                models.Link.custom_alias == short_code
            )
        ).values(
            clicks=models.Link.clicks + 1,
            last_accessed_at=datetime.now(timezone.utc)
        )
        await db.execute(stmt)
        await db.commit()
        return {"original_url": cached_url}
    
    # Ищем в БД
    query = select(models.Link).where(
        or_(
            models.Link.short_code == short_code,
            models.Link.custom_alias == short_code
        ),
        models.Link.is_active == True
    )
    result = await db.execute(query)
    link = result.scalar_one_or_none()
    
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )
    
    # Проверяем не истекла ли ссылка
    if link.expires_at and link.expires_at < datetime.now(timezone.utc):
        link.is_active = False
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Link has expired"
        )
    
    # Обновляем статистику
    link.clicks += 1
    link.last_accessed_at = datetime.now(timezone.utc)
    await db.commit()
    
    # Кэшируем
    await cache_link(short_code, link.original_url)
    
    return {"original_url": link.original_url}


@router.get("/{short_code}/stats", response_model=schemas.LinkStats)
async def get_link_stats(
    short_code: str,
    db: AsyncSession = Depends(get_db)
):
    """Получить статистику по ссылке"""
    # Ищем ссылку в БД
    query = select(models.Link).where(
        or_(
            models.Link.short_code == short_code,
            models.Link.custom_alias == short_code
        )
    )
    result = await db.execute(query)
    link = result.scalar_one_or_none()
    
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )
    
    return link


@router.delete("/{short_code}")
async def delete_link(
    short_code: str,
    db: AsyncSession = Depends(get_db)
):
    """Удаление короткой ссылки"""
    query = select(models.Link).where(
        or_(
            models.Link.short_code == short_code,
            models.Link.custom_alias == short_code
        )
    )
    result = await db.execute(query)
    link = result.scalar_one_or_none()
    
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )
    
    await db.delete(link)
    await db.commit()
    await delete_cached_link(short_code)
    
    return {"message": "Link deleted successfully"}

@router.put("/{short_code}", response_model=schemas.LinkResponse)
async def update_link(
    short_code: str,
    link_data: schemas.LinkUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновление оригинального URL"""
    query = select(models.Link).where(
        or_(
            models.Link.short_code == short_code,
            models.Link.custom_alias == short_code
        )
    )
    result = await db.execute(query)
    link = result.scalar_one_or_none()
    
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )
    
    if link_data.original_url:
        link.original_url = str(link_data.original_url)
    if link_data.expires_at:
        link.expires_at = link_data.expires_at
    
    await db.commit()
    await db.refresh(link)
    await cache_link(short_code, link.original_url)
    
    return link

@router.get("/search", response_model=List[schemas.LinkResponse])
async def search_links(
    original_url: str = Query(..., description="Оригинальный URL для поиска"),
    db: AsyncSession = Depends(get_db)
):
    """Поиск ссылок по оригинальному URL"""
    query = select(models.Link).where(
        models.Link.original_url.contains(original_url)
    )
    result = await db.execute(query)
    links = result.scalars().all()
    
    return links

@router.post("/cleanup")
async def cleanup_expired_links(
    db: AsyncSession = Depends(get_db)
):
    """Удаление истекших ссылок"""
    query = select(models.Link).where(
        models.Link.expires_at < datetime.now(timezone.utc),
        models.Link.is_active == True
    )
    result = await db.execute(query)
    expired_links = result.scalars().all()
    
    for link in expired_links:
        link.is_active = False
        await delete_cached_link(link.short_code)
    
    await db.commit()
    
    return {
        "message": f"Cleaned up {len(expired_links)} expired links"
    }