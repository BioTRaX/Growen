#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_migrations_fresh_postgres.py
# NG-HEADER: Ubicación: tests/test_migrations_fresh_postgres.py
# NG-HEADER: Descripción: Valida Alembic head desde una base PostgreSQL temporal vacía.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Prueba opt-in de la cadena completa de migraciones sobre PostgreSQL real."""

from __future__ import annotations

import os
import asyncio
from pathlib import Path
import subprocess
import sys
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db.sku_generator import generate_canonical_sku
from db.models import Product, Sale, SaleLine
from services.routers.sales import confirm_sale

from scripts.audit_schema import _safe_db_url, run_audit


ROOT = Path(__file__).resolve().parents[1]
DATABASE_PREFIX = "growen_migration_test_"
POSTGRES_URL_ENV = "MIGRATION_TEST_POSTGRES_URL"


async def _allocate_concurrent_skus(database_url: str, count: int = 12) -> list[str]:
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def allocate() -> str:
        async with sessions() as session:
            sku = await generate_canonical_sku(session, "Concurrente", "Prueba")
            await session.commit()
            return sku

    try:
        return await asyncio.gather(*(allocate() for _ in range(count)))
    finally:
        await engine.dispose()


async def _confirm_competing_sales(database_url: str) -> tuple[list[object], Decimal]:
    """Dos transacciones compiten por la última unidad; sólo una puede confirmar."""
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as setup:
            product = Product(title="Stock concurrente", sku_root=f"CON-{uuid4().hex[:8]}", stock=Decimal("1.00"))
            setup.add(product); await setup.flush()
            sales = [Sale(status="BORRADOR", sale_kind="MOSTRADOR") for _ in range(2)]
            setup.add_all(sales); await setup.flush()
            setup.add_all([
                SaleLine(sale_id=sale.id, product_id=product.id, qty=Decimal("1.00"), unit_price=Decimal("10.00"), line_discount=Decimal("0"))
                for sale in sales
            ])
            await setup.commit(); sale_ids = [sale.id for sale in sales]; product_id = product.id

        async def confirm(sale_id: int) -> object:
            async with sessions() as session:
                try:
                    return await confirm_sale(sale_id, session, SimpleNamespace(user_id=None, session_id=None), None)
                except Exception as exc:  # el perdedor debe recibir conflicto de stock
                    await session.rollback()
                    return exc

        results = await asyncio.gather(*(confirm(sale_id) for sale_id in sale_ids))
        async with sessions() as check:
            stock = Decimal(str((await check.get(Product, product_id)).stock))
        return results, stock
    finally:
        await engine.dispose()


def test_audit_schema_masks_database_password() -> None:
    password = "super-secret"
    safe = _safe_db_url(
        f"postgresql+psycopg://growen:{password}@localhost:5433/growen"
    )
    assert "super-secret" not in safe
    assert "***" in safe


def _drop_temporary_database(admin_engine, database_name: str) -> None:
    if not database_name.startswith(DATABASE_PREFIX):
        raise ValueError("Se rechazó eliminar una base fuera del prefijo temporal")

    with admin_engine.connect() as connection:
        connection.execute(
            text(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = :database_name
                  AND pid <> pg_backend_pid()
                """
            ),
            {"database_name": database_name},
        )
        connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))


@pytest.mark.postgres
@pytest.mark.integration
def test_alembic_upgrade_head_from_empty_postgres() -> None:
    """Crea una base temporal, aplica todo Alembic y valida objetos críticos."""

    raw_admin_url = os.getenv(POSTGRES_URL_ENV)
    if not raw_admin_url:
        pytest.skip(f"Definir {POSTGRES_URL_ENV} para ejecutar esta integración")

    admin_url = make_url(raw_admin_url)
    if not admin_url.drivername.startswith("postgresql"):
        pytest.fail(f"{POSTGRES_URL_ENV} debe apuntar a PostgreSQL")

    database_name = f"{DATABASE_PREFIX}{uuid4().hex[:12]}"
    target_url = admin_url.set(database=database_name)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    target_engine = None

    try:
        _drop_temporary_database(admin_engine, database_name)
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))

        target_engine = create_engine(target_url, isolation_level="AUTOCOMMIT")
        with target_engine.connect() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        target_engine.dispose()
        target_engine = None

        environment = os.environ.copy()
        environment["DB_URL"] = target_url.render_as_string(hide_password=False)
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", str(ROOT / "alembic.ini"), "upgrade", "head"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr

        target_engine = create_engine(target_url)
        schema = inspect(target_engine)
        tables = set(schema.get_table_names())
        assert {
            "alembic_version",
            "customers",
            "knowledge_sources",
            "meli_accounts",
            "meli_oauth_states",
            "meli_notifications",
            "meli_item_links",
            "meli_sync_jobs",
            "knowledge_chunks",
            "products",
            "sales",
            "canonical_batch_jobs",
            "canonical_batch_job_items",
            "stock_reservations",
            "customer_account_entries",
            "drive_sync_runs",
            "drive_sync_items",
            "scheduler_settings",
            "scheduler_runs",
            "knowledge_index_tasks",
            "catalog_generation_runs",
            "catalog_generation_events",
            "chat_message_feedback",
            "ai_prompt_versions",
            "ai_prompt_evaluations",
            "market_alerts",
            "market_update_jobs",
            "market_update_items",
            "market_update_source_results",
            "external_identities",
            "external_identity_link_requests",
            "telegram_updates",
            "chat_runs",
            "chat_tool_events",
            "chat_feedback_events",
            "canonical_knowledge_assets",
            "canonical_knowledge_locations",
            "canonical_knowledge_labels",
            "knowledge_capabilities",
            "canonical_knowledge_asset_capabilities",
            "canonical_knowledge_versions",
            "canonical_knowledge_claims",
            "canonical_knowledge_facts",
            "canonical_knowledge_events",
            "canonical_knowledge_jobs",
            "canonical_knowledge_market_profiles",
        } <= tables

        assert "market_sources" not in tables
        market_source_columns = {
            column["name"] for column in schema.get_columns("canonical_knowledge_market_profiles")
        }
        assert {
            "asset_id",
            "is_active",
            "validation_status",
            "ars_confirmed",
            "argentina_delivery_confirmed",
            "created_by_user_id",
        } <= market_source_columns
        assert {"product_id", "source_name", "url"}.isdisjoint(market_source_columns)
        assert {item["name"] for item in schema.get_indexes("market_update_items")} >= {
            "uq_market_update_items_active_product"
        }

        chat_session_columns = {column["name"] for column in schema.get_columns("chat_sessions")}
        assert {"channel", "assigned_user_id", "detected_intent", "sentiment", "classification_model", "problem_signals"} <= chat_session_columns
        assert {"external_identity_id", "subject_hmac", "conversation_key"} <= chat_session_columns

        knowledge_source_columns = {
            column["name"] for column in schema.get_columns("knowledge_sources")
        }
        assert {
            "role_scope",
            "channel_scope",
            "visibility",
            "content_version",
            "status",
            "indexed_at",
            "expires_at",
        } <= knowledge_source_columns
        assert "ix_knowledge_sources_status_expiry" in {
            item["name"] for item in schema.get_indexes("knowledge_sources")
        }

        product_columns = {column["name"]: column for column in schema.get_columns("products")}
        assert product_columns["stock"]["type"].precision == 14
        assert product_columns["stock"]["type"].scale == 2
        assert "subcategory_id" in product_columns

        category_columns = {column["name"]: column for column in schema.get_columns("categories")}
        batch_item_columns = {column["name"]: column for column in schema.get_columns("canonical_batch_job_items")}
        assert category_columns["kind"]["nullable"] is False
        assert "tag_names" in batch_item_columns
        assert {item["name"] for item in schema.get_indexes("categories")} >= {"ux_categories_kind_lower_name"}
        assert {item["name"] for item in schema.get_indexes("tags")} >= {"ux_tags_lower_name"}

        customer_indexes = schema.get_indexes("customers")
        document_indexes = [
            item
            for item in customer_indexes
            if item.get("column_names") == ["document_number"] and item.get("unique")
        ]
        assert len(document_indexes) == 1
        assert document_indexes[0]["name"] == "ux_customers_document_number"

        history_columns = {column["name"]: column for column in schema.get_columns("supplier_price_history")}
        assert history_columns["file_fk"]["nullable"] is True

        audit = run_audit(target_url.render_as_string(hide_password=False))
        assert audit.missing() == []

        concurrent_skus = asyncio.run(
            _allocate_concurrent_skus(target_url.render_as_string(hide_password=False))
        )
        assert len(concurrent_skus) == len(set(concurrent_skus)) == 12
        assert all(__import__("re").fullmatch(r"CON_[0-9]{4}_PRU", sku) for sku in concurrent_skus)

        confirm_results, final_stock = asyncio.run(
            _confirm_competing_sales(target_url.render_as_string(hide_password=False))
        )
        assert sum(isinstance(result, dict) for result in confirm_results) == 1
        assert final_stock == Decimal("0.00")

        with target_engine.connect() as connection:
            versions = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
            assert versions == ["20260905_meli_scopes_text"]
            assert connection.execute(text("SELECT data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='meli_accounts' AND column_name='scopes'")).scalar_one() == "text"

            market_item_columns = {column["name"] for column in schema.get_columns("market_update_items")}
            assert {
                "stage",
                "competitors_existing",
                "sources_discovered",
                "sources_confirmed",
                "sources_quarantined",
            } <= market_item_columns
            source_result_columns = {
                column["name"] for column in schema.get_columns("market_update_source_results")
            }
            assert "operation" in source_result_columns
    finally:
        if target_engine is not None:
            target_engine.dispose()
        _drop_temporary_database(admin_engine, database_name)
        admin_engine.dispose()
