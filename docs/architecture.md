---
title: Architektur
---

# Architektur

Diese Datei beschreibt den technischen Aufbau der Wetter Routing App und das Zusammenspiel der wichtigsten Komponenten.

---

## Überblick

Die Wetter Routing App besteht aus einem browserbasierten Frontend, einem FastAPI-Backend und einer Routing-Logik, die OpenStreetMap-Daten mit NetCDF-Wetterdaten kombiniert.

Die Anwendung berechnet Routen auf Basis von Strassen- beziehungsweise Wegenetzen. Wetterinformationen können in die Bewertung der Route einbezogen werden, damit Strecken mit ungünstigen Wetterbedingungen höher gewichtet oder vermieden werden.

Kontext und Fragestellung stehen in [About](about.html). Details zu den Routingmodellen befinden sich in [Routing-Logik](routing.html), Details zur Wetterdatenpipeline in [Wetterdaten](weather-data.html).

---

## Projektstruktur

```text
VPRouting/
│
├── backend/                    # Backend-Ordner
│   ├── api.py                  # API-Einstiegspunkt
│   ├── utils_forecast.py       # Wetter-/Forecast-Logik
│   ├── utils_fetch.py          # Bezug ICON-Daten und Fetch-Daemon
│   ├── utils_graph.py          # Graph-Handling
│   ├── utils_nc_file.py        # NetCDF-Dateiauswahl
│   ├── utils_routingmodels.py  # Routingmodelle
│   └── data/
│       ├── graphs/             # gespeicherte Graphen mit Indexierung
│       │   ├── *.graphml
│       │   └── index.json
│       └── NC/                 # NetCDF-Wetterdaten
│           ├── *.nc
│           └── NC_for_Cellid.nc
│
├── frontend/                   # Frontend-Ordner
│   └── vp_routing.html
│
├── scripts/
│   └── startup/                # Start- und Vorbereitungsskripte
│       ├── reduce_nc_to_grid_geometry.py
│       └── startup.py
│
├── docs/                       # Dokumentation
│   ├── about.md
│   ├── installation.md
│   ├── startup.md
│   ├── architecture.md
│   ├── routing.md
│   └── weather-data.md
│
├── environment.yml             # Conda-Umgebung
├── requirements.txt            # zusätzliche pip-Abhängigkeiten
└── README.md                   # Projektübersicht
```

---

## Frontend

Die Hauptdatei des Frontends ist:

```text
frontend/vp_routing.html
```

Das Frontend wird lokal im Browser geöffnet beziehungsweise über das Backend ausgeliefert und kommuniziert über HTTP-Anfragen mit dem Backend.

Aufgaben des Frontends:

- Darstellung der Karte
- Auswahl von Start- und Zielpunkten
- Eingabe der Routingparameter
- Absenden der Routinganfrage an das Backend
- Darstellung der berechneten Route

---

## Backend

Der Einstiegspunkt der API ist:

```text
backend/api.py
```

Das Backend basiert auf FastAPI und stellt HTTP-Endpunkte für das Frontend bereit.

Aufgaben des Backends:

- Entgegennahme von Routinganfragen
- Validierung der Eingabedaten
- Aufruf der Routing-Logik
- Laden benötigter Wetter- und Kartendaten
- Rückgabe der berechneten Route an das Frontend

Das Backend wird lokal gestartet. Weitere Informationen dazu befinden sich in [Startup](startup.html).

---

## Aufbau der API-Verarbeitung

Über den Endpunkt `/WAPapi/v1/route` wird eine Routinganfrage vom Frontend an das Backend übergeben.

Die Anfrage enthält unter anderem:

- Startpunkt
- Zielpunkt
- Startzeit
- Geschwindigkeit
- Routingmodell
- Regenempfindlichkeit

Im Backend wird die Anfrage validiert und an die Routing-Logik weitergegeben. Dort werden die benötigten Graph- und Wetterdaten geladen, die Route berechnet und anschliessend als Antwort an das Frontend zurückgegeben.

Die lokale API-Dokumentation ist nach dem Start des Backends erreichbar unter:

```text
http://127.0.0.1:8000/docs
```

Die wichtigsten Prozessschritte:

1. **API-Vorbereitung:** `backend/api.py` validiert die Anfrage, verarbeitet Start- und Zielpunkt, konvertiert die Geschwindigkeit und öffnet die passende NetCDF-Wetterdatei.
2. **Graph-Vorbereitung:** Aus Start und Ziel wird eine Bounding Box berechnet. Anschliessend wird ein passender Graph aus dem Cache geladen oder über OSMnx neu erstellt.
3. **Node-Zuordnung:** Start- und Zielkoordinaten werden den nächstgelegenen Nodes im Graphen zugeordnet.
4. **Modellauswahl:** Abhängig vom gewählten Routingmodell wird entweder ein einfaches oder ein zeitabhängiges Routingverfahren verwendet.
5. **Rückgabe:** Nach der Routenberechnung wird die Route in ein GeoJSON-ähnliches Format umgewandelt und an das Frontend zurückgegeben.

<details>
<summary><strong>📊 Ablaufdiagramm anzeigen / ausblenden</strong></summary>

<img src="{{ '/assets/Ablaufdiagramm_Verarbeitung_API.svg' | relative_url }}" alt="Ablaufdiagramm Verarbeitung API">

</details>

Weitere Details zur Berechnung befinden sich in [Routing-Logik](routing.html#einordnung-in-den-api-ablauf).

---

## Routing-Logik

Die Routing-Logik befindet sich hauptsächlich in:

```text
backend/utils_routingmodels.py
```

Aktuell stehen zwei Routingmodelle zur Verfügung:

| Routingmodell | Beschreibung |
|---|---|
| `einfach` | Bewertet die Kanten einmalig mit dem Forecast zur Startzeit. |
| `advanced` | Bewertet Kanten zeitabhängig anhand der erwarteten Ankunftszeit. |

Das Routing verwendet vorbereitete oder neu erzeugte OSM-Graphen. Diese werden im Projekt gespeichert, damit sie bei späteren Anfragen wiederverwendet werden können.

Gespeicherte Graphen befinden sich unter:

```text
backend/data/graphs/
```

Weitere Details zu Algorithmen, Kostenberechnung und Ergebnisformat stehen in [Routing-Logik](routing.html).

---

## Wetterdaten

Die Wetterdaten werden als NetCDF-Dateien gespeichert und für die Bewertung der Route verwendet.

Erwarteter Pfad:

```text
backend/data/NC/
```

Beispiel:

```text
backend/data/NC/1712345678.nc
```

Für die Zuordnung von OSM-Kanten zum Wetterraster wird bevorzugt die Datei `NC_for_Cellid.nc` verwendet. Falls diese nicht existiert, wird sie beim Starten des Servers erzeugt. Siehe dazu [Startup: NC_for_Cellid vorbereiten](startup.html#schritt-2-nc_for_cellid-vorbereiten).

Weitere Details zur Erzeugung, Auswahl und Verwendung der Wetterdaten befinden sich in [Wetterdaten](weather-data.html).

---

## Weiterführende Dokumentation

- [About](about.html)
- [Installation](installation.html)
- [Startup](startup.html)
- [Routing-Logik](routing.html)
- [Wetterdaten](weather-data.html)
