import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from src.core import config
print("%-24s %-14s %-6s %s" % ("PROVEEDOR","ESTADO","KEY","MODELO"))
print("-"*76)
for r in config.provider_report():
    print("%-24s %-14s %-6s %s" % (r["nombre"], r["estado"], r["tiene_key"], r["modelo"]))
print()
print("configurados:", config.configured_providers())
