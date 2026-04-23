from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageOut(BaseModel):
    message: str


class UserLogin(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    nickname: str
    full_name: str
    role: str
    is_active: bool
    available_house_ids: list[int] = Field(default_factory=list)
    default_house_id: int | None = None
    created_at: datetime


class UserUpdate(BaseModel):
    nickname: str = Field(default="", max_length=50)
    full_name: str = Field(default="", max_length=50)
    default_house_id: int | None = None
    password: str | None = Field(default=None, min_length=6, max_length=64)


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    sort_order: int = Field(default=0, ge=0)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime


class TagIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    is_active: bool
    created_at: datetime


class HouseIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    sort_order: int = Field(default=0, ge=0)


class HouseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime


class LocationIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    sort_order: int = Field(default=0, ge=0)
    house_id: int | None = None
    parent_id: int | None = None


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    sort_order: int
    house_id: int | None
    house_name: str | None = None
    path: str
    parent_id: int | None
    is_active: bool
    created_at: datetime


class ItemImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    url: str
    created_at: datetime


class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location_detail: str = Field(min_length=1, max_length=500)
    quantity: int = Field(default=1, ge=1)
    brand: str = ""
    category_id: int
    house_id: int
    room_id: int
    tag_ids: list[int] = []
    tag_names: list[str] = []


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    location_detail: str
    quantity: int
    brand: str
    category_id: int | None
    category_name: str | None = None
    room_id: int | None
    room_path: str | None = None
    house_id: int | None = None
    house_name: str | None = None
    tags: list[TagOut] = []
    images: list[ItemImageOut] = []
    owner_user_id: int
    owner_username: str
    owner_display_name: str
    created_at: datetime
    updated_at: datetime


class PaginatedItemsOut(BaseModel):
    items: list[ItemOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class AdminUserIn(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    full_name: str = Field(default="", max_length=50)
    password: str = Field(min_length=6, max_length=64)
    role: str = "user"
    is_active: bool = True
    available_house_ids: list[int] = Field(default_factory=list)
    default_house_id: int | None = None


class AdminUserUpdate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    full_name: str = Field(default="", max_length=50)
    role: str = "user"
    is_active: bool = True
    available_house_ids: list[int] = Field(default_factory=list)
    default_house_id: int | None = None
