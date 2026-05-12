---
title: Wetter Routing App
---

# Wetter Routing App

Die **Wetter Routing App** ist ein Prototyp für wetterabhängiges Routing. Sie kombiniert OpenStreetMap-Daten mit Niederschlagsprognosen von MeteoSwiss, damit Routen nicht nur nach Distanz oder Reisezeit, sondern auch nach erwarteten Wetterbedingungen bewertet werden können.

Das Projekt entstand im Rahmen des Vertiefungsprofils Geoinformatik/Raumanalyse an der FHNW.

## Dokumentation

Diese GitHub Page verwendet die Markdown-Dateien aus dem Ordner `docs/` als Projektdokumentation.

| Seite | Inhalt |
|---|---|
| [About](about.md) | Projektkontext, Fragestellung, Datenquellen und Team |
| [Installation](installation.md) | Einrichtung der Conda-Umgebung und Abhängigkeiten |
| [Server starten](startup.md) | Startprozess, Wetterdatenprüfung, API-Server und Fetch-Daemon |
| [Architektur](architecture.md) | Technischer Aufbau und Zusammenspiel der Komponenten |
| [Routing-Logik](routing.md) | Routingmodelle, Kostenfunktion und Ergebnisformat |
| [Wetterdaten](weather-data.md) | Bezug, Aufbereitung und Zuordnung der MeteoSwiss-Daten |

## Projektaufbau

Die Anwendung besteht aus:

- einem browserbasierten Frontend zur Eingabe von Start, Ziel und Routingparametern
- einem FastAPI-Backend als Schnittstelle zwischen Frontend, Routinglogik und Daten
- Routingmodellen auf Basis von OSMnx-Graphen
- Wetterdaten im NetCDF-Format zur Bewertung von Niederschlag entlang der Route
- Startup-Skripten für Datenvorbereitung und Serverstart

## Schnellstart

```bash
conda env create -f environment.yml
conda activate vprouting
python scripts/startup/startup.py
```

Nach dem Start ist die Anwendung lokal erreichbar unter:

```text
http://127.0.0.1:8000
```

Die automatisch erzeugte Swagger-Dokumentation befindet sich unter:

```text
http://127.0.0.1:8000/docs
```

## Repository

Das Projekt wird auf GitHub verwaltet:

```text
https://github.com/calgon854/VPRouting
```
