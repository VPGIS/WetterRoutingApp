---
title: A priori – Highlights
---

# A priori – Highlights

Diese Datei beschreibt die Verwendung, Erzeugung und Zuordnung der Wetterdaten im Projekt Wetter Routing App.

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

Der Timestamp entspricht dem Referenzzeitpunkt des Modellaufs (nicht dem Zeitpunkt des Downloads). Er dient zur Zuordnung der Startzeit einer Routinganfrage und zur Prüfung der zeitlichen Gültigkeit der Datei. Das Backend leitet daraus den Lead-Time-Index ab:

```text
lead_h = (departure_unix - file_stem) / 3600
```

### Hilfsdatei für Wetterzellen

Für die Zuordnung von OSM-Kanten zum Wetterraster wird bevorzugt folgende Datei verwendet:

```text
NC_for_Cellid.nc
```

Diese Datei enthält eine reduzierte Rastergeometrie (nur `lat` und `lon`) und wird beim Erstellen neuer Graphen verwendet. Falls sie beim Start noch nicht existiert, wird sie gemäss [Startup](startup.html#schritt-2-nc_for_cellid-vorbereiten) erzeugt.

## GRIB2-, xarray- und NetCDF-Datenstruktur

MeteoSwiss veröffentlicht die ICON-CH1-EPS-Daten im GRIB2-Format über den STAC-Katalog (`data.geo.admin.ch`). GRIB2 ist ein binäres Rasterformat der WMO, das Meteorologen weltweit verwenden. Es enthält komprimierte Felder pro Zeitschritt und Ensemble-Member, jedoch ohne reguläre Lat/Lon-Koordinaten, da ICON ein unstrukturiertes Dreiecksgitter verwendet.

Für die Weiterverarbeitung im Projekt ist folgende Umwandlungskette relevant:

```text
STAC-Katalog (HTTP)
  → GRIB2-Datei je Lead-Time (34 Dateien × N Ensemble-Member)
    → eccodes: Dekodierung der Binärdaten zu NumPy-Arrays
      → scipy KD-Tree: Regridding auf reguläres Lat/Lon-Raster (429 × 295)
        → xarray.Dataset: Zusammenführung aller Zeitschritte + Dimensionen
          → netCDF4: Speicherung als .nc-Datei
```

### Warum diese Umwandlung?

Das ICON-Gitter hat ~600'000 unstrukturierte Gitterpunkte ohne feste Zeilen-/Spaltenindizes. Für das Routing muss aber jede OSM-Kante einem Rasterpunkt zugeordnet werden — das funktioniert nur auf einem regulären Koordinatengitter. xarray erlaubt danach die effiziente Arbeit mit benannten Dimensionen (`lead_time`, `eps`, `y`, `x`), und NetCDF ist das Standardformat für geowissenschaftliche Zeitreihen.

### Inhalt der gespeicherten NC-Datei

Jede gespeicherte Datei enthält drei Variablen:

| Variable | Dimensionen | Beschreibung |
|---|---|---|
| `TOT_PREC` | `(eps, lead_time, y, x)` | Kumulierter Niederschlag aller Ensemble-Member (Rohwert) |
| `hourly_rain` | `(lead_time, y, x)` | Ensemble-Mittelwert des stündlichen Niederschlags (diff von TOT_PREC) |
| `hourly_rain_p90` | `(lead_time, y, x)` | 90. Perzentil des stündlichen Niederschlags über alle Ensemble-Member |

`TOT_PREC` wird für die Routingkostenfunktion verwendet. `hourly_rain` und `hourly_rain_p90` werden von `utils_render.py` direkt ausgelesen und als PNG-Kacheln gerendert, ohne dass bei der Anfrage noch numpy- oder xarray-Operationen anfallen.

## Aufbereitung der NetCDF-Datei

Die Wetterdaten werden durch `utils_fetch.py` bezogen, verarbeitet und als NetCDF-Datei gespeichert. Das Skript greift per HTTP direkt auf den MeteoSwiss-OGD-STAC-Katalog zu und verarbeitet die Rohdaten mit `eccodes`.

| Parameter | Verwendung im Projekt |
|---|---|
| MeteoSwiss-Collection | `ch.meteoschweiz.ogd-forecasting-icon-ch1` |
| Forecast-Variable | `TOT_PREC`: kumulierter Niederschlag; Grundlage für den daraus abgeleiteten stündlichen Niederschlag |
| Datenformat | GRIB2 (je Lead-Time eine Datei, je Datei N Ensemble-Member als separate GRIB-Messages) |

### Ablauf der Wetterdaten-Erzeugung

Die Wetterdaten-Erzeugung umfasst folgende Schritte:

1. STAC-Katalog abfragen: Neuesten vollständigen ICON-CH1-Modelllauf ermitteln.
2. Gitter-Koordinaten laden: ICON-CH1 CLAT/CLON einmalig als `horizontal_constants` GRIB2 (~200 MB) herunterladen und als `.npy` cachen.
3. Regridding-Indizes aufbauen: Mit `scipy.cKDTree` für jeden Ausgabepixel (429 × 295) den nächsten nativen Gitterpunkt bestimmen. Ergebnis wird als `icon_ch1_regrid_indices.npy` gecacht (Bauzeit ~1 min auf dem Raspberry Pi).
4. GRIB2 herunterladen und dekodieren: Für alle 34 Lead-Times je eine GRIB2-Datei abrufen; `eccodes` liest daraus je Ensemble-Member ein NumPy-Array.
5. Regridding anwenden: Die nativen ICON-Vektoren per Fancy-Indexing auf das reguläre 429 × 295 Raster umrechnen.
6. Dataset zusammenführen: Alle Zeitschritte und Ensemble-Member zu einem `(eps, lead_time, y, x)` xarray-DataArray kombinieren.
7. Stündlichen Niederschlag und p90 berechnen: `hourly_rain = mean(TOT_PREC, axis=eps).diff("lead_time")`; p90 wird direkt im Speicher mit `np.sort(axis=0)` berechnet.
8. Sehr kleine Werte unter `0.01 mm/h` auf `0.0` setzen, damit numerische Restwerte nicht als Regen interpretiert werden.
9. Als timestamp-basierte `.nc`-Datei speichern (drei Variablen: `TOT_PREC`, `hourly_rain`, `hourly_rain_p90`).
10. `utils_render.py` aufrufen, um sofort alle 33 × 2 PNG-Kacheln zu erzeugen.

### Räumliche Aufbereitung

Die MeteoSwiss-ICON-Daten liegen auf einem unstrukturierten Dreiecksgitter mit ~600'000 Punkten vor. Für die Zellzuordnung im Routinggraphen werden sie auf ein reguläres Raster projiziert:

```text
Koordinatensystem: EPSG:4326 (WGS84)
Ausdehnung:        -0.817, 18.183, 41.183, 51.183  (lon_min, lon_max, lat_min, lat_max)
Rastergrösse:      429 × 295
```

Die Umrechnung erfolgt mit einem vorberechneten Nearest-Neighbour-Index (scipy KD-Tree). Die Gitter-Koordinaten und der Index werden als `.npy`-Dateien gecacht:

```text
backend/.fetch_cache/icon_ch1_clat.npy
backend/.fetch_cache/icon_ch1_clon.npy
backend/.fetch_cache/icon_ch1_regrid_indices.npy
```

Diese Bounds stimmen exakt mit `BOUNDS` in `frontend/js/config.js` und dem Zielraster in `utils_render.py` überein. Dies ist später für die Zellzuordnung relevant.

### Zeitliche Aufbereitung

Die Forecast-Horizonte werden im Bereich von **0 bis 33 Stunden** geladen.

Da `TOT_PREC` kumulierten Niederschlag beschreibt, wird daraus der stündliche Niederschlag abgeleitet:

```text
hourly_rain = mean_precip.diff("lead_time")
```

Im gespeicherten NetCDF-Dataset stehen dadurch drei zentrale Variablen zur Verfügung:

```text
TOT_PREC          # kumulierter Niederschlag (Rohwert, alle Ensemble-Member)
hourly_rain       # Ensemble-Mittelwert des stündlichen Niederschlags
hourly_rain_p90   # 90. Perzentil des stündlichen Niederschlags
```

Für das Routing ist `hourly_rain` relevant. `hourly_rain_p90` wird für die Unsicherheits-Visualisierung in der Kartendarstellung verwendet.

### Dateibenennung und Aktualisierung

Die erzeugten NetCDF-Dateien erhalten den Unix-Timestamp des Modell-Referenzzeitpunkts als Dateinamen, zum Beispiel:

```text
1712345678.nc
```

Die Aktualisierungslogik:

- Beim Start wird geprüft, ob bereits eine aktuelle `.nc`-Datei vorhanden ist.
- Falls die Daten veraltet sind, wird sofort ein neuer Forecast geladen.
- Danach läuft ein Scheduler-Daemon, der neue Daten jeweils kurz nach den ICON-CH1-Modellläufen lädt.

Geplante Fetch-Zeiten:

```text
00:05, 03:05, 06:05, 09:05, 12:05, 15:05, 18:05, 21:05 UTC
```

Damit orientiert sich die Aktualisierung am dreistündigen Aktualisierungsrhythmus der ICON-CH1-Daten. Auf dem Raspberry Pi wird `utils_fetch.py` als systemd-Dienst gestartet, siehe [Startup](startup.html).

### Abhängigkeiten

Für das Fetching und die Aufbereitung werden folgende Pakete benötigt. Sie werden über die Projektumgebung installiert, siehe [Installation](installation.html).

Wichtige Pakete:

- `eccodes` — GRIB2-Dekodierung (C-Bibliothek; ARM64-Wheel auf PyPI und conda-forge verfügbar)
- `scipy` — KD-Tree für Nearest-Neighbour-Regridding
- `xarray` — Dimensionsbasierte Array-Operationen und NC-Dataset-Assemblierung
- `netCDF4` — NetCDF-Schreib- und Lesezugriff
- `requests` — HTTP-Abfragen an den STAC-Katalog

> **Hinweis zur Deployment-Architektur:** Das frühere Paket `meteodata-lab` (offizielle MeteoSwiss-Bibliothek) ist nicht ARM64-kompatibel und wurde deshalb durch eine direkte STAC/eccodes-Implementierung ersetzt. Gleiches gilt für `earthkit` und `rasterio`, die als transitive Abhängigkeiten von `meteodata-lab` weggefallen sind.

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
- Dateien ohne numerischen Timestamp werden ignoriert (z.B. `NC_for_Cellid.nc`).
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
