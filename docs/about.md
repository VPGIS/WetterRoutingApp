# About

## Projekt

Die **Wetter Routing App** entstand im Rahmen des Vertiefungsprofils 4230 Geoinformatik Raumanalyse I.

Das Projekt kombiniert OpenStreetMap-Daten mit Wetterdaten im NetCDF-Format, um Routen nicht nur nach Distanz, sondern auch anhand von Wetterbedingungen wie Niederschlag bewerten zu können.


## Aufgabenstellung   
Überlegt Euch eine spannende Fragestellung, die Ihr in Eurer Projektarbeit umsetzen möchtet.
Lasst Euch von verschiedenen Themen inspirieren, die für das Erarbeiten einer Geodateninfra-
struktur spannend sein könnten, wie beispielsweise einem Energiemonitoring in einer Region
oder Qualitätsabschätzung Oberflächenabflussdaten oder dem GWR für Energieabschätzun-
gen.
Seite 2/3
Stöbert in der Literatur oder spannenden Projekten, die Euch interessieren, Dokumentationen,
informiert Euch über die Methoden und das Vorgehen und erarbeitet Euch ein Konzept zur Um-
setzung und Lösung der Fragestellung, die Ihr im Rahmen der Arbeit untersuchen werdet.
Im Verlauf des Semesters werdet Ihr in die einzelnen Themen ergänzend zum Vorwissen, wel-
ches Ihr aus dem bisherigen Studienverlauf mitbringt, eingeführt. Es wird von Euch eine aktive
Mitarbeit sowie hohe Selbstständigkeit erwartet, um die Themen zu verstehen und in Eurem
Projekt umzusetzen.
Die Projektarbeit wird in Gruppen von 3 Studierenden durchgeführt. Die Gruppenarbeit wird in
den Vorlesungen und Übungen begleitet und mit Coaching unterstützt. Das Projekt soll in einem
öffentlichen GitHub Repository verwaltet werden, sowie auf einem Raspberry Pi installiert wer-
den, der als Euer Projektserver dient. Ein Raspberry Pi 4 wird Euch für die Dauer der Projektar-
beit zur Verfügung gestellt


  



---

## Ziel des Projekts

Ziel des Projekts ist die Entwicklung eines Prototyps für wetterbewertetes Routing.

Der Fokus liegt auf:

- Routing mit OpenStreetMap-Daten
- Integration von NetCDF-Wetterdaten
- Bewertung von Routen anhand von Niederschlag
- Vergleich einfacher und zeitabhängiger Routingmodelle
- Bereitstellung eines lokalen Frontends und einer FastAPI-Schnittstelle

---
## Kontext

Dieses Projekt entstand im Rahmen eines studentischen Projekts.

Hochschule: Fachhochschule Nordwestschweiz FHNW  
Institut: Institut Geomatik IGEO  
Studiengang: BSC Geomatik  
Modul: 4230 Geoinformatik Raumanalyse I  
Semester: 4 und 6

## Projektteam
Studierende:
- Tobias Schulthess
- Ignaz Kuczynski


Betreuung:
- Pia Bereuter
- Stefan Eberlein
- Carolin Bronowicz





---

## Hinweis zum Prototyp

Dieses Projekt ist ein akademischer Prototyp.

Die berechneten Routen dienen Demonstrations- und Forschungszwecken.  
Sie sind nicht für sicherheitskritische Navigation, Einsatzplanung oder produktive Verkehrsführung vorgesehen.

---

## Datenquellen

Das Projekt verwendet unter anderem:

- OpenStreetMap-Daten
- Wetterdaten im NetCDF-Format
- offene Wetterdatenquellen, sofern konfiguriert

Weitere Details befinden sich in:

- [Wetterdaten](weather-data.md)
- [Routing-Logik](routing.md)

---

## Kontakt

Kontakt über das GitHub-Repository:

```text
https://github.com/calgon854/VPRouting
```

---

## Lizenz

Die Lizenz des Projekts befindet sich in der Datei:

```text
LICENSE
```