---
title: Installation
---

# Installationsanleitung

Diese Anleitung beschreibt die Installation des Projekts mit Conda. Die Conda-Umgebung heisst `vprouting` und basiert auf Python 3.12.

Nach der Installation kann der Server gemäss [Startup](startup.html) gestartet werden.

## Voraussetzungen

Empfohlen wird eine Installation unter Linux oder Windows mit WSL2. Das Projekt verwendet mehrere GIS- und Geo-Bibliotheken, die unter Windows ohne Conda oft aufwendig zu installieren sind.

Voraussetzungen:

- Git
- Miniconda, Anaconda oder Mambaforge
- Internetverbindung für Paketinstallation, OpenStreetMap-/OSMnx-Abfragen und Wetterdaten

## Miniconda / Conda

Falls Conda noch nicht installiert ist, wird Miniconda empfohlen:

```text
https://docs.conda.io/projects/miniconda/en/latest/
```

Nach der Installation sollte Conda im Terminal verfügbar sein:

```bash
conda --version
```

Optional kann Conda aktualisiert werden:

```bash
conda update -n base -c defaults conda
```

## Repository klonen

```bash
git clone https://github.com/calgon854/VPRouting.git
cd VPRouting
```

## Conda-Umgebung erstellen

Die Standardumgebung wird aus der Datei `environment.yml` erstellt:

```bash
conda env create -f environment.yml
```

Dabei werden die wichtigsten Pakete über `conda-forge` installiert. Zusätzliche Python-Abhängigkeiten werden über `pip` aus `requirements.txt` installiert, sofern diese in der Conda-Umgebung eingebunden sind.

## Umgebung aktivieren

```bash
conda activate vprouting
```

## Umgebung aktualisieren

Wenn `environment.yml` oder `requirements.txt` geändert wurde, kann die bestehende Umgebung aktualisiert werden:

```bash
conda env update -f environment.yml --prune
```

## Umgebung entfernen

Falls die Umgebung neu erstellt oder gelöscht werden soll:

```bash
conda deactivate
conda env remove -n vprouting
```

Anschliessend kann sie bei Bedarf erneut erstellt werden:

```bash
conda env create -f environment.yml
```

## Nächster Schritt

Nach der Installation wird der API-Server mit dem Startup-Skript gestartet. Siehe [Startup](startup.html).
