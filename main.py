from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from api.database import engine, init_db 
from api.routers import links
import os



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекст жизненного цикла для событий запуска/остановки приложения
    """
    # Проверяем, запущены ли тесты
    is_testing = os.getenv("TESTING", "false").lower() == "true"
    
    print("Запуск приложения")
    
    # Инициализируем базу данных только если это не тесты
    if not is_testing:
        await init_db()
        print("База данных инициализирована")
    else:
        print("Тестовый режим: инициализация БД пропущена")
    
    yield  # Приложение работает здесь
    
    # События при остановке приложения
    if not is_testing:
        await engine.dispose()
        print("Соединение с базой данных закрыто")
    
    print("Приложение остановлено")


# Создаем FastAPI приложение с контекстом жизненного цикла
app = FastAPI(
    title="Short Link App",
    description="Сервис для сокращения ссылок",
    version="1.0.0",
    lifespan=lifespan  # Добавляем управление жизненным циклом
)


@app.get("/", tags=["Root"])
async def root():
    """
    Корневой эндпоинт - базовый GET запрос
    """
    return {
        "message": "Short Link App",
        "version": "1.0.0",
        "endpoints": {
            "create_short_link": {
                "method": "POST",
                "path": "/links/shorten",
                "description": "Созданип короткой ссылки"
            },
            "redirect": {
                "method": "GET",
                "path": "/links/{short_code}",
                "description": "Перенаправление на оригинальный URL"
            },
            "delete_link": {
                "method": "DELETE",
                "path": "/links/{short_code}",
                "description": "Удаление короткой ссылки"
            },
            "update_link": {
                "method": "PUT",
                "path": "/links/{short_code}",
                "description": "Обновление оригинального URL для короткой ссылки"
            },
            "get_info": {
                "method": "GET",
                "path": "/links/{short_code}/stats",
                "description": "Получить информацию по ссылке"
            },
            # TODO: передача кастомного alias
            "create_custom_link": {
                "method": "POST",
                "path": "/links/shorten",
                "description": "Создание ссылки с уникальным alias"
            },
            "search_by_original_url": {
                "method": "GET",
                "path": "/links/search?original_url={url}",
                "description": "Поиск ссылки по оригинальному URL"
            },
            # TODO: создается с параметром expires_at в формате даты с точностью до минуты
            "create_custom_link": {
                "method": "POST",
                "path": "/links/shorten",
                "description": "Создание ссылки с уникальным alias"
            },
            "health": {
                "method": "GET",
                "path": "/health",
                "description": "Проверка работоспособности сервиса"
            }
        },
        "database": {
            "type": "PostgreSQL (асинхронная)",
            "file": "url_db.db"
        }
    }


@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
async def health_check():
    """
    Эндпоинт проверки здоровья приложения
    """
    return {
        "status": "healthy",
        "service": "ml-prediction-service"
    }


# Регистрируем роутер для работы со ссылками
app.include_router(links.router, prefix="/links")

