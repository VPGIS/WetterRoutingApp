# About

## Projektübersicht

Die **Wetter Routing App** ist ein studentisches Projekt im Rahmen des Vertiefungsprofils **4230 Geoinformatik Raumanalyse I** an der Fachhochschule Nordwestschweiz FHNW. Das Projekt entstand am Institut Geomatik IGEO im Studiengang BSc Geomatik und wurde im 4. und 6. Semester umgesetzt.

Ziel des Projekts ist die Entwicklung eines Prototyps, der klassische Routingfunktionen mit Wetterinformationen verbindet. Die Anwendung nutzt OpenStreetMap-Daten zur Erstellung eines Wegenetzes und kombiniert dieses mit Wetterdaten von MeteoSwiss. Dadurch kann eine Route nicht nur anhand von Distanz oder Reisezeit berechnet, sondern zusätzlich anhand wetterbezogener Einflüsse wie Niederschlag bewertet werden.

Im Zentrum steht die Frage, wie Wetterdaten in eine Geodateninfrastruktur integriert werden können und wie daraus ein Routingmodell entsteht, das für bestimmte Wetterbedingungen geeignete Wege ermittelt, damit Nutzende möglichst trocken ans Ziel gelangen.

### Projektteam

Studierende:

- Tobias Schulthess (GitHub-User: asterixgis)
- Ignaz Kuczynski (GitHub-User: calgon854)

Betreuung:

- Pia Bereuter
- Stefan Eberlein
- Carolin Bronowicz

## Aufgabenstellung und Fragestellung

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

## Datenquellen

Das Projekt verwendet zwei zentrale Datengrundlagen: OpenStreetMap für das Wegenetz und Wetterdaten von MeteoSwiss für die wetterabhängige Bewertung der Route.

### OpenStreetMap

Die Strassen- und Wegenetze werden aus [OpenStreetMap](https://www.openstreetmap.org/) bezogen und mit OSMnx als Routinggraph verarbeitet. OpenStreetMap liefert dabei die geometrische und topologische Grundlage für die Routenberechnung, zum Beispiel Wege, Knoten, Kantenlängen und weitere Attribute des Verkehrsnetzes.

Die Daten von OpenStreetMap stehen unter der [Open Database License (ODbL)](https://www.openstreetmap.org/copyright). Bei der Verwendung ist die entsprechende Attribution an OpenStreetMap und die Mitwirkenden zu beachten.

### MeteoSwiss

Die Wetterdaten stammen aus dem Open-Data-Angebot von [MeteoSwiss](https://www.meteoschweiz.admin.ch/service-und-publikationen/service/open-data.html). Verwendet werden numerische Vorhersagedaten des Modells [ICON-CH1-EPS](https://opendatadocs.meteoswiss.ch/de/e-forecast-data/e2-e3-numerical-weather-forecasting-model), das Wetterinformationen für die Schweiz und das nahe Umfeld in hoher räumlicher Auflösung bereitstellt.

Für das Routing ist insbesondere der Niederschlag relevant. Im Projekt wird dafür die Forecast-Variable `TOT_PREC` verwendet. Die Daten werden aus dem MeteoSwiss-OGD-Angebot bezogen, für die Anwendung aufbereitet und projektintern als NetCDF-Dateien gespeichert. Diese NetCDF-Dateien bilden anschliessend die Grundlage für die wetterabhängige Bewertung einzelner Kanten im Routinggraphen.

Verwendete MeteoSwiss-Collection:

```text
ch.meteoschweiz.ogd-forecasting-icon-ch1
```

Weitere Informationen (Projektintern):

- [Wetterdaten Dokumentation](weather-data.md)
- [Routing-Logik Dokumentation](routing.md)

Weitere Informationen (MeteoSwiss):

- [MeteoSwiss Open Data Dokumentation](https://opendatadocs.meteoswiss.ch/)
- [MeteoSwiss STAC Collection ICON-CH1-EPS](https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-forecasting-icon-ch1)

## Umsetzung

Die Umsetzung besteht aus mehreren Komponenten, die zusammen eine einfache Geodateninfrastruktur für wetterabhängiges Routing bilden.

Aus OpenStreetMap-Daten wird ein Routinggraph aufgebaut, dessen Kanten mit geometrischen und topologischen Informationen versehen sind. Die Wetterdaten von MeteoSwiss werden separat bezogen, verarbeitet und in einem für die Anwendung geeigneten Format gespeichert. Anschliessend werden die Niederschlagsinformationen räumlich und zeitlich den Kanten des Routinggraphen zugeordnet.

Die Routinglogik nutzt diese Informationen, um verschiedene Routenvarianten zu berechnen und zu vergleichen. Neben klassischen Kriterien wie Distanz oder Reisezeit kann dadurch auch der erwartete Niederschlag entlang einer Route berücksichtigt werden.

Für Routinganfragen stellt das Projekt eine FastAPI-Schnittstelle bereit. Ein lokales Frontend ermöglicht die Auswahl von Startpunkt, Zielpunkt und Routingparametern. Damit kann der Prototyp demonstrieren, wie wetterabhängige Informationen in eine Routingentscheidung einfliessen.

## Reflektion

<span style="color:red">Dieser Abschnitt wird noch ergänzt. </span>

Mögliche Punkte für die spätere Reflektion:

- Welche Teile des Prototyps haben gut funktioniert?
- Welche technischen Herausforderungen gab es bei der Verarbeitung der Wetterdaten?
- Wie gut eignet sich `TOT_PREC` als Kriterium für wetterabhängiges Routing?
- Welche Einschränkungen ergeben sich durch räumliche und zeitliche Auflösung der Wetterdaten?
- Wie zuverlässig ist die Zuordnung von Niederschlagswerten zu einzelnen Kanten?
- Welche Erweiterungen wären für eine produktive Anwendung notwendig?
- Welche alternativen Wetterparameter könnten zusätzlich berücksichtigt werden?

## Lizenz

Das Projekt ist als Open-Source-Projekt vorgesehen.
