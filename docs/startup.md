# Server starten

Der API-Server kann über das Startup-Skript gestartet werden.  
Das Skript führt zuerst die nötige Vorbereitung aus und startet danach das FastAPI-Backend.

> Hinweis: Das Aufstarten kann länger dauern, da zuerst die aktuellen Wetterdaten bezogen werden müssen

## Voraussetzungen

Die Conda-Umgebung muss aktiviert sein.

Siehe: [Installationsanleitung](INSTALL.md)

```bash
conda activate vprouting
```

Ausserdem muss der Befehl aus dem Projekt-Root ausgeführt werden:

```bash
cd VPRouting
```

## Startbefehl

```bash
python scripts/startup/startup.py
```

Danach läuft der API-Server unter:  
Siehe: [Swagger-Dokumentation](http://127.0.0.1:8000/docs)

```text
http://127.0.0.1:8000
```

---

### Was passiert beim Start?

Das Skript `scripts/startup/startup.py` führt ein mehrstufiger Startprozess aus.

Der Startup-Prozess umfasst aktuell folgende Schritte:

1. Aktuelle Wetterdaten vorbereiten
2. `NC_for_Cellid.nc` vorbereiten
3. API-Server starten

---

### Schritt 1: Aktuelle Wetterdaten vorbereiten

Dieser Schritt ist bereits als Platzhalter im Startup-Skript vorbereitet, aber noch nicht implementiert.

Später soll hier ein Skript aufgerufen werden, das aktuelle Wetterdaten lädt, verarbeitet und als `.nc`-Datei im folgenden Ordner speichert:

```text
backend/data/NC/
```

Geplanter Zweck dieses Schritts:

- aktuelle Wetterdaten herunterladen
- daraus eine neue NetCDF-Datei erzeugen
- die Datei im Backend-Datenordner speichern
- sicherstellen, dass die Routing-API mit aktuellen Wetterdaten arbeiten kann

Aktuell wird dieser Schritt beim Start nur gemeldet und danach übersprungen:

```text
Schritt 1 übersprungen: Generierung aktueller .nc-Dateien ist noch nicht implementiert.
```

---

### Schritt 2: NC_for_Cellid vorbereiten

Das Vorbereitungsskript prüft, ob folgende Datei existiert:

```text
backend/data/NC/NC_for_Cellid.nc
```

Falls diese Datei noch nicht existiert, wird die erste vorhandene `.nc`-Datei aus `backend/data/NC/` gelesen. Daraus werden nur die Variablen `lat` und `lon` extrahiert und als `NC_for_Cellid.nc` gespeichert.

Diese reduzierte Datei wird später im Backend verwendet, um Kanten aus dem OSM-Graphen einer Wetterrasterzelle zuzuordnen.

---

### Schritt 3: API-Server starten

Anschliessend startet das Startup-Skript den API-Server mit:

```bash
python -m uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
```

---

# Server stoppen

Der Server läuft im Terminal weiter.

Zum Stoppen:

```text
Ctrl + C
```
