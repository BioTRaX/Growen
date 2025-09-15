import importlib
mods=['playwright','tenacity']
for m in mods:
  try:
    importlib.import_module(m)
    print('OK',m)
  except Exception as e:
    print('FAIL',m,e)
