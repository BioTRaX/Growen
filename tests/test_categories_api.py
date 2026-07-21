#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_categories_api.py
# NG-HEADER: Ubicación: tests/test_categories_api.py
# NG-HEADER: Descripción: Pruebas de categorías y subcategorías planas, tipadas y creables.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pytest


@pytest.mark.asyncio
async def test_same_normalized_name_is_unique_per_kind(client) -> None:
    category = await client.post("/categories", json={"name": " Cultivo ", "kind": "category"})
    subcategory = await client.post("/categories", json={"name": "Cultivo", "kind": "subcategory"})
    assert category.status_code == 200, category.text
    assert subcategory.status_code == 200, subcategory.text
    assert category.json()["kind"] == "category"
    assert subcategory.json()["kind"] == "subcategory"
    assert category.json()["path"] == subcategory.json()["path"] == "Cultivo"

    duplicate = await client.post("/categories", json={"name": "cultivo", "kind": "category"})
    assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_list_and_search_filter_by_kind(client) -> None:
    await client.post("/categories", json={"name": "Riego", "kind": "category"})
    await client.post("/categories", json={"name": "Riego", "kind": "subcategory"})
    listed = await client.get("/categories", params={"kind": "subcategory"})
    searched = await client.get("/categories/search", params={"q": "rie", "kind": "category"})
    assert listed.status_code == searched.status_code == 200
    assert listed.json() and all(row["kind"] == "subcategory" for row in listed.json())
    assert searched.json() and all(row["kind"] == "category" for row in searched.json())


@pytest.mark.asyncio
async def test_legacy_parent_infers_subcategory_but_is_not_selection_rule(client) -> None:
    root = (await client.post("/categories", json={"name": "Legacy", "kind": "category"})).json()
    child = await client.post("/categories", json={"name": "Legacy Sub", "parent_id": root["id"]})
    assert child.status_code == 200
    assert child.json()["kind"] == "subcategory"
    assert child.json()["parent_id"] == root["id"]
