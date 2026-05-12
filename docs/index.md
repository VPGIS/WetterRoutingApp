---
title: Wetter Routing App
---

# Dokumentation

<p align="center">
  <img src="assets/logo.jpg" alt="Logo der Wetter Routing App" width="180">
</p>

<p align="center">
  <strong>Tobias Schulthess und Ignaz Kuczynski</strong>
</p>

Die **Wetter Routing App** ist ein Prototyp für wetterabhängiges Routing. Sie kombiniert OpenStreetMap-Daten mit Niederschlagsprognosen von MeteoSwiss, damit Routen nicht nur nach Distanz oder Reisezeit, sondern auch nach erwarteten Wetterbedingungen bewertet werden können.

<div class="info-band">
Das Projekt entstand im Rahmen des Vertiefungsprofils Geoinformatik/Raumanalyse an der FHNW. Diese GitHub Page verwendet die bestehenden Markdown-Dateien aus dem Ordner <code>docs/</code> als Projektdokumentation.
</div>

## Einstieg

<div class="doc-grid">
  <a class="doc-card" href="about.html">
    <strong>About</strong>
    <span>Projektkontext, Fragestellung, Datenquellen und Team.</span>
  </a>
  <a class="doc-card" href="installation.html">
    <strong>Installation</strong>
    <span>Einrichtung der Conda-Umgebung und benötigte Abhängigkeiten.</span>
  </a>
  <a class="doc-card" href="startup.html">
    <strong>Server starten</strong>
    <span>Startprozess, Wetterdatenprüfung, API-Server und Fetch-Daemon.</span>
  </a>
  <a class="doc-card" href="architecture.html">
    <strong>Architektur</strong>
    <span>Technischer Aufbau und Zusammenspiel der Komponenten.</span>
  </a>
  <a class="doc-card" href="routing.html">
    <strong>Routing-Logik</strong>
    <span>Routingmodelle, Kostenfunktion und Ergebnisformat.</span>
  </a>
  <a class="doc-card" href="weather-data.html">
    <strong>Wetterdaten</strong>
    <span>Bezug, Aufbereitung und Zuordnung der MeteoSwiss-Daten.</span>
  </a>
</div>

## Projektaufbau

Die Anwendung besteht aus einem browserbasierten Frontend, einem FastAPI-Backend, Routingmodellen auf Basis von OSMnx-Graphen und Wetterdaten im NetCDF-Format. Die Route wird über eine API-Anfrage berechnet und im Browser dargestellt.

<div class="quick-links">
  <a href="architecture.html#aufbau-der-api-verarbeitung">API-Ablauf</a>
  <a href="routing.html#routingmodelle">Routingmodelle</a>
  <a href="weather-data.html#aufbereitung-der-netcdf-datei">Wetterdatenpipeline</a>
  <a href="startup.html#was-passiert-beim-start">Startprozess</a>
</div>


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

Detaillierte Hinweise zur Einrichtung stehen in [Installation](installation.html), der Startprozess ist in [Startup](startup.html) beschrieben.

## Repository
Das Repository ist unter folgendem Link aufrufbar:
[https://github.com/VPGIS/VPRouting](https://github.com/VPGIS/VPRouting)

## Projektteam

Die Wetter Routing App wurde von **Tobias Schulthess** und **Ignaz Kuczynski** im Rahmen des Vertiefungsprofils Geoinformatik/Raumanalyse an der FHNW umgesetzt.
