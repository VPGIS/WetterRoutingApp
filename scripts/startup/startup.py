
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# Schritt 1: Start ICON CH1 data fetcher daemon
subprocess.Popen(
    [sys.executable, str(PROJECT_ROOT / "backend" / "fetch_icon.py")],
    cwd=PROJECT_ROOT
)


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

