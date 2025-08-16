"""Modelos principales de la base de datos."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Float,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku_root: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    brand_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"))
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"))
    description_html: Mapped[Optional[str]] = mapped_column(Text)
    slug: Mapped[Optional[str]] = mapped_column(String(200))
    status: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    stock: Mapped[int] = mapped_column(Integer, default=0)

    variants: Mapped[list["Variant"]] = relationship(back_populates="product")
    images: Mapped[list["Image"]] = relationship(back_populates="product")
    tags: Mapped[list["Tag"]] = relationship(
        secondary="product_tags", back_populates="products"
    )


class Variant(Base):
    __tablename__ = "variants"
    __table_args__ = (UniqueConstraint("sku"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    sku: Mapped[str] = mapped_column(String(100))
    name: Mapped[Optional[str]] = mapped_column(String(100))
    value: Mapped[Optional[str]] = mapped_column(String(100))
    barcode: Mapped[Optional[str]] = mapped_column(String(100))
    price: Mapped[Optional[Numeric]] = mapped_column(Numeric(10, 2))
    promo_price: Mapped[Optional[Numeric]] = mapped_column(Numeric(10, 2))
    compare_at: Mapped[Optional[Numeric]] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    product: Mapped["Product"] = relationship(back_populates="variants")
    inventory: Mapped[Optional["Inventory"]] = relationship(back_populates="variant")


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(primary_key=True)
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("variants.id", ondelete="CASCADE"), unique=True
    )
    warehouse: Mapped[Optional[str]] = mapped_column(String(100))
    stock_qty: Mapped[int] = mapped_column(Integer, default=0)
    min_qty: Mapped[Optional[int]] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    variant: Mapped["Variant"] = relationship(back_populates="inventory")


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(String(500))
    sort_order: Mapped[Optional[int]] = mapped_column(Integer)

    product: Mapped["Product"] = relationship(back_populates="images")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"))


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    products: Mapped[list["Product"]] = relationship(
        secondary="product_tags", back_populates="tags"
    )


class ProductTag(Base):
    __tablename__ = "product_tags"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(50))
    params: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    result: Mapped[Optional[dict]] = mapped_column(JSON)


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    products: Mapped[list["SupplierProduct"]] = relationship(back_populates="supplier")


class SupplierFile(Base):
    __tablename__ = "supplier_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    filename: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64))
    rows: Mapped[int] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class SupplierProduct(Base):
    __tablename__ = "supplier_products"
    __table_args__ = (
        UniqueConstraint("supplier_id", "supplier_product_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    supplier_product_id: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(200))
    category_level_1: Mapped[Optional[str]] = mapped_column(String(100))
    category_level_2: Mapped[Optional[str]] = mapped_column(String(100))
    category_level_3: Mapped[Optional[str]] = mapped_column(String(100))
    min_purchase_qty: Mapped[Optional[Numeric]] = mapped_column(Numeric(10, 2))
    current_purchase_price: Mapped[Optional[Numeric]] = mapped_column(Numeric(10, 2))
    current_sale_price: Mapped[Optional[Numeric]] = mapped_column(Numeric(10, 2))
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    internal_product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"))
    internal_variant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("variants.id"))

    supplier: Mapped["Supplier"] = relationship(back_populates="products")
    price_history: Mapped[list["SupplierPriceHistory"]] = relationship(back_populates="supplier_product")
    equivalence: Mapped[Optional["ProductEquivalence"]] = relationship(
        back_populates="supplier_product", uselist=False
    )


class SupplierPriceHistory(Base):
    __tablename__ = "supplier_price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_product_fk: Mapped[int] = mapped_column(ForeignKey("supplier_products.id"))
    # `file_fk` solía ser obligatorio; se vuelve opcional para permitir
    # registrar cambios de precio sin asociarlos a un archivo concreto.
    file_fk: Mapped[Optional[int]] = mapped_column(
        ForeignKey("supplier_files.id"), nullable=True
    )
    as_of_date: Mapped[date]
    purchase_price: Mapped[Optional[Numeric]] = mapped_column(Numeric(10, 2))
    sale_price: Mapped[Optional[Numeric]] = mapped_column(Numeric(10, 2))
    delta_purchase_pct: Mapped[Optional[Numeric]] = mapped_column(Numeric(10, 2))
    delta_sale_pct: Mapped[Optional[Numeric]] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    supplier_product: Mapped["SupplierProduct"] = relationship(back_populates="price_history")


class CanonicalProduct(Base):
    __tablename__ = "canonical_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    ng_sku: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    brand: Mapped[Optional[str]] = mapped_column(String(100))
    specs_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    equivalences: Mapped[list["ProductEquivalence"]] = relationship(
        back_populates="canonical_product"
    )


class ProductEquivalence(Base):
    __tablename__ = "product_equivalences"
    __table_args__ = (
        UniqueConstraint("supplier_id", "supplier_product_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    supplier_product_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_products.id")
    )
    canonical_product_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_products.id")
    )
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    supplier: Mapped["Supplier"] = relationship()
    supplier_product: Mapped["SupplierProduct"] = relationship(
        back_populates="equivalence"
    )
    canonical_product: Mapped["CanonicalProduct"] = relationship(
        back_populates="equivalences"
    )


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    filename: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default="DRY_RUN")
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    rows: Mapped[list["ImportJobRow"]] = relationship(back_populates="job")


class ImportJobRow(Base):
    __tablename__ = "import_job_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id", ondelete="CASCADE"))
    row_index: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(String(200))
    row_json_normalized: Mapped[dict] = mapped_column(JSON)

    job: Mapped["ImportJob"] = relationship(back_populates="rows")
