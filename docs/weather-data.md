# Wetterdaten

Diese Datei beschreibt die Verwendung, Erzeugung und Zuordnung der Wetterdaten im Projekt VP Routing.

---

## Überblick

VP Routing verwendet Wetterdaten im NetCDF-Format, um Routen wetterabhängig bewerten zu können.

Die Wetterdaten werden genutzt, um Niederschlag entlang einer Route zu erkennen und betroffene Kanten im Routinggraphen höher zu gewichten.

---

## Speicherort

Die Routing-API erwartet die NetCDF-Dateien im folgenden Ordner:

```text
backend/data/NC/
```

Beispiel:

```text
backend/data/NC/1712345678.nc
```

---

## Dateibenennung

Die Forecast-Dateien werden als Unix-Timestamp benannt.

Beispiel:

```text
1712345678.nc
```

Der Timestamp im Dateinamen wird vom Backend verwendet, um zu prüfen, ob die Datei zur angefragten Startzeit passt.

---

## Hilfsdatei für Wetterzellen

Für die Zuordnung von OSM-Kanten zum Wetterraster wird bevorzugt folgende Datei verwendet:

```text
backend/data/NC/NC_for_Cellid.nc
```

Diese Datei enthält die reduzierte Rastergeometrie und wird beim Erstellen neuer Graphen verwendet.

---

## Entstehung der Wetterdaten

Die Wetterdaten werden durch folgendes Skript erzeugt:

```text
backend/fetch_icon.py
```

Das Skript bezieht Wetterdaten aus offenen MeteoSwiss-OGD-Daten.

Verwendete Collection:

```text
ogd-forecasting-icon-ch1
```

Verwendete Variable:

```text
TOT_PREC
```

---

## Verarbeitungsschritte

Die Wetterdaten werden in mehreren Schritten verarbeitet:

1. Forecast-Daten werden für mehrere Zeithorizonte geladen.
2. Die ICON-Daten werden auf ein reguläres Koordinatengitter umgerechnet.
3. Die einzelnen Forecast-Horizonte werden zu einem gemeinsamen Dataset kombiniert.
4. Aus dem kumulierten Niederschlag kann stündlicher Regen abgeleitet werden.
5. Das Ergebnis wird als `.nc`-Datei gespeichert.

---

## Forecast-Horizont

Aktuell werden Forecast-Horizonte von:

```text
+0h bis +33h
```

verwendet.

Dadurch kann das Backend prüfen, ob eine vorhandene Datei für eine angefragte Startzeit noch gültig ist.

---

## Auswahl der passenden NetCDF-Datei

Bei einer Routinganfrage ruft das Backend folgende Funktion auf:

```text
get_nc_file(start_time)
```

Datei:

```text
backend/utils_nc_file.py
```

Die Funktion durchsucht:

```text
backend/data/NC/
```

Dabei gilt:

- nur `.nc`-Dateien werden berücksichtigt
- Dateien ohne numerischen Timestamp werden ignoriert
- die Datei muss zur angefragten Startzeit passen
- gültig ist eine Datei, wenn sie maximal 33 Stunden alt ist
- von allen gültigen Dateien wird die neueste verwendet

Logik:

```text
age = start_time - file_timestamp

gültig, wenn:
0 <= age <= 33 Stunden
```

Wenn keine passende Datei gefunden wird, kann keine wetterbasierte Route berechnet werden.

---

## Reduzierte Rasterdatei

Die Datei:

```text
NC_for_Cellid.nc
```

wird durch folgendes Skript erzeugt:

```text
scripts/startup/reduce_nc_to_grid_geometry.py
```

Diese Datei enthält nur die für die Zellzuordnung benötigten Koordinateninformationen.

Typische Variablen:

```text
lat
lon
```

---

## Zuordnung von Straßenkanten zu Wetterzellen

Damit eine OSM-Kante einen Wetterwert erhalten kann, muss sie einer Wetterzelle zugeordnet werden.

Dieser Prozess passiert beim Erstellen eines neuen Graphen.

Ablauf:

1. Das Wetterraster wird aus `NC_for_Cellid.nc` gelesen.
2. Aus allen Rasterpunkten wird ein KD-Tree aufgebaut.
3. Für jede OSM-Kante wird der Mittelpunkt der Geometrie bestimmt.
4. Der nächstgelegene Rasterpunkt wird gesucht.
5. Die Kante erhält Wetterzellen-Attribute.

Gespeicherte Attribute:

```text
cell_i
cell_j
cell_id
```

Diese Attribute bleiben im gespeicherten Graphen erhalten.

---

## Vorteil der Zellzuordnung

Durch die gespeicherten Wetterzellen-Attribute muss die Zuordnung nicht bei jeder Routinganfrage neu berechnet werden.

Das verbessert:

- Laufzeit
- Wiederverwendbarkeit der Graphen
- Effizienz der Forecast-Abfragen

---

## Verwendung im Routing

Während der Routenberechnung wird für jede relevante Kante ein Forecast-Wert gelesen.

Dazu verwendet das Backend:

```text
get_forecast
```

Datei:

```text
backend/utils_forecast.py
```

Benötigt werden:

```text
cell_i
cell_j
target_timestamp
```

---

## Unterschied zwischen den Routingmodellen

Beim Modell `einfach` wird der Forecast zur Startzeit verwendet.

```text
target_timestamp = start_time
```

Beim Modell `advanced` wird die erwartete Ankunftszeit an der jeweiligen Kante verwendet.

```text
target_timestamp = arrival_time
```

Dadurch kann das erweiterte Modell zeitliche Änderungen im Wetter berücksichtigen.

---

## Einfluss auf die Kosten

Der gelesene Forecast-Wert wird an folgende Funktion übergeben:

```text
compute_rain_adjusted_cost
```

Datei:

```text
backend/utils_forecast.py
```

Diese Funktion erhöht die Kosten einer Kante abhängig von:

- Kantenlänge
- Niederschlagsmenge
- Regenempfindlichkeit `sensibility`

Weitere Details zur Kostenberechnung befinden sich in:

```text
docs/routing.md
```

---

## Hinweis zum Ausgabeordner

Aktueller Hinweis zur Implementierung:

```text
backend/fetch_icon.py
```

verwendet möglicherweise einen anderen Standard-Ausgabeordner als die Routing-API.

Die Routing-API erwartet produktiv verwendete Wetterdateien hier:

```text
backend/data/NC/
```

Falls der Fetcher Dateien in einem anderen Ordner speichert, müssen sie entweder verschoben oder der Ausgabeordner angepasst werden.

---

## Zusammenfassung

Die Wetterdaten übernehmen drei zentrale Aufgaben:

1. Bereitstellung von Forecast-Werten für Routinganfragen
2. Zuordnung von OSM-Kanten zu Wetterzellen
3. wetterabhängige Gewichtung einzelner Routenabschnitte