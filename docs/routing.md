---
title: Routing-Logik
---

# Routing-Logik

Diese Datei beschreibt die Routingmodelle, die Kostenberechnung und die Verwendung von Wetterdaten in der Routenbewertung.

---

## Überblick

Die Wetter Routing App berechnet Fahrradrouten auf Basis von OpenStreetMap-Graphen. Die Anwendung bewertet Kanten nicht nur nach ihrer Länge, sondern kann zusätzlich Niederschlagsdaten aus MeteoSwiss-Forecasts berücksichtigen. Dadurch werden Streckenabschnitte mit ungünstigen Wetterbedingungen höher gewichtet.

Die Routinglogik ist Teil der FastAPI-Verarbeitung. Eine Anfrage kommt über den Endpunkt `/WAPapi/v1/route` ins Backend, wird in `backend/api.py` vorbereitet und anschliessend an eines der Routingmodelle übergeben.

Die wichtigste Datei für die Routingmodelle ist:

```text
backend/utils_routingmodels.py
```

Zusätzlich werden Funktionen aus folgenden Dateien verwendet:

```text
backend/utils_forecast.py
backend/utils_graph.py
backend/utils_nc_file.py
```

Weitere Einordnung zum gesamten Ablauf befindet sich in:

- [Architektur](architecture.html)
- [Wetterdaten](weather-data.html)

---

## Einordnung in den API-Ablauf

Bevor die eigentliche Routenberechnung startet, bereitet das Backend mehrere Daten vor:

1. Start- und Zielpunkt werden aus Adresse oder Koordinaten in WGS84-Koordinaten umgewandelt.
2. Die Geschwindigkeit wird von km/h in m/s konvertiert.
3. Über `get_nc_file(start_time)` wird eine passende NetCDF-Wetterdatei aus `backend/data/NC/` ausgewählt.
4. Aus Start und Ziel wird eine Bounding Box berechnet.
5. Ein passender OSM-Graph wird aus `backend/data/graphs/` geladen oder über OSMnx neu erstellt.
6. Start- und Zielkoordinaten werden den nächstgelegenen Nodes im Graphen zugeordnet.
7. Abhängig vom Parameter `routingmodel` wird `einfach` oder `advanced` ausgeführt.

Das Ergebnis der Routingfunktion ist eine Sequenz von Node-IDs. Diese wird danach mit OSMnx in ein GeoJSON-ähnliches Format umgewandelt und an das Frontend zurückgegeben.

---

## Routingmodelle

Aktuell stehen zwei Routingmodelle zur Verfügung:

| Routingmodell | Beschreibung                                                     |
| ------------- | ---------------------------------------------------------------- |
| `einfach`     | Bewertet alle Kanten einmalig mit dem Forecast zur Startzeit.    |
| `advanced`    | Bewertet Kanten zeitabhängig anhand der erwarteten Ankunftszeit. |

Beide Modelle verwenden dieselbe Grundidee für die Wetterbewertung: Pro Kante wird ein Forecast-Wert gelesen und daraus mit `compute_rain_adjusted_cost` ein wetterabhängiger Kostenwert berechnet.

---

## Einfaches Routingmodell: `einfach`

Das Modell `einfach` verwendet einen statischen Dijkstra-Ansatz.

Implementierung im Code:

```text
static_djikstra
```

Datei:

```text
backend/utils_routingmodels.py
```

### Grundidee

Bei diesem Modell werden alle Kanten vor der eigentlichen Wegsuche einmalig bewertet. Der Forecast wird für alle Kanten zur Startzeit der Route gelesen.

Danach wird mit OSMnx der kürzeste Pfad anhand der berechneten Kosten gesucht. Die Route bleibt dadurch einfach nachvollziehbar und ist schneller berechnet als beim zeitabhängigen Modell.

### Ablauf

```mermaid
flowchart TD
    A[Routingmodell einfach] --> B[static_djikstra starten]
    B --> C[Start- und Zielnode übernehmen]
    C --> D[Forecast zur Startzeit bestimmen]
    D --> E[Alle Edges durchlaufen]
    E --> F[Forecast-Wert pro Edge lesen]
    F --> G[Regen-Penalty berechnen]
    G --> H[cost pro Edge setzen]
    H --> I[travel_time pro Edge setzen]
    I --> J[OSMnx shortest_path ausführen]
    J --> K[weight = cost verwenden]
    K --> L[Node-Pfad zurückgeben]
```

### Vorteile

- einfach nachvollziehbar
- schneller als das zeitabhängige Modell
- gut geeignet für kurze Routen
- geringe Komplexität

### Grenzen

- Wetter wird nur zur Startzeit berücksichtigt
- spätere Wetteränderungen entlang der Route werden nicht berücksichtigt
- bei längeren Routen weniger realistisch

---

## Erweitertes Routingmodell: `advanced`

Das Modell `advanced` verwendet einen zeitabhängigen Dijkstra-Ansatz.

Implementierung:

```text
time_dependent_dijkstra
```

Datei:

```text
backend/utils_routingmodels.py
```

### Grundidee

Bei diesem Modell wird nicht nur betrachtet, welche Kante befahren wird, sondern auch zu welchem Zeitpunkt diese Kante voraussichtlich erreicht wird. Dadurch kann dieselbe Kante je nach Ankunftszeit unterschiedliche Kosten erhalten.

Im Unterschied zum einfachen Modell wird der Forecast während der Suche laufend anhand der erwarteten Ankunftszeit abgefragt. Zwischen den Forecast-Zeitschritten wird interpoliert.

### Ablauf

```mermaid
flowchart TD
    A[Routingmodell advanced] --> B[time_dependent_dijkstra starten]
    B --> C[Start-State initialisieren]
    C --> D[Priority Queue erstellen]
    D --> E[Startnode mit Kosten 0 einfügen]

    E --> F{Priority Queue leer?}
    F -- ja --> Z[Keine Route gefunden]
    F -- nein --> G[State mit geringsten Kosten entnehmen]

    G --> H{Ziel erreicht?}
    H -- ja --> I[Pfad rekonstruieren]
    H -- nein --> J[Ausgehende Kanten prüfen]

    J --> K[Travel Time der Kante berechnen]
    K --> L[Ankunftszeit am Nachbarn bestimmen]
    L --> M[Forecast zur Ankunftszeit interpolieren]
    M --> N[Regen-Penalty berechnen]
    N --> O[Neue Gesamtkosten berechnen]

    O --> P{Besserer Pfad gefunden?}
    P -- ja --> Q[dist und parent aktualisieren]
    Q --> R[Neuen State in Priority Queue einfügen]
    R --> F

    P -- nein --> F
    I --> S[Node-Pfad zurückgeben]
```

### Vorteile

- realistischere Wetterbewertung
- geeignet für längere Routen
- berücksichtigt zeitliche Änderungen im Forecast
- bewertet Regen dort, wo die Route ihn voraussichtlich erreicht

### Grenzen

- rechenintensiver als `einfach`
- komplexere Zustandsverwaltung
- mehr Forecast-Abfragen während der Suche

---

## Kantenbewertung

Für jede Kante wird eine Kostenfunktion berechnet. Die Kosten basieren auf der Kantenlänge und einem wetterabhängigen Zuschlag.

Die Berechnung erfolgt über:

```text
compute_rain_adjusted_cost
```

Datei:

```text
backend/utils_forecast.py
```

Grundformel:

```text
rain_amount = max(forecast, 0)

cost = length * (1 + multiplier * rain_amount^exponent)
```

Wenn kein Regen vorhanden ist:

```text
cost = length
```

Für die höchste Regenempfindlichkeit gilt zusätzlich:

```text
cost = infinity
```

Damit werden Kanten mit Regen vollständig vermieden, sofern eine alternative Route existiert.

Der berechnete Wert wird als `cost` an der Kante gespeichert und für die Pfadsuche verwendet. Zusätzlich wird aus Länge und Geschwindigkeit eine `travel_time` berechnet.

---

### Regenempfindlichkeit `sensibility`

`sensibility` steuert, wie stark Regen die Kosten einer Kante erhöht. Der Parameter wird über die API übergeben und an `compute_rain_adjusted_cost` weitergereicht.

| `sensibility` | `multiplier` | `exponent` | Wirkung                                        |
| ------------- | -----------: | ---------: | ---------------------------------------------- |
| `lowest`      |            - |          - | Regen hat keinen Einfluss auf die Kosten.      |
| `low`         |         25.0 |        1.0 | Regen erhöht die Kosten leicht.                |
| `medium`      |        100.0 |        1.2 | Regen wird deutlich vermieden.                 |
| `high`        |        400.0 |        1.4 | Regenabschnitte werden stark bestraft.         |
| `highest`     |            - |          - | Kanten mit Regen werden vollständig vermieden. |

Bei `lowest` bleibt `cost = length`, auch wenn Regen vorhergesagt ist. Bei `highest` wird für Kanten mit Regen `cost = infinity` gesetzt.

---

## Graphen

Die Routingmodelle arbeiten auf OSMnx-Graphen. Ein Graph enthält Nodes, Kanten, Kantenlängen und Geometrien. Beim Erstellen eines neuen Graphen werden fehlende Kantengeometrien ergänzt und die Kanten anschliessend mit Wetterzellen verknüpft.

Gespeicherte Graphen befinden sich im Ordner:

```text
backend/data/graphs/
```

Typische Dateien:

- `*.graphml`: gecachte und aufbereitete Graphen
- `index.json`: Verzeichnis der verfügbaren Graphen

Wenn ein passender Graph bereits vorhanden ist, wird er aus dem Cache geladen. Falls kein passender Graph vorhanden ist, wird ein neuer Graph über OSMnx erstellt, mit Wetterzellen ergänzt und gespeichert.

## Wetterzellen auf Kanten

Damit eine Kante mit Wetterdaten bewertet werden kann, besitzt sie Verweise auf eine Zelle im NetCDF-Wetterraster:

- `cell_i`
- `cell_j`
- `cell_id`

Die Zuordnung wird beim Erstellen eines neuen Graphen berechnet und im gespeicherten Graphen abgelegt. Dadurch kann das Routing später direkt den passenden Forecast-Wert pro Kante lesen.

Die detaillierte Beschreibung der Rasteraufbereitung und Zellzuordnung befindet sich in [Wetterdaten](weather-data.html#zuordnung-von-strassenkanten-zu-wetterzellen).

## Wetterdaten im Routing

Im Routing wird die geöffnete NetCDF-Datei nur noch abgefragt. Die Aufbereitung, Aktualisierung, Auswahl der Datei und Zuordnung der Wetterzellen ist in [Wetterdaten](weather-data.html) beschrieben.

Beim einfachen Modell wird der Forecast ohne zeitliche Interpolation zur Startzeit gelesen. Beim erweiterten Modell wird der Forecast zur erwarteten Ankunftszeit interpoliert.

## Ergebnis

Das Ergebnis der Routenberechnung ist ein Node-Pfad. Dieser wird anschliessend in `backend/api.py` mit OSMnx in ein GeoJSON-ähnliches Format umgewandelt.

Die Antwort enthält pro Routensegment unter anderem:

- `osmid`
- `length`
- `cost`
- `travel_time`
- `geometry`
