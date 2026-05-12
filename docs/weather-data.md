---
title: Wetterdaten
---

# Wetterdaten

Diese Datei beschreibt die Verwendung, Erzeugung und Zuordnung der Wetterdaten im Projekt **Wetter Routing App**.

## Überblick

Die Wetter Routing App verwendet Wetterdaten im NetCDF-Format, um Routen wetterabhängig bewerten zu können. Die Daten stammen aus dem Open-Data-Angebot von MeteoSwiss und werden im Projekt insbesondere zur Bewertung von Niederschlag entlang einer Route genutzt.

Die Wetterdaten ermöglichen es, betroffene Kanten im Routinggraphen zu erkennen und abhängig von der Niederschlagsmenge höher zu gewichten. Dadurch können Routen berechnet werden, die wetterbezogene Einflüsse berücksichtigen.

Der Zusammenhang mit der API-Verarbeitung ist in [Architektur](architecture.html#aufbau-der-api-verarbeitung) beschrieben. Die Verwendung der Wetterwerte in der Kostenfunktion steht in [Routing-Logik](routing.html#kantenbewertung).

## NetCDF-Ablagestruktur

Die Routing-API erwartet die NetCDF-Dateien im folgenden Ordner:

```text
backend/data/NC/
```

### Wetterdaten

Die Forecast-Dateien enthalten einen Unix-Timestamp im Dateinamen, zum Beispiel:

```text
1712345678.nc
```

Der Timestamp dient zur Zuordnung der Startzeit und zur Prüfung der zeitlichen Gültigkeit der Datei.

### Hilfsdatei für Wetterzellen

Für die Zuordnung von OSM-Kanten zum Wetterraster wird bevorzugt folgende Datei verwendet:

```text
NC_for_Cellid.nc
```

Diese Datei enthält eine reduzierte Rastergeometrie und wird beim Erstellen neuer Graphen verwendet. Falls sie beim Start noch nicht existiert, wird sie gemäss [Startup](startup.html#schritt-2-nc_for_cellid-vorbereiten) erzeugt.

## Aufbereitung der NetCDF-Datei

Die Wetterdaten werden durch die Fetch-Logik bezogen, verarbeitet und als NetCDF-Datei gespeichert. Die relevanten Funktionen befinden sich im Backend, insbesondere im Bereich der ICON-/Forecast-Verarbeitung.

Das Skript greift auf die offenen MeteoSwiss-OGD-Daten zu. Dafür wird das Python-Paket `meteodata-lab` verwendet, genauer die Schnittstelle `meteodatalab.ogd_api`. Die Abfrage holt jeweils den aktuellsten verfügbaren ICON-CH1-Forecast (`reference_datetime="latest"`).

| Parameter | Verwendung im Projekt |
|---|---|
| MeteoSwiss-Collection | `ch.meteoschweiz.ogd-forecasting-icon-ch1` |
| Collection im Skript | `ogd-forecasting-icon-ch1` |
| Forecast-Variable | `TOT_PREC`: kumulierter Niederschlag; Grundlage für den daraus abgeleiteten stündlichen Niederschlag |

### Ablauf der Wetterdaten-Erzeugung

Die Wetterdaten-Erzeugung umfasst mehrere Schritte:

1. Für jeden Forecast-Horizont von `+0h` bis `+33h` wird eine Anfrage an MeteoSwiss OGD erstellt.
2. Für jeden Horizont wird die Variable `TOT_PREC` geladen.
3. Die ICON-Daten werden von ihrem ursprünglichen ICON-Gitter auf ein reguläres Koordinatengitter in WGS84 (`EPSG:4326`) umgerechnet.
4. Die einzelnen Forecast-Horizonte werden entlang der Dimension `lead_time` zu einem gemeinsamen Dataset zusammengeführt.
5. Aus den Ensemble-Membern wird ein Mittelwert gebildet.
6. Aus dem kumulierten Niederschlag wird mit einer Differenz über die Zeit der stündliche Niederschlag berechnet.
7. Sehr kleine Werte unter `0.01` werden auf `0.0` gesetzt, damit minimale numerische Restwerte nicht als Regen interpretiert werden.
8. Das Ergebnis wird als timestamp-basierte `.nc`-Datei gespeichert.

### Räumliche Aufbereitung

Die MeteoSwiss-ICON-Daten liegen ursprünglich nicht als einfaches reguläres Lat/Lon-Raster vor. Für die spätere Zuordnung zu OSM-Kanten werden sie deshalb auf ein regelmässiges Raster reprojiziert.

Im aktuellen Skript ist folgendes Zielraster definiert:

```text
Koordinatensystem: EPSG:4326
Ausdehnung:       -0.817, 18.183, 41.183, 51.183
Rastergrösse:     429 x 295
```

Die Umrechnung erfolgt mit:

```text
meteodatalab.operators.regrid.iconremap
```

Dadurch erhalten die Wetterdaten `lat`- und `lon`-Koordinaten, die später für die Zellzuordnung im Routinggraphen verwendet werden können.

### Zeitliche Aufbereitung

Die Forecast-Horizonte werden im Bereich von **0 bis 33 Stunden** geladen.

Nach dem Laden werden die einzelnen Horizonte zu einer Zeitreihe kombiniert. Da `TOT_PREC` kumulierten Niederschlag beschreibt, wird daraus der stündliche Niederschlag abgeleitet:

```text
hourly_rain = mean_precip.diff("lead_time")
```

Im gespeicherten NetCDF-Dataset stehen dadurch zwei zentrale Variablen zur Verfügung:

```text
TOT_PREC      # ursprünglicher kumulierter Niederschlag
hourly_rain   # daraus abgeleiteter stündlicher Niederschlag
```

Für das Routing ist vor allem `hourly_rain` relevant, da die Kantenbewertung wissen muss, wie stark es zu einem bestimmten Zeitpunkt an einer bestimmten Wetterzelle regnet.

### Dateibenennung und Aktualisierung

Die erzeugten NetCDF-Dateien erhalten den aktuellen Unix-Timestamp als Dateinamen, zum Beispiel:

```text
1712345678.nc
```

Die Aktualisierungslogik:

- Beim Start wird geprüft, ob bereits eine aktuelle `.nc`-Datei vorhanden ist.
- Falls die Daten veraltet sind, wird sofort ein neuer Forecast geladen.
- Danach läuft ein Scheduler, der neue Daten jeweils kurz nach den ICON-CH1-Modellläufen lädt.

Geplante Fetch-Zeiten:

```text
00:05, 03:05, 06:05, 09:05, 12:05, 15:05, 18:05, 21:05 UTC
```

Damit orientiert sich die Aktualisierung am dreistündigen Aktualisierungsrhythmus der ICON-CH1-Daten.

### Abhängigkeiten

Für das Fetching und die Aufbereitung werden zusätzliche MeteoSwiss- und Wetterdaten-Bibliotheken benötigt. Sie werden über die Projektumgebung installiert, siehe [Installation](installation.html).

Wichtige Pakete sind unter anderem:

- `meteodata-lab`
- `earthkit`
- `xarray`
- `netCDF4`
- `rasterio`

## Auswahl der passenden NetCDF-Datei

Bei einer Routinganfrage ruft das Backend die Funktion `get_nc_file(start_time)` auf:

```text
backend/utils_nc_file.py
```

Die Funktion durchsucht:

```text
backend/data/NC/
```

Dabei gilt:

- Nur `.nc`-Dateien werden berücksichtigt.
- Dateien ohne numerischen Timestamp werden ignoriert.
- Die Datei muss zur angefragten Startzeit passen.
- Gültig ist eine Datei, wenn sie maximal 33 Stunden alt ist.
- Von allen gültigen Dateien wird die neueste verwendet.

Logik:

```text
age = start_time - file_timestamp

gültig, wenn:
0 <= age <= 33 Stunden
```

Wenn keine passende Datei gefunden wird, kann keine wetterbasierte Route berechnet werden.

## Zuordnung von Strassenkanten zu Wetterzellen

Damit Wetterdaten im Routing verwendet werden können, müssen die Kanten des OSM-Graphen mit dem Wetterraster verknüpft werden. Diese Zuordnung verbindet die räumliche Struktur des Wegenetzes mit den Rasterzellen der NetCDF-Datei.

Der Prozess wird beim Erstellen eines neuen Graphen ausgeführt und die berechneten Zellinformationen werden anschliessend direkt im Graphen gespeichert.

Ablauf:

1. Das Wetterraster wird aus `NC_for_Cellid.nc` gelesen.
2. Aus den Rasterpunkten wird ein KD-Tree aufgebaut.
3. Für jede OSM-Kante wird ein Referenzpunkt bestimmt, in der Regel der Mittelpunkt der Geometrie.
4. Der nächstgelegene Rasterpunkt wird gesucht.
5. Die Kante erhält die Attribute `cell_i`, `cell_j` und `cell_id`.

Diese Attribute bleiben im gespeicherten Graphen erhalten und können bei späteren Routinganfragen direkt wiederverwendet werden.

### Vorteil der Zellzuordnung

Die Zuordnung muss nicht bei jeder Routinganfrage neu berechnet werden. Das verbessert die Laufzeit, reduziert wiederholte Rasterabfragen und macht gespeicherte Graphen wiederverwendbar.

Weitere Informationen zur Verwendung dieser Zellattribute in der Routenberechnung befinden sich in [Routing-Logik](routing.html#wetterzellen-auf-kanten).
