from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


item_tags = Table(
    "item_tags",
    Base.metadata,
    Column("item_id", ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

user_accessible_houses = Table(
    "user_accessible_houses",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("house_id", ForeignKey("houses.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    nickname: Mapped[str] = mapped_column(String(50), default="")
    full_name: Mapped[str] = mapped_column(String(50), default="")
    role: Mapped[str] = mapped_column(String(20), default="user", index=True)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    default_house_id: Mapped[int | None] = mapped_column(ForeignKey("houses.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    categories: Mapped[list["Category"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    tags: Mapped[list["Tag"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    locations: Mapped[list["Location"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    items: Mapped[list["Item"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    logs: Mapped[list["OperationLog"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    accessible_houses: Mapped[list["House"]] = relationship(secondary=user_accessible_houses, back_populates="accessible_users")

    @property
    def available_house_ids(self) -> list[int]:
        return [house.id for house in self.accessible_houses]


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_category_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner: Mapped["User"] = relationship(back_populates="categories")
    items: Mapped[list["Item"]] = relationship(back_populates="category")


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_tag_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner: Mapped["User"] = relationship(back_populates="tags")
    items: Mapped[list["Item"]] = relationship(secondary=item_tags, back_populates="tags")


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("user_id", "name", "parent_id", name="uq_location_user_name_parent"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    house_id: Mapped[int | None] = mapped_column(ForeignKey("houses.id", ondelete="CASCADE"), nullable=True, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(80))
    path: Mapped[str] = mapped_column(String(255), index=True)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner: Mapped["User"] = relationship(back_populates="locations")
    parent: Mapped["Location | None"] = relationship(remote_side=[id], backref="children")
    items: Mapped[list["Item"]] = relationship(back_populates="location")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    location_detail: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    brand: Mapped[str] = mapped_column(String(120), default="")
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    voice_terms_dirty_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    voice_terms_last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    owner: Mapped["User"] = relationship(back_populates="items")
    category: Mapped["Category | None"] = relationship(back_populates="items")
    location: Mapped["Location | None"] = relationship(back_populates="items")
    images: Mapped[list["ItemImage"]] = relationship(back_populates="item", cascade="all, delete-orphan")
    tags: Mapped[list["Tag"]] = relationship(secondary=item_tags, back_populates="items")


class ItemImage(Base):
    __tablename__ = "item_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    item: Mapped["Item"] = relationship(back_populates="images")


class VoiceSearchTerm(Base):
    __tablename__ = "voice_search_terms"
    __table_args__ = (
        UniqueConstraint("user_id", "item_id", "term", "term_type", name="uq_voice_search_term_item_term"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    term: Mapped[str] = mapped_column(String(120), index=True)
    term_type: Mapped[str] = mapped_column(String(20), index=True)
    weight: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(100))
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner: Mapped["User"] = relationship(back_populates="logs")


class House(Base):
    __tablename__ = "houses"
    __table_args__ = (UniqueConstraint("name", name="uq_house_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    accessible_users: Mapped[list["User"]] = relationship(secondary=user_accessible_houses, back_populates="accessible_houses")
