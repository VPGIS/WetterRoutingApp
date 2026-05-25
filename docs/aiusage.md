---
title: AI Nutzung
---

# AI Nutzung

Diese Seite beschreibt, wie und wo künstliche Intelligenz im Projekt eingesetzt wurde: zur Erschliessung von Themenbereichen, beim Debugging, beim Prototyping und bei der Lösung von Architekturproblemen.

---

## Einstieg in die Wetterdaten

Zu Beginn des Projekts war der Umgang mit Wetterdaten und den zugehörigen Formaten weitgehend unbekannt. AI half dabei, einen schnellen Überblick über verfügbare Datenquellen zu gewinnen: Was bietet MeteoSwiss an, welche Formate werden verwendet, was sind die Unterschiede zwischen GRIB2, NetCDF und ICON-Gittern?

Nach allgemeinem Recherchieren konnten Vor- und Nachteile verschiedener Ansätze gezielt nachgefragt werden, etwa der Vergleich von ICON-CH1-EPS mit alternativen Quellen wie Copernicus-Satellitendaten. Entscheidend war dabei das Verifizieren, ob vorgeschlagene Ansätze überhaupt umsetzbar und zielführend waren, bevor Zeit in die Implementierung investiert wurde.

---

## Experimentelle Phase mit Notebooks

Als Ausgangspunkt für die Wetterdatenverarbeitung wurden Jupyter Notebooks aus dem offiziellen MeteoSwiss-Repository [meteodata-lab](https://github.com/MeteoSwiss/meteodata-lab) erkundet, darunter Beispiele wie `07_where_will_it_rain_next_24h`. Die eigenen Explorations-Notebooks sind im Ordner `_apriori/` abgelegt.

AI wurde dabei gezielt eingesetzt, um die behandelten Beispiele detaillierter zu erklären und mit relevanten Code-Snippets für das Weitertesten zu erweitern. So konnte schnell ein Verständnis für die Datenstruktur (Ensemble-Member, Lead-Time-Dimensionen, unstrukturiertes ICON-Gitter) aufgebaut werden.

Nach dieser Explorationsphase liessen sich die Erkenntnisse rasch in direkte `.py`-Skripte überführen.

---

## Architekturproblem: meteodata-lab und ARM64

Das grösste architekturelle Problem entstand beim Deployment auf den Raspberry Pi. Es wurde zunächst angenommen, dass `meteodata-lab` auf dem Pi lauffähig sei, weil weder Windows noch WSL-Ubuntu grössere Schwierigkeiten zeigten. Auf dem Pi mit ARM64-Architektur fehlten jedoch die nötigen Binaries für `meteodata-lab` und seine Abhängigkeiten (`earthkit`, `rasterio`).

AI half dabei, einen alternativen Ansatz zu entwickeln: eine direkte Pipeline über den MeteoSwiss STAC-Katalog mit `eccodes` für die GRIB2-Dekodierung und `scipy` für das Regridding. Diese Kombination ist ARM64-kompatibel und bildet heute die Grundlage von `backend/utils_fetch.py`. Mehr dazu steht in [Architektur](architecture.html).

> Das Paket `meteodata-lab` (offizieller MeteoSwiss-Client) hat kein ARM64-Package. Es wurde durch eine direkte STAC/eccodes-Implementierung ersetzt.

---

## Agentic AI im Projektalltag

Im Verlauf des Projekts wurde GitHub Copilot mit agentem Modus und Claude Sonnet 4.6 als Modell intensiv genutzt. Die direkte Darstellung des Reasonings war dabei besonders hilfreich: Sie ermöglichte nachzuvollziehen, ob der eigene Prompt präzise genug war, wie plausibel die Fehlersuche des Modells war und wie realistisch der vorgeschlagene Lösungsansatz einzuschätzen ist.

Kombiniert mit dem vollständigen Projektkontext, den man dem Modell mitgeben konnte, wurde Agentic Usage zu einem starken Werkzeug für komplexe Aufgaben. Bei grossen Anpassungen wurde häufig zuerst eine Reihe von Fragen gestellt, um ein genaues Konzept und einen konkreten Ablauf zu planen. Erst danach wurde der Agentic Mode für die Umsetzung verwendet.

Typische Einsatzgebiete:

| Bereich | Beschreibung |
| --- | --- |
| Themenerschliessung | Überblick über Wetterdatenformate, ICON-Modell, Ensemble-Forecasts |
| Debugging | Eingrenzen von Fehlern in der GRIB2-Pipeline, Graphverarbeitung, API-Antworten |
| Prototyping | Schnelle Umsetzung von Ideen in lauffähigen Code, z. B. Regridding, Renderer |
| Architektur | Erarbeitung des STAC-Ansatzes als Ersatz für meteodata-lab auf ARM64 |
| Dokumentation | Strukturierung und Formulierung dieser Dokumentation |

---

## Verwendete Modelle

| Modell | Anbieter |
| --- | --- |
| Claude Sonnet 4.6 | Anthropic (via GitHub Copilot) |
| Gemini 3.1 | Google |
| ChatGPT 5.5 | OpenAI |
