from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional

# Схемы для пользователя
class UserBase(BaseModel):
    email: str
    username: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

# Схемы для ссылок
class LinkBase(BaseModel):
    original_url: HttpUrl

class LinkCreate(LinkBase):
    custom_alias: Optional[str] = None
    expires_at: Optional[datetime] = None

class LinkUpdate(BaseModel):
    original_url: Optional[HttpUrl] = None
    expires_at: Optional[datetime] = None

class LinkResponse(LinkBase):
    short_code: str
    custom_alias: Optional[str] = None
    clicks: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None
    owner_id: Optional[int] = None
    
    class Config:
        from_attributes = True

class LinkSearch(BaseModel):
    original_url: HttpUrl
    short_code: str
    created_at: datetime

class LinkStats(LinkResponse):
    """Статистика по ссылке (наследует все поля из LinkResponse)"""
    pass

class LinkUpdate(BaseModel):
    original_url: Optional[HttpUrl] = None
    expires_at: Optional[datetime] = None