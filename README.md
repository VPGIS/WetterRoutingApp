# VP Routing

README mit Installationsanweisungen, Systemanforderungen sowie Verweisen auf die API-Dokumentation und GitHub Page.

## Systemanforderungen

- Betriebssystem: Linux oder Windows mit WSL wird empfohlen
- Python: Version 3.12 oder kompatibel
- Paketmanager: `pip`
- Internetverbindung fuer OpenStreetMap-/OSMnx-Abfragen und Kartendaten
- NetCDF-Wetterdaten im Projektordner
- Empfohlene Systempakete unter Ubuntu/WSL:

```bash
sudo apt update
sudo apt install gdal-bin libgdal-dev libproj-dev proj-bin libspatialindex-dev libgeos-dev
```

## Installation

Repository klonen:

```bash
git clone https://github.com/calgon854/VPRouting.git
cd VPRouting
```

Virtuelle Python-Umgebung erstellen und aktivieren:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Abhaengigkeiten installieren:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Wetterdaten

Das Backend erwartet die NetCDF-Dateien im folgenden Ordner:

```text
backend/data/NC/
```

Die Routing-Dateien sollten als Unix-Timestamp benannt sein, zum Beispiel:

```text
backend/data/NC/1712345678.nc
```

Fuer die Zuordnung der OSM-Kanten zum Wetterraster wird bevorzugt diese Datei verwendet:

```text
backend/data/NC/NC_for_Cellid.nc
```

## Backend starten

```bash
uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
```

Die API ist danach lokal erreichbar unter:

```text
http://127.0.0.1:8000
```

## Frontend starten

Das Frontend kann lokal im Browser geoeffnet werden:

```text
frontend/vp_routing.html
```

Das Backend muss laufen, damit Routen berechnet werden koennen.

## API-Dokumentation

Die Swagger-Dokumentation wird automatisch von FastAPI bereitgestellt:

```text
http://127.0.0.1:8000/docs
```

Die OpenAPI-Spezifikation ist unter folgender Adresse verfuegbar:

```text
http://127.0.0.1:8000/openapi.json
```

## GitHub Page

Die GitHub Page des Projekts ist hier erreichbar:

```text
https://calgon854.github.io/VPRouting/
```
