
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# Schritt 1: Aktuelle Wetterdaten vorbereiten
# TODO: Hier soll später ein Skript aufgerufen werden, das neue .nc-Dateien
#       herunterlädt, berechnet und unter backend/data/NC speichert.
#       Platzhalter, bis dieses Vorbereitungsskript fertig erstellt ist.
print("Schritt 1 übersprungen: Generierung aktueller .nc-Dateien ist noch nicht implementiert.")


# Schritt 2: Erstelle NC_for_Cellid, falls sie noch nicht existiert
subprocess.run(
    [sys.executable, 
     str(Path(__file__).resolve().parent / "reduce_nc_to_grid_geometry.py"), 
     str(PROJECT_ROOT / "backend" / "data" / "NC")],
    check=True
)

print("Schritt 3: Starte API-Server unter http://127.0.0.1:8000")
subprocess.run(
    [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.api:app",
        "--reload",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ],
    cwd=PROJECT_ROOT,
    check=True,
)

