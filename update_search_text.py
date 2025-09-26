import pathlib
path = pathlib.Path("services/chat/price_lookup.py")
text = path.read_text(encoding="utf-8")
old = "    entries: List[ProductEntry] = []\n    suggestions: List[str] = []\n\n    name_filters = [CanonicalProduct.name.ilike(f\"%{term}%\") for term in query.terms]\n"
new = "    entries: List[ProductEntry] = []\n    suggestions: List[str] = []\n    focus_text = " ".join(query.terms).strip().lower()\n    search_text = focus_text if focus_text else query.normalized.lower()\n\n    name_filters = [CanonicalProduct.name.ilike(f\"%{term}%\") for term in query.terms]\n"
if old not in text:
    raise SystemExit('preface block not found')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
