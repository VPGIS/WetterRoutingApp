# Architektur

Diese Datei beschreibt den technischen Aufbau von VP Routing und das Zusammenspiel der wichtigsten Komponenten.

---

## Überblick

VP Routing besteht aus einem browserbasierten Frontend, einem FastAPI-Backend und einer Routing-Logik, die OpenStreetMap-Daten mit NetCDF-Wetterdaten kombiniert.

Die Anwendung berechnet Routen auf Basis von Straßen- bzw. Wegenetzen und kann zusätzliche Wetterinformationen in die Bewertung der Route einbeziehen.

## Projektstruktur <a id="backend-anker"></a>

```text
VPRouting/
│
├── backend/                    # Backend / FastAPI     <a id="backend-anker"></a>
│   ├── api.py                  # API-Einstiegspunkt
│   ├── utils_forecast.py       # Wetter-/Forecast-Logik
│   ├── utils_graph.py          # Graph-Handling
│   ├── utils_nc_file.py        # NetCDF-Dateien
│   ├── utils_routingmodels.py  # Routing-Modelle
│   └── data/
│       ├── graphs/             # gespeicherte Graphen mit Indexierung
│       │   ├── *.graphml
│       │   └── index.json
│       └── NC/                 # NetCDF-Wetterdaten
│           ├── *.nc
│           └── NC_for_Cellid.nc
│
├── frontend/                   # Browser-Frontend
│   └── vp_routing.html
│
├── scripts/
│   └── startup/                # Start-/Vorbereitungsskripte
│       ├── reduce_nc_to_grid_geometry.py
│       └── startup.py
│
├── docs/                       # Dokumentation
│   ├── installation.md
│   ├── startup.md
│   └── architecture.md
│
├── environment.yml             # Conda-Umgebung
├── requirements.txt            # zusätzliche pip-Abhängigkeiten
└── README.md                   # Projektübersicht
```

## Frontend

Das Frontend befindet sich im Ordner:

```text
frontend/
```

Die Hauptdatei ist:

```text
frontend/vp_routing.html
```

Das Frontend wird lokal im Browser geöffnet und kommuniziert mit dem Backend über HTTP-Anfragen.

Aufgaben des Frontends:

- Darstellung der Karte
- Auswahl von Start- und Zielpunkten
- Eingabe von Routingparametern
- Absenden der Routinganfrage an das Backend
- Darstellung der berechneten Route

---

## Backend

[backend-anker](backend-anker)
Das Backend befindet sich im Ordner:

```text
backend/
```

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

Das Backend wird lokal gestartet mit:

```bash
uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
```

---

## Routing-Logik

Die Routing-Logik ist für die Berechnung der Route verantwortlich.

Sie verwendet:

- OpenStreetMap-Daten
- Graphstrukturen
- Routingparameter
- optionale Wetterinformationen

Typische Aufgaben:

- Laden oder Erzeugen eines Routinggraphen
- Zuordnung von Start- und Zielpunkten zum Graphen
- Bewertung von Kanten
- Berechnung der optimalen Route
- Rückgabe der Route als Koordinaten oder GeoJSON-ähnliche Struktur

---

## Wetterdaten

Die Wetterdaten liegen als NetCDF-Dateien im Projektordner.

Erwarteter Pfad:

```text
backend/data/NC/
```

Beispiel:

```text
backend/data/NC/1712345678.nc
```

Für die Zuordnung von OSM-Kanten zum Wetterraster wird bevorzugt folgende Datei verwendet:

```text
backend/data/NC/NC_for_Cellid.nc
```

Aufgaben der Wetterdatenintegration:

- Laden der NetCDF-Dateien
- Zuordnung von Koordinaten oder Kanten zu Wetterzellen
- Bereitstellung wetterbezogener Werte für die Routingbewertung
- Einfluss auf die Gewichtung einzelner Routenabschnitte

---

## Datenfluss

Der typische Ablauf einer Routinganfrage:

1. Nutzer wählt Start- und Zielpunkt im Frontend.
2. Das Frontend sendet eine Anfrage an das FastAPI-Backend.
3. Das Backend validiert die Anfrage.
4. Die Routing-Logik lädt benötigte Karten- und Wetterdaten.
5. Start- und Zielpunkt werden dem OSM-Graphen zugeordnet.
6. Die Kanten des Graphen werden bewertet.
7. Die optimale Route wird berechnet.
8. Das Backend gibt die Route an das Frontend zurück.
9. Das Frontend stellt die Route auf der Karte dar.

---

---

## Schnittstellen

Die wichtigste Schnittstelle zwischen Frontend und Backend ist die FastAPI-API.

Lokale API-Adresse:

```text
http://127.0.0.1:8000
```

Swagger-Dokumentation:

```text
http://127.0.0.1:8000/docs
```

OpenAPI-Spezifikation:

```text
http://127.0.0.1:8000/openapi.json
```

---

## Laufzeitverhalten

Zur Laufzeit müssen folgende Komponenten verfügbar sein:

- aktive Conda-Umgebung
- gestartetes FastAPI-Backend
- vorhandene NetCDF-Wetterdaten
- Internetverbindung für OSM-/OSMnx-Abfragen, sofern Daten nicht gecacht sind
- lokal geöffnetes Frontend im Browser

---

## Architekturentscheidungen

Wichtige Entscheidungen im Projekt:

- FastAPI wird als Backend-Framework verwendet.
- Das Frontend ist zunächst als lokale HTML-Datei umgesetzt.
- Conda wird für die Installation von GIS- und Scientific-Abhängigkeiten genutzt.
- NetCDF wird als Format für Wetterdaten verwendet.
- OpenStreetMap dient als Grundlage für Routingdaten.

---

## Abgrenzung

Diese Datei beschreibt die Architektur auf hoher Ebene.

Weitere Details befinden sich in:

- `docs/installation.md`
- `docs/quickstart.md`
- `docs/weather-data.md`
- `docs/routing.md`
- `docs/api.md`
