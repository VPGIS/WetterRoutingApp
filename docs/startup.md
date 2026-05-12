---
title: Server starten
---

# Server starten

Der API-Server kann über das Startup-Skript gestartet werden. Das Skript führt zuerst die nötige Vorbereitung aus und startet danach das FastAPI-Backend.

> Hinweis: Das Aufstarten kann länger dauern, wenn zuerst aktuelle Wetterdaten bezogen werden müssen.

## Voraussetzungen

Die Conda-Umgebung muss aktiviert sein. Siehe dazu [Installation](installation.html).

```bash
conda activate vprouting
```

Ausserdem muss der Befehl aus dem Projekt-Root ausgeführt werden:

```bash
cd VPRouting
```

## Startbefehl

```bash
python scripts/startup/startup.py
```

Danach läuft der API-Server unter:

```text
http://127.0.0.1:8000
```

Die lokale Swagger-Dokumentation ist erreichbar unter:

```text
http://127.0.0.1:8000/docs
```

---

## Was passiert beim Start?

Das Skript `scripts/startup/startup.py` führt einen mehrstufigen Startprozess aus.

Der Startup-Prozess umfasst aktuell folgende Schritte:

1. aktuelle Wetterdaten prüfen und bei Bedarf beziehen
2. `NC_for_Cellid.nc` vorbereiten
3. API-Server starten
4. Fetch-Daemon im API-Prozess starten

---

### Schritt 1: Aktuelle Wetterdaten prüfen

Das Startup-Skript ruft zu Beginn `check_fetch_on_startup()` aus `backend/utils_fetch.py` auf.

Dabei wird geprüft, ob im Ordner `backend/data/NC/` bereits eine aktuelle NetCDF-Datei vorhanden ist.

Falls keine aktuelle Datei vorhanden ist, werden neue ICON-CH1-Wetterdaten von MeteoSwiss bezogen, verarbeitet und als timestamp-basierte `.nc`-Datei gespeichert.

Ziel dieses Schritts:

- aktuelle Wetterdaten verfügbar machen
- neue NetCDF-Dateien in `backend/data/NC/` speichern
- sicherstellen, dass die API beim Routing eine passende Wetterdatei findet

Weitere Details zur Wetterdatenaufbereitung befinden sich in [Wetterdaten](weather-data.html).

---

### Schritt 2: NC_for_Cellid vorbereiten

Das Vorbereitungsskript prüft, ob folgende Datei existiert:

```text
backend/data/NC/NC_for_Cellid.nc
```

Falls diese Datei noch nicht existiert, wird die erste vorhandene `.nc`-Datei aus `backend/data/NC/` gelesen. Daraus werden nur die Variablen `lat` und `lon` extrahiert und als `NC_for_Cellid.nc` gespeichert.

Diese reduzierte Datei wird später im Backend verwendet, um Kanten aus dem OSM-Graphen einer Wetterrasterzelle zuzuordnen.

Das zuständige Skript ist:

```text
scripts/startup/reduce_nc_to_grid_geometry.py
```

Weitere Details zur Zellzuordnung stehen in [Wetterdaten: Zuordnung von Strassenkanten zu Wetterzellen](weather-data.html#zuordnung-von-strassenkanten-zu-wetterzellen).

---

### Schritt 3: API-Server starten

Anschliessend startet das Startup-Skript den API-Server mit:

```bash
python -m uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
```

Das Frontend wird danach direkt über die API ausgeliefert:

```text
http://127.0.0.1:8000
```

---

### Schritt 4: Fetch-Daemon im API-Prozess

Beim Start von `backend/api.py` wird über den FastAPI-Lifespan zusätzlich ein Hintergrundprozess gestartet:

```text
backend/utils_fetch.py
```

Dieser Fetch-Daemon bleibt während der Laufzeit des Servers aktiv. Er prüft beim Start nochmals, ob die Wetterdaten aktuell sind, und lädt danach gemäss Zeitplan neue Daten nach.

Geplante Fetch-Zeiten:

```text
00:05, 03:05, 06:05, 09:05, 12:05, 15:05, 18:05, 21:05 UTC
```

Beim Stoppen des API-Servers wird der Hintergrundprozess beendet.

---

## Server stoppen

Der Server läuft im Terminal weiter.

Zum Stoppen:

```text
Ctrl + C
```
