# About

## Projekt

Die **Wetter Routing App** ist ein studentisches Projekt im Rahmen des Vertiefungsprofils 4230 Geoinformatik Raumanalyse I an der FHNW. Ziel ist ein Prototyp, der klassische Routingfunktionen mit Wetterinformationen verbindet.

Die Anwendung nutzt OpenStreetMap-Daten zur Erstellung eines Wegenetzes und kombiniert dieses mit Wetterdaten von MeteoSwiss. Dadurch kann eine Route nicht nur anhand der Distanz oder Reisezeit berechnet werden, sondern auch anhand wetterbezogener Einflüsse wie Niederschlag bewertet werden.

Im Zentrum steht die Frage, wie sich Wetterdaten in eine Geodateninfrastruktur integrieren lassen und wie daraus ein Routingmodell entsteht, das für bestimmte Wetterbedingungen geeignete Wege ermittelt, die Nutzende möglichst trocken ans Ziel führen.

## Projektkontext

Dieses Projekt entstand im Rahmen eines studentischen Projekts.

Hochschule: Fachhochschule Nordwestschweiz FHNW  
Institut: Institut Geomatik IGEO  
Studiengang: BSC Geomatik  
Modul: 4230 Geoinformatik Raumanalyse I  
Semester: 4 und 6

### Projektteam

Studierende:
- Tobias Schulthess (GitHub-User: asterixgis)
- Ignaz Kuczynski   (GitHub-User: calgon854)

Betreuung:

- Pia Bereuter
- Stefan Eberlein
- Carolin Bronowicz  

## Aufgabenstellung

Im Modul sollte eine eigene geoinformatische Fragestellung entwickelt und als Projektarbeit umgesetzt werden. Die Aufgabe bestand darin, ein Thema zu wählen, dazu ein fachliches und technisches Konzept zu erarbeiten und dieses in einer funktionierenden Geodateninfrastruktur umzusetzen.

Für dieses Projekt wurde die Fragestellung auf wetterabhängiges Routing ausgerichtet:

**Wie kann eine Routinganwendung so erweitert werden, dass Wetterdaten, insbesondere Niederschlag, in die Bewertung und Auswahl einer Route einfliessen?**

Daraus ergaben sich folgende Teilaufgaben:

- Aufbau eines Routing-Prototyps auf Basis von OpenStreetMap-Daten
- Einbindung und Verarbeitung von Wetterdaten der MeteoSwiss in geeignetem Format (NetCDF)
- Zuordnung von Wetterinformationen zu Kanten eines Routinggraphen
- Entwicklung und Vergleich einfacher sowie zeitabhängiger Routingmodelle
- Bereitstellung einer FastAPI-Schnittstelle für Routinganfragen
- Umsetzung eines lokalen Frontends zur Auswahl von Start, Ziel und Routingparametern
- Dokumentation der Architektur, Datenquellen und Routinglogik

Die Projektarbeit wurde in einer Gruppe bearbeitet, in den Lehrveranstaltungen begleitet und als öffentliches GitHub-Projekt verwaltet. Der entwickelte Prototyp ist zu Demonstrationszwecken gedacht und zeigt, wie Wetterinformationen in eine Routingentscheidung integriert werden können.

# Reflektion



## Datenquellen

Das Projekt verwendet unter anderem:

- OpenStreetMap-Daten
- Wetterdaten von MeteoSwiss im NetCDF-Format
- offene Wetterdatenquellen, sofern konfiguriert

Weitere Details befinden sich in:

- [Wetterdaten](weather-data.md)
- [Routing-Logik](routing.md)



## Lizenz

Die Lizenz des Projekts befindet sich in der Datei:

```text
LICENSE Opensource
```
