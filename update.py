"""Pełne odświeżenie: terminarz + wyniki z Roster Athletics + przeliczenie klasyfikacji.
Ostatnia linia wyjścia to ZMIANA albo BEZ ZMIAN (czy strona wymaga ponownej publikacji)."""
import os, runpy, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sha = os.path.join(HERE, "data", "data.sha256")
before = open(sha).read() if os.path.exists(sha) else ""

from plan import update_plan
update_plan()
subprocess.run([sys.executable, os.path.join(HERE, "fetch.py")], check=True, cwd=HERE)
runpy.run_path(os.path.join(HERE, "build.py"), run_name="__main__")

after = open(sha).read()
print("ZMIANA" if after != before else "BEZ ZMIAN")
