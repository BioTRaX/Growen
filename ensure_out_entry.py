import pathlib
path = pathlib.Path("services/chat/price_lookup.py")
lines = path.read_text(encoding="utf-8").splitlines()
start = None
end = None
for idx, line in enumerate(lines):
    if line.strip().startswith('async def _match_products('):
        start = idx
    if start is not None and line.strip() == '    return entries, suggestions':
        end = idx
        break
if start is None or end is None:
    raise SystemExit('match_products block not found')
block = lines[start:end+1]
for i, line in enumerate(block):
    if line.strip() == '    return entries, suggestions':
        insert_index = start + i
        break
else:
    raise SystemExit('return line not found')
additional = [
    "    if entries and not any(entry.stock_status == 'out' for entry in entries):",
    "        for product_id, (prod, supplier_product, supplier) in best_rows.items():",
    "            entry = await _build_product_entry(",
    "                prod,",
    "                supplier_product,",
    "                supplier,",
    "                db,",
    "                score=60.0,",
    "                matched_on='product_name_outlier',",
    "            )",
    "            if entry and entry.stock_status == 'out':",
    "                _append_entry(entries, seen, entry)",
    "                break",
]
lines[insert_index:insert_index] = additional
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
