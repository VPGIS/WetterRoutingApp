
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from utils_fetch import check_fetch_on_startup


print('Schritt 1: Stelle sicher, dass aktuelle Wetterdaten vorhanden sind')
check_fetch_on_startup()


print('Schritt 2: Erstelle NC_for_Cellid, falls sie noch nicht existiert')
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

