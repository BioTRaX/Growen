"""Modelos de datos principales."""

import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .db import Base


class StatusEnum(str, enum.Enum):
    active = "active"
    draft = "draft"
    archived = "archived"


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    parent_id = Column(ForeignKey("categories.id"))

    parent = relationship("Category", remote_side=[id])
    products = relationship("Product", back_populates="category")

    __table_args__ = (Index("ix_categories_parent_id", "parent_id"),)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    sku_root = Column(String, unique=True)
    title = Column(String, nullable=False)
    brand = Column(String)
    category_id = Column(ForeignKey("categories.id"))
    description_html = Column(Text)
    slug = Column(String, nullable=False, unique=True)
    status = Column(Enum(StatusEnum), nullable=False, default=StatusEnum.active)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    category = relationship("Category", back_populates="products")
    variants = relationship(
        "Variant", back_populates="product", cascade="all, delete-orphan"
    )
    images = relationship(
        "Image", back_populates="product", cascade="all, delete-orphan"
    )
    tags = relationship("Tag", secondary="product_tags", back_populates="products")

    __table_args__ = (
        Index("ix_products_slug", "slug", unique=True),
        Index("ix_products_category_id", "category_id"),
    )


class Variant(Base):
    __tablename__ = "variants"

    id = Column(Integer, primary_key=True)
    product_id = Column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    sku = Column(String, nullable=False, unique=True)
    name = Column(String)
    value = Column(String)
    barcode = Column(String)
    price = Column(Numeric(12, 2), nullable=False)
    promo_price = Column(Numeric(12, 2))
    weight_kg = Column(Numeric(10, 3))
    length_cm = Column(Numeric(10, 2))
    width_cm = Column(Numeric(10, 2))
    height_cm = Column(Numeric(10, 2))
    status = Column(Enum(StatusEnum), nullable=False, default=StatusEnum.active)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    product = relationship("Product", back_populates="variants")
    inventory = relationship(
        "Inventory", back_populates="variant", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_variants_sku", "sku", unique=True),
        Index("ix_variants_product_id_status", "product_id", "status"),
    )


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True)
    variant_id = Column(ForeignKey("variants.id"), nullable=False)
    warehouse = Column(String, nullable=False, default="default")
    stock_qty = Column(Integer, nullable=False, default=0)

    variant = relationship("Variant", back_populates="inventory")

    __table_args__ = (
        UniqueConstraint(
            "variant_id", "warehouse", name="uq_inventory_variant_warehouse"
        ),
    )


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True)
    product_id = Column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    url = Column(String, nullable=False)
    alt = Column(String)
    sort_order = Column(Integer, default=0)

    product = relationship("Product", back_populates="images")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    products = relationship("Product", secondary="product_tags", back_populates="tags")


class ProductTag(Base):
    __tablename__ = "product_tags"

    product_id = Column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)

    __table_args__ = (UniqueConstraint("product_id", "tag_id", name="uq_product_tag"),)


class PriceList(Base):
    __tablename__ = "price_lists"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    prices = relationship(
        "VariantPrice", back_populates="price_list", cascade="all, delete-orphan"
    )


class VariantPrice(Base):
    __tablename__ = "variant_prices"

    variant_id = Column(ForeignKey("variants.id", ondelete="CASCADE"), primary_key=True)
    price_list_id = Column(
        ForeignKey("price_lists.id", ondelete="CASCADE"), primary_key=True
    )
    price = Column(Numeric(12, 2), nullable=False)

    variant = relationship("Variant")
    price_list = relationship("PriceList", back_populates="prices")

    __table_args__ = (
        UniqueConstraint("variant_id", "price_list_id", name="uq_variant_price"),
    )


class Conversation(Base):
    """Conversación de chat agrupada por sesión."""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    """Mensaje individual dentro de una conversación."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    meta = Column(JSON)

    conversation = relationship("Conversation", back_populates="messages")


class Job(Base):
    """Tareas en ejecución o completadas."""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    type = Column(String, nullable=False)
    params = Column(JSON, nullable=False, default={})
    status = Column(String, nullable=False, default="pending")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    result = Column(JSON)
