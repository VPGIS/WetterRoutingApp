# Installationsanleitung

Diese Anleitung beschreibt die Installation des Projekts mit Conda. Die Conda-Umgebung heisst `vprouting` und basiert auf Python 3.12.

## Voraussetzungen

Empfohlen wird eine Installation unter Linux oder Windows mit WSL2. Das Projekt verwendet mehrere GIS- und Geo-Bibliotheken, die unter Windows ohne Conda oft aufwendig zu installieren sind.

Voraussetzungen:

- Git
- Miniconda, Anaconda oder Mambaforge
- Internetverbindung fuer Paketinstallation, OpenStreetMap-/OSMnx-Abfragen und Kartendaten
- NetCDF-Wetterdaten fuer den Betrieb der Routing-API

Die wichtigsten GIS-Systemabhaengigkeiten werden ueber Conda installiert:

- `gdal`
- `proj`
- `geos`
- `libspatialindex`

## Miniconda / Conda

Falls Conda noch nicht installiert ist, wird Miniconda empfohlen:

```text
https://docs.conda.io/projects/miniconda/en/latest/
```

Nach der Installation sollte Conda im Terminal verfuegbar sein:

```bash
conda --version
```

Optional kann Conda aktualisiert werden:

```bash
conda update -n base -c defaults conda
```

## Repository klonen

```bash
git clone https://github.com/calgon854/VPRouting.git
cd VPRouting
```

## Conda-Umgebung erstellen

Die Umgebung wird aus der Datei `environment.yml` erstellt:

```bash
conda env create -f environment.yml
```

Dabei werden die GIS- und Scientific-Pakete ueber `conda-forge` installiert. Zusaetzliche Python-Abhaengigkeiten werden anschliessend ueber `pip` aus `requirements.txt` installiert.

## Umgebung aktivieren

```bash
conda activate vprouting
```

## Installation pruefen

Pruefen, ob Python korrekt aus der Conda-Umgebung verwendet wird:

```bash
python --version
```

Wichtige Pakete testen:

```bash
python -c "import numpy, pandas, scipy, xarray, netCDF4; print('Scientific packages OK')"
python -c "import osmnx, geopandas, rasterio; print('Geo packages OK')"
```

FastAPI-Backend starten:

```bash
uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
```

Danach kann die Swagger-Dokumentation im Browser geoeffnet werden:

```text
http://127.0.0.1:8000/docs
```

## Umgebung aktualisieren

Wenn `environment.yml` oder `requirements.txt` geaendert wurde, kann die bestehende Umgebung aktualisiert werden:

```bash
conda env update -f environment.yml --prune
```

Falls nur neue `pip`-Pakete in `requirements.txt` hinzugekommen sind:

```bash
pip install -r requirements.txt
```

## Umgebung entfernen

Falls die Umgebung neu erstellt oder geloescht werden soll:

```bash
conda deactivate
conda env remove -n vprouting
```

Anschliessend kann sie bei Bedarf erneut erstellt werden:

```bash
conda env create -f environment.yml
```
