import redis.asyncio as redis
import os
from typing import Optional

# Получаем настройки из переменных окружения
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Создаем асинхронный клиент Redis
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
    socket_connect_timeout=5
)

async def cache_link(short_code: str, original_url: str, ttl: int = 3600):
    """Кэшируем ссылку на 1 час"""
    try:
        await redis_client.setex(f"link:{short_code}", ttl, original_url)
    except Exception as e:
        print(f"Redis cache error: {e}")

async def get_cached_link(short_code: str) -> Optional[str]:
    """Получаем ссылку из кэша"""
    try:
        return await redis_client.get(f"link:{short_code}")
    except Exception as e:
        print(f"Redis get error: {e}")
        return None

async def delete_cached_link(short_code: str):
    """Удаляем ссылку из кэша"""
    try:
        await redis_client.delete(f"link:{short_code}")
    except Exception as e:
        print(f"Redis delete error: {e}")

async def ping_redis() -> bool:
    """Проверка подключения к Redis"""
    try:
        return await redis_client.ping()
    except:
        return False