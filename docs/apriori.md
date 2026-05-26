---
title: A priori
---

# A priori – Highlights

Diese Seite dokumentiert die interessantesten, seltsamsten und wichtigsten Skripte und Notebooks aus den `_apriori/`-Ordnern des Projekts. Sie zeigen den Weg vom ersten Experiment bis zur produktiven Lösung.

Die Dateien liegen in zwei Ordnern:

- `_apriori/` — Wetterdaten-Visualisierung und Daten-Pipeline-Experimente
- `backend/_apriori/` — Routing-Experimente und Graph-Optimierungen

---

## Wetterdaten und Visualisierung

### `_apriori/html_rain.ipynb` — Der erste echte Pipeline-Prototyp

Das Notebook, mit dem alles begann. Es ruft ICON-CH1-EPS-Daten über die offizielle MeteoSwiss-Bibliothek `meteodata-lab` ab, regriddert 34 Lead-Time-Schritte auf ein reguläres 429×295-Raster und speichert das Ergebnis als NetCDF. Anschliessend wird eine interaktive Leaflet-Karte mit OSM-Kacheln gerendert. Drei klare Schritte: Fetch, Clean, Render.

Warum es besonders ist: Es war die erste funktionierende End-to-End-Pipeline vom STAC-Katalog bis zur sichtbaren Karte.

---

### `_apriori/icon_ch1_animated_map.ipynb` — 33 Frames, ein riesiges HTML

Das Notebook rendert alle 33 Forecast-Stunden als `matplotlib`-PNGs, kodiert jeden Frame als Base64 und injiziert das gesamte Array als JavaScript-Variable in eine selbstständige HTML-Datei. Die resultierende Datei läuft ohne Server, ohne API, ohne Abhängigkeiten. Einfach im Browser öffnen.

Das generierte HTML enthält einen Zeitregler, eine Opazitätssteuerung und eine Legende. Alle Bilder sind mit Haversine-Masking auf die Schweiz zugeschnitten. Die fertige HTML-Datei ist mehrere Megabyte gross.

Warum es besonders ist: Server-loses animated rain forecast. Kompletter Verzicht auf jede Backend-Infrastruktur. Der direkte Vorläufer des heutigen Tile-Renderers.

---

### `_apriori/utils_geoserver.py` — GeoServer-Vollautomatisierung auf dem Pi

Dieses Skript verbindet sich via REST-API mit einer lokalen GeoServer-Instanz, erstellt automatisch Workspace, Datastore, SLD-Style und Layer und veröffentlicht die aktuellste NetCDF-Datei als WMS-Schicht. Falls GeoServer noch nicht läuft, startet das Skript ihn selbst über das `startup.sh`-Script und wartet bis zu 60 Sekunden auf den Hochlauf.

Das SLD enthält einen High-Contrast-Debug-Farbverlauf (Grau → Rot → Orange → Gelb → Grün → Blau → Lila), der bei jedem Wert über 0.01 mm anspringt.

Der Ansatz wurde schliesslich zugunsten des eigenen Tile-Renderers aufgegeben, weil vermutet wurde, dass es am netcdf Format lag. Es lag daran wie eccodes die Grib2 arrays abfüllte.

Warum es besonders ist: Vollständige automatisierte GeoServer-Infrastruktur, programmgesteuert von Grund auf aufgebaut und verworfen. Heute würde es sehr wahrscheinlich funktionieren.

---

## Routing-Entwicklung

### `backend/_apriori/Routing_Provisorisch/Djikstra_mit_abfahrtzeit.ipynb` — Der Ursprung

Das erste Routing-Notebook. Dijkstra auf einem OSMnx-Fahrradgraphen mit zufälligen Wettergewichten (`np.random.uniform(0, 16, 24)` pro Kante). Hier wurden die Bausteine ein erstes mal getestet, und sich überlegt wie die Wetterdaten auf die Kanten kommen. Noch bevor es überhaupt Wetterdaten gab.

Warum es besonders ist: Die Idee des zeitabhängigen Routings wird hier das erste Mal angerissen.

---

### `backend/_apriori/Djikstra_toll.ipynb` — Echter Wetterdaten-Routing

Die Weiterentwicklung: ersetzt zufällige Gewichte durch echte NC-Daten. Der entscheidende Fortschritt ist der Batch-Nearest-Neighbour-Lookup: alle Kanten-Zentroiden werden in einem einzigen `cKDTree.query()`-Aufruf dem nächsten Wetterrasterputnkt zugeordnet. Dann werden alle 24-Stunden-Forecasts mit einem einzigen numpy-Slice extrahiert.

Performance-Output aus dem Notebook:

```text
Dataset loaded:           ~ms
Centroids collected:      ~ms  (N edges)
Batch nearest-neighbour:  ~ms
Forecast values sliced:   ~ms
```

Warum es besonders ist: Der Moment, wo abstraktes Wetterdata-Routing zur messbaren, echten Funktion wurde.

---

### `backend/_apriori/amazing_query.py` — Die Query-Bibliothek mit dem besten Namen

251 Zeilen sauberer Query-Code: `open_dataset`, `query_point`, `query_points`, `find_heavy_rain`, und das Herzstück `_nearest_yx_batch` mit scipy `cKDTree`. Vollständig dokumentiert mit Usage-Beispielen im Docstring. Unterstützt Einzelpunkt-, Mehrpunkt- und All-Lead-Time-Abfragen.

Warum es besonders ist: Eigenständige, gut dokumentierte Bibliothek, die direkt in `dickstra_toll.ipynb` eingebunden wurde und die Basis für `utils_graph.py` ist.

---

### `backend/_apriori/light_graph_test.ipynb` — Graph-Diät für den Raspberry Pi

Das Notebook testet, wie weit sich der OSMnx-Graph reduzieren lässt. Die Funktion `graph_to_lightgraph` entfernt alle nicht benötigten Edge- und Node-Attribute. Ein weiterer Ansatz, das Umrechnen der Kantenlängen von Float-Metern zu Integer-Zentimetern (`int(round(length * 100))`), was RAM auf dem Pi sparen soll.

Warum es besonders ist: Dieses Notebook bereitet Ansätze vor, wie der RAM bei grossen Graphen eingespart werden kann. Was sich allerdings nicht Umgesetz wurde.

---

### `backend/_apriori/fetch_icon_old.py` — Das Relikt vor ARM64

Der originale Fetch-Code auf Basis von `meteodata-lab`, `earthkit` und `rasterio`. Funktioniert auf Windows und WSL-Ubuntu problemlos. Das Skript ist vollständig und produktionsreif. Es war der direkte Vorgänger von `utils_fetch.py`, wurde aber verworfen, weil `meteodata-lab` kein ARM64-Package hat. Mehr dazu in [AI Nutzung](aiusage.html) und [Architektur](architecture.html).

Warum es besonders ist: Das historische Zeugnis des ARM64-Problems.

---

### `backend/_apriori/reduce_nc_to_grid_geometry.ipynb` — Der Zell-Index-Trick

Erzeugt die Hilfsdatei `NC_for_Cellid.nc`: eine NetCDF-Datei, die nur noch `lat` und `lon` als 2D-Arrays enthält, ohne Forecast-Daten. Diese Datei wird beim Graph-Erstellen verwendet, um jeder OSM-Kante einmalig ihren nächsten Wetterzelle zuzuordnen. Das spart bei jeder späteren Routing-Anfrage die Vektorielle Zuordnung von Edge und Wetterzelle.

Warum es besonders ist: Ein einmaliger Preprocessing-Schritt, der alle späteren Anfragen erheblich schneller macht.

---

### `backend/_apriori/get_routingparam_test.ipynb` — End-to-End-Systemtest

Das Notebook testet den vollständigen Routing-Ablauf: Geocoding einer Adresse (`Hof Schönenberg 2, 4133 Pratteln`), Bounding-Box-Berechnung, gecachter Graph-Load, NC-Datei-Auswahl. Es ist der direkte Vorgänger des API-Endpunkts `/WAPapi/v1/route`.

Warum es besonders ist: Erster vollständiger Durchstich durch alle Backend-Schichten in einem einzigen Notebook.
