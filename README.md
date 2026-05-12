# Wetter Routing App

Die **Wetter Routing App** ist ein Prototyp für wetterabhängiges Routing. Sie kombiniert OpenStreetMap-Daten mit Niederschlagsprognosen von MeteoSwiss, damit Routen nicht nur nach Distanz oder Reisezeit, sondern auch nach erwarteten Wetterbedingungen bewertet werden können.

Das Projekt entstand im Rahmen des Vertiefungsprofils Geoinformatik/Raumanalyse an der FHNW.

## Überblick

Die Anwendung besteht aus:

- einem browserbasierten Frontend zur Eingabe von Start, Ziel und Routingparametern
- einem FastAPI-Backend als Schnittstelle zwischen Frontend, Routinglogik und Daten
- Routingmodellen auf Basis von OSMnx-Graphen
- Wetterdaten im NetCDF-Format zur Bewertung von Niederschlag entlang der Route
- Startup-Skripten für Datenvorbereitung und Serverstart

Eine ausführlichere Einordnung des Projekts, der Fragestellung und der Datenquellen befindet sich in [About](docs/about.md). Der technische Aufbau ist in [Architektur](docs/architecture.md) beschrieben.

## Schnellstart

Nach dem Klonen des Repositorys wird zuerst die Conda-Umgebung erstellt und aktiviert. Danach kann der API-Server mit dem Startup-Skript gestartet werden.

```bash
conda env create -f environment.yml
conda activate vprouting
python scripts/startup/startup.py
```

Nach dem Start ist die Anwendung lokal erreichbar unter:

- [http://127.0.0.1:8000](http://127.0.0.1:8000)

Die automatisch erzeugte Swagger-Dokumentation befindet sich unter:

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Detaillierte Hinweise zur Einrichtung stehen in [Installation](docs/installation.md), der Startprozess ist in [Startup](docs/startup.md) beschrieben.

## Dokumentation

Die wichtigsten Detailinformationen befinden sich in den Markdown-Dateien im Ordner `docs/`:

| Datei                                | Inhalt                                                        |
| ------------------------------------ | ------------------------------------------------------------- |
| [About](docs/about.md)               | Projektkontext, Fragestellung, Datenquellen und Team          |
| [Installation](docs/installation.md) | Einrichtung der Conda-Umgebung und Abhängigkeiten             |
| [Startup](docs/startup.md)           | Startprozess, Wetterdatenprüfung, API-Server und Fetch-Daemon |
| [Architektur](docs/architecture.md)  | Technischer Aufbau und Zusammenspiel der Komponenten          |
| [Routing-Logik](docs/routing.md)     | Routingmodelle, Kostenfunktion und Ergebnisformat             |
| [Wetterdaten](docs/weather-data.md)  | Bezug, Aufbereitung und Zuordnung der MeteoSwiss-Daten        |

## API

Die wichtigste API-Route ist: `GET /WAPapi/v1/route`

Sie berechnet eine wetterabhängige Route zwischen Start- und Zielpunkt. Die vollständige API-Beschreibung wird beim laufenden Backend über Swagger bereitgestellt.

Weitere Informationen zum Ablauf einer Routinganfrage befinden sich in [Architektur](docs/architecture.md#aufbau-der-api-verarbeitung) und [Routing-Logik](docs/routing.md#einordnung-in-den-api-ablauf).

## GitHub Page

Die GitHub Page des Projekts ist hier erreichbar:

- [https://github.com/VPGIS/VPRouting](https://vpgis.github.io/VPRouting/)

Die Dokumentation des Projekts und die GitHub Page befindet sich in: `docs/index.md`
