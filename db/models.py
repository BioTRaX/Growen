# NG-HEADER: Nombre de archivo: models.py
# NG-HEADER: Ubicación: db/models.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Modelos principales de la base de datos."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Time,
    ForeignKey,
    Integer,
    Numeric,
    Float,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
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
    # Ruta relativa dentro de MEDIA_ROOT para poder mover el root sin reescribir DB
    path: Mapped[Optional[str]] = mapped_column(String(600), nullable=True)
    sort_order: Mapped[Optional[int]] = mapped_column(Integer)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    alt_text: Mapped[Optional[str]] = mapped_column(String(300))
    title_text: Mapped[Optional[str]] = mapped_column(String(300))
    mime: Mapped[Optional[str]] = mapped_column(String(100))
    bytes: Mapped[Optional[int]] = mapped_column(Integer)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    product: Mapped["Product"] = relationship(back_populates="images")


class ImageVersion(Base):
    __tablename__ = "image_versions"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('original','bg_removed','watermarked','thumb','card','full')",
            name="ck_image_versions_kind",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    path: Mapped[str] = mapped_column(String(700))
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    hash: Mapped[Optional[str]] = mapped_column(String(64))
    mime: Mapped[Optional[str]] = mapped_column(String(64))
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    source_url: Mapped[Optional[str]] = mapped_column(String(800))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class ImageReview(Base):
    __tablename__ = "image_reviews"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected')",
            name="ck_image_reviews_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class ImageJob(Base):
    __tablename__ = "image_jobs"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('off','on','window')",
            name="ck_image_jobs_mode",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    mode: Mapped[str] = mapped_column(String(16), default="off")
    window_start: Mapped[Optional[datetime]] = mapped_column(Time, nullable=True)
    window_end: Mapped[Optional[datetime]] = mapped_column(Time, nullable=True)
    retries: Mapped[int] = mapped_column(Integer, default=3)
    rate_rps: Mapped[Optional[float]] = mapped_column(Float, default=1.0)
    burst: Mapped[int] = mapped_column(Integer, default=3)
    log_retention_days: Mapped[int] = mapped_column(Integer, default=90)
    purge_ttl_days: Mapped[int] = mapped_column(Integer, default=30)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class ImageJobLog(Base):
    __tablename__ = "image_job_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_name: Mapped[str] = mapped_column(String(64))
    level: Mapped[str] = mapped_column(String(16), default="INFO")
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class ExternalMediaMap(Base):
    __tablename__ = "external_media_map"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(32))
    remote_media_id: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


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
    # Datos extendidos
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    contact_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
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
    # Campos extendidos (Sept 2025)
    original_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


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
    # ng_sku se genera post-inserción; es nullable a nivel DB
    ng_sku: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    brand: Mapped[Optional[str]] = mapped_column(String(100))
    # Precio de venta a nivel canónico
    sale_price: Mapped[Optional[Numeric]] = mapped_column(Numeric(12, 2), nullable=True)
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


class User(Base):
    """Usuario del sistema con roles y proveedor opcional."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    identifier: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    supplier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('cliente','proveedor','colaborador','admin')",
            name="ck_users_role",
        ),
    )

    supplier: Mapped[Optional["Supplier"]] = relationship()


class Session(Base):
    """Sesiones persistidas para autenticación mediante cookies."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(100), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    ip: Mapped[Optional[str]] = mapped_column(String(100))
    user_agent: Mapped[Optional[str]] = mapped_column(String(200))

    __table_args__ = (
        CheckConstraint(
            "role IN ('guest','cliente','proveedor','colaborador','admin')",
            name="ck_sessions_role",
        ),
    )

    user: Mapped[Optional["User"]] = relationship()


class UserPreference(Base):
    __tablename__ = "user_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "scope", name="ux_user_preferences_user_scope"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    scope: Mapped[str] = mapped_column(String(64))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 'canonical' o 'supplier'
    entity_type: Mapped[str] = mapped_column(String(16))
    entity_id: Mapped[int] = mapped_column(Integer)
    price_old: Mapped[Optional[Numeric]] = mapped_column(Numeric(12, 2))
    price_new: Mapped[Optional[Numeric]] = mapped_column(Numeric(12, 2))
    note: Mapped[Optional[str]] = mapped_column(Text)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    ip: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(32))
    table: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    # Nota: 'metadata' es un nombre reservado en SQLAlchemy; usamos 'meta' como atributo
    # pero conservamos el nombre de columna 'metadata' a nivel de base de datos.
    meta: Mapped[Optional[dict]] = mapped_column(JSON, name="metadata")
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    ip: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


# --- Compras (Purchases) ---

class Purchase(Base):
    __tablename__ = "purchases"
    __table_args__ = (
        UniqueConstraint("supplier_id", "remito_number", name="ux_purchases_supplier_remito"),
        CheckConstraint(
            "status IN ('BORRADOR','VALIDADA','CONFIRMADA','ANULADA')",
            name="ck_purchases_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    remito_number: Mapped[str] = mapped_column(String(64))
    remito_date: Mapped[date] = mapped_column(Date)
    depot_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="BORRADOR")
    global_discount: Mapped[Optional[Numeric]] = mapped_column(Numeric(6, 2), default=0)
    vat_rate: Mapped[Optional[Numeric]] = mapped_column(Numeric(5, 2), default=0)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    supplier: Mapped["Supplier"] = relationship()
    lines: Mapped[list["PurchaseLine"]] = relationship(back_populates="purchase")
    attachments: Mapped[list["PurchaseAttachment"]] = relationship(back_populates="purchase")


class PurchaseLine(Base):
    __tablename__ = "purchase_lines"
    __table_args__ = (
        CheckConstraint(
            "state IN ('OK','SIN_VINCULAR','PENDIENTE_CREACION')",
            name="ck_purchase_lines_state",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"))
    supplier_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("supplier_products.id"), nullable=True)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    supplier_sku: Mapped[Optional[str]] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(300))
    qty: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0)
    unit_cost: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0)
    line_discount: Mapped[Optional[Numeric]] = mapped_column(Numeric(6, 2), default=0)
    state: Mapped[str] = mapped_column(String(24), default="OK")
    note: Mapped[Optional[str]] = mapped_column(Text)

    purchase: Mapped["Purchase"] = relationship(back_populates="lines")
    supplier_item: Mapped[Optional["SupplierProduct"]] = relationship()
    product: Mapped[Optional["Product"]] = relationship()


class PurchaseAttachment(Base):
    __tablename__ = "purchase_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    mime: Mapped[Optional[str]] = mapped_column(String(100))
    size: Mapped[Optional[int]] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    purchase: Mapped["Purchase"] = relationship(back_populates="attachments")


class ImportLog(Base):
    __tablename__ = "import_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"))
    correlation_id: Mapped[str] = mapped_column(String(64))
    level: Mapped[str] = mapped_column(String(16), default="INFO")
    stage: Mapped[str] = mapped_column(String(64))
    event: Mapped[str] = mapped_column(String(64))
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


# --- Services registry (lightweight orchestration) ---

class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint(
            "status IN ('stopped','starting','running','degraded','failed')",
            name="ck_services_status",
        ),
        UniqueConstraint("name", name="ux_services_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="stopped")
    auto_start: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    uptime_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class ServiceLog(Base):
    __tablename__ = "service_logs"
    __table_args__ = (
        CheckConstraint(
            "action IN ('start','stop','status','health','panic')",
            name="ck_service_logs_action",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    service: Mapped[str] = mapped_column(String(64))
    correlation_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(16))
    host: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class StartupMetric(Base):
    __tablename__ = "startup_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    ttfb_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    app_ready_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)


# --- Clientes y Ventas ---

class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("email", name="ux_customers_email"),
        UniqueConstraint("doc_id", name="ux_customers_doc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    doc_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    sales: Mapped[list["Sale"]] = relationship(back_populates="customer")


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint(
            "status IN ('BORRADOR','CONFIRMADA','ANULADA')",
            name="ck_sales_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="CONFIRMADA")
    sale_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    total_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0)
    paid_total: Mapped[Optional[Numeric]] = mapped_column(Numeric(12, 2), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    customer: Mapped[Optional["Customer"]] = relationship(back_populates="sales")
    lines: Mapped[list["SaleLine"]] = relationship(back_populates="sale")
    payments: Mapped[list["SalePayment"]] = relationship(back_populates="sale")
    attachments: Mapped[list["SaleAttachment"]] = relationship(back_populates="sale")


class SaleLine(Base):
    __tablename__ = "sale_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0)
    unit_price: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0)
    line_discount: Mapped[Optional[Numeric]] = mapped_column(Numeric(6, 2), default=0)
    note: Mapped[Optional[str]] = mapped_column(Text)

    sale: Mapped["Sale"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship()


class SalePayment(Base):
    __tablename__ = "sale_payments"
    __table_args__ = (
        CheckConstraint(
            "method IN ('efectivo','debito','credito','transferencia','mercadopago','otro')",
            name="ck_sale_payments_method",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"))
    method: Mapped[str] = mapped_column(String(20), default="efectivo")
    amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0)
    reference: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    sale: Mapped["Sale"] = relationship(back_populates="payments")


class SaleAttachment(Base):
    __tablename__ = "sale_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    mime: Mapped[Optional[str]] = mapped_column(String(100))
    size: Mapped[Optional[int]] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    sale: Mapped["Sale"] = relationship(back_populates="attachments")
