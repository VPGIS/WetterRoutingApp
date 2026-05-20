---
title: About
---

# About

Diese Seite beschreibt den Projektkontext, die Fragestellung, das Team und die verwendeten Datenquellen. Technische Details sind in [Architektur](architecture.html), [Routing-Logik](routing.html) und [Wetterdaten](weather-data.html) ausgelagert.

## Projektübersicht

Die Wetter Routing App entstand im Rahmen des Vertiefungsprofils 4230 Geoinformatik Raumanalyse I an der Fachhochschule Nordwestschweiz FHNW. Das Projekt entstand am Institut Geomatik IGEO im Studiengang BSc Geomatik und wurde im 4. und 6. Semester umgesetzt.

Ziel des Projekts ist die Entwicklung eines Prototyps, der klassische Routingfunktionen mit Wetterinformationen verbindet. Die Anwendung nutzt OpenStreetMap-Daten zur Erstellung eines Wegenetzes und kombiniert dieses mit Wetterdaten von MeteoSwiss. Dadurch kann eine Route nicht nur anhand von Distanz oder Reisezeit berechnet, sondern zusätzlich anhand wetterbezogener Einflüsse wie Niederschlag bewertet werden.

Im Zentrum steht die Frage, wie Wetterdaten in eine Geodateninfrastruktur integriert werden können und wie daraus ein Routingmodell entsteht, das für bestimmte Wetterbedingungen geeignete Wege ermittelt, damit Nutzende möglichst trocken ans Ziel gelangen.

## Projektteam

Studierende:

- Tobias Schulthess (GitHub-User: `asterixgis`)
- Ignaz Kuczynski (GitHub-User: `calgon854`)

Betreuung:

- Pia Bereuter
- Stefan Eberlein
- Carolin Bronowicz

## Aufgabenstellung und Fragestellung

Im Modul sollte eine eigene geoinformatische Fragestellung entwickelt und als Projektarbeit umgesetzt werden. Die Aufgabe bestand darin, ein Thema zu wählen, dazu ein fachliches und technisches Konzept zu erarbeiten und dieses in einer funktionierenden Geodateninfrastruktur umzusetzen.

Für dieses Projekt wurde die Fragestellung auf wetterabhängiges Routing ausgerichtet:

> **Wie kann eine Routinganwendung so erweitert werden, dass Wetterdaten, insbesondere Niederschlag, in die Bewertung und Auswahl einer Route einfliessen?**

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

Die Strassen- und Wegenetze werden aus [OpenStreetMap](https://www.openstreetmap.org/) bezogen und mit OSMnx als Routinggraph verarbeitet. OpenStreetMap liefert die geometrische und topologische Grundlage für die Routenberechnung, zum Beispiel Wege, Knoten, Kantenlängen und weitere Attribute des Verkehrsnetzes.

Die Daten von OpenStreetMap stehen unter der [Open Database License (ODbL)](https://www.openstreetmap.org/copyright). Bei der Verwendung ist die entsprechende Attribution an OpenStreetMap und die Mitwirkenden zu beachten.

### MeteoSwiss

Die Wetterdaten stammen aus dem Open-Data-Angebot von [MeteoSwiss](https://www.meteoschweiz.admin.ch/service-und-publikationen/service/open-data.html). Verwendet werden numerische Vorhersagedaten des Modells [ICON-CH1-EPS](https://opendatadocs.meteoswiss.ch/de/e-forecast-data/e2-e3-numerical-weather-forecasting-model), das Wetterinformationen für die Schweiz und das nahe Umfeld in einer räumlichen Auflösung von 1km bereitstellt.

Für das Routing ist insbesondere der Niederschlag relevant. Im Projekt wird die Forecast-Variable `TOT_PREC` bezogen und daraus für die Routenbewertung stündlicher Niederschlag abgeleitet. Die Daten werden aus dem MeteoSwiss-OGD-Angebot bezogen, für die Anwendung aufbereitet und projektintern als NetCDF-Dateien gespeichert.

Verwendete MeteoSwiss-Collection:

```text
ch.meteoschweiz.ogd-forecasting-icon-ch1
```

Weitere Informationen:

- [Wetterdaten](weather-data.html)
- [Routing-Logik](routing.html)
- [MeteoSwiss Open Data Dokumentation](https://opendatadocs.meteoswiss.ch/)
- [MeteoSwiss STAC Collection ICON-CH1-EPS](https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-forecasting-icon-ch1)

## Umsetzung

Die Umsetzung besteht aus mehreren Komponenten, die zusammen eine einfache Geodateninfrastruktur für wetterabhängiges Routing bilden.

Aus OpenStreetMap-Daten wird ein Routinggraph aufgebaut, dessen Kanten mit geometrischen und topologischen Informationen versehen sind. Die Wetterdaten von MeteoSwiss werden separat bezogen, verarbeitet und in einem für die Anwendung geeigneten Format gespeichert. Anschliessend werden die Niederschlagsinformationen räumlich und zeitlich den Kanten des Routinggraphen zugeordnet.

Die Routinglogik nutzt diese Informationen, um verschiedene Routenvarianten zu berechnen und zu vergleichen. Neben klassischen Kriterien wie Distanz oder Reisezeit kann dadurch auch der erwartete Niederschlag entlang einer Route berücksichtigt werden.

Für Routinganfragen stellt das Projekt eine FastAPI-Schnittstelle bereit. Ein lokales Frontend ermöglicht die Auswahl von Startpunkt, Zielpunkt und Routingparametern. Damit kann der Prototyp demonstrieren, wie wetterabhängige Informationen in eine Routingentscheidung einfliessen.

Weitere Details:

- [Architektur](architecture.html)
- [Startup](startup.html)
- [Routing-Logik](routing.html)
- [Wetterdaten](weather-data.html)

## Reflektion

Am Anfang des Projekts stand der Wunsch, ein Thema zu bearbeiten, das unsere gemeinsamen Interessen verbindet und gleichzeitig einen klaren Raumbezug hat. Als erste Idee wurde ein Ansatz mit Schneedaten vom [WSL-Institut für Schnee- und Lawinenforschung SLF](https://www.slf.ch) verfolgt, doch bei weiterer Recherche sind wir über den ICON-CH1-EPS Datensatz gestolpert. Da wir beide gerne auf dem Fahrrad unterwegs sind, rückte die Idee einer Routinganwendung schnell in den Vordergrund. Dadurch entstand der Gedanke, diese Daten nicht nur ergänzend anzuzeigen, sondern direkt in die Routenberechnung einzubeziehen.

So stand die Idee einmal. Doch wie setzt man solch ein Projekt um? Der Start war zunächst holprig. Wir mussten abschätzen, welche Technologien sich für unser Vorhaben eignen, wie die verfügbaren Daten aufgebaut sind und welche Anforderungen sich daraus für die Umsetzung ergeben. Viele richtungsweisende Entscheidungen schienen anzustehen, ohne ein fundiertes Wissen darüber zu haben. Dies wirkte zu Beginn fast schon lähmend. Hier half nur Googeln, Dokumentationen zu überfliegen und Examples auszuprobieren, um in möglichst viele Richtungen blicken und die «ceiling height» eines Tools abschätzen zu können. Dies war ein grosses Learning, wenn es einen fast schon überwältigt: sich einen kurzen Überblick über die Tools und Technologien verschaffen und dann auf leichten Füssen eines nach dem anderen durchgehen und ausprobieren. So kann man am ehesten das Potenzial abschätzen. Wenn es nicht klappt, ist das auch eine Information.

Eine erste wichtige Entscheidung betraf die Routingtechnologie. Zu Beginn haben wir PG-Routing als mögliche Grundlage betrachtet, da es im Bereich geodatenbasiertes Routing naheliegend ist. In den ersten Tests zeigte sich jedoch, wie mühselig es ist, OSM-Daten samt Topologie einzulesen. Ebenfalls zeichnete sich ab, dass ein Routing mit dynamischen Kosten nur sehr schwer umzusetzen ist. Hier hat OSMnx in Kombination mit NetworkX überzeugt. Diese Lösung bot uns mehr Flexibilität beim Aufbau, der Bearbeitung und der Analyse des Routinggraphen. Nachdem erste Graphen geladen und einfache Routen berechnet werden konnten, wurde das Projekt technisch greifbarer.

Auch der Bezug und die Verarbeitung der Wetterdaten stellten eine grosse Herausforderung dar. Die MeteoSwiss-Daten mussten zunächst verstanden, heruntergeladen und in ein geeignetes Format überführt werden. Besonders anspruchsvoll war, dass einige Werkzeuge eine Linux-Umgebung voraussetzen. Zusätzlich mussten wir klären, welche Variable für unser Ziel geeignet ist und wie aus den vorhandenen Vorhersagedaten stündliche Niederschlagsinformationen abgeleitet werden können.

Ein zentraler und fachlich besonders spannender Teil des Projekts war die Verknüpfung der Wetterdaten mit den Kanten des Graphen. Der Graph besteht aus zehntausenden von Kanten, welche alle mit der Zelle verschnitten werden müssten, um ihnen die Daten der Wetterzelle zuzuweisen. Hier gäbe es ein grosses Performance-Problem. Durch viel Skizzieren konnte die räumliche Verknüpfung durch eine attributive ersetzt werden, was am Ende den gleichen Effekt hat, nur performanter.

Währenddem die Routinglogik erarbeitet wurde, wurde auch die Vorprozessierung und das Frontend umgesetzt. Der Einsatz von KI-Werkzeugen war dabei eine grosse Unterstützung. Die grössere Herausforderung lag weniger darin, eine Webseite aufzubauen, sondern ein möglichst schlichtes, verständliches und funktionales Layout zu gestalten. Besonders das Rendern des Regens war anspruchsvoll, da hier sowohl die räumliche als auch die zeitliche Komponente beachtet werden musste.

Eine weitere Herausforderung bestand darin, Frontend, API und Routinglogik sauber miteinander zu verbinden. Nachdem die einzelnen Komponenten in sich funktionierten, mussten die Schnittstellen definiert und die Abläufe zusammengeführt werden. Dabei half es, den gesamten Prozess zuerst als Dummy aufzubauen. So konnten die einzelnen Puzzleteile wie Routinggraph, Wetterdaten, API-Call, Routenberechnung und Visualisierung Schritt für Schritt eingesetzt werden. Diese Vorgehensweise machte sichtbar, wo noch die z.B. die Datenvorprozessierung der Meteodaten angepasst oder Funktionen ergänzt werden mussten.

Auch die Dokumentation war aufwändiger als erwartet. Eine Schwierigkeit bestand darin, die Dokumentation so aufzubauen, dass sie vollständig ist, aber keine unnötigen Wiederholungen enthält. KI war auch hier hilfreich, um Abläufe aus dem Code in verständliche Texte zu übertragen und erste Formulierungen zu erarbeiten. Trotzdem zeigte sich, dass der Feinschliff, die Kontrolle der Inhalte und eine konsistente Struktur viel Zeit benötigen.

Insgesamt sind wir mit dem Projekt zufrieden. Der entwickelte Prototyp zeigt, dass Wetterdaten grundsätzlich in eine Routingentscheidung integriert werden können und dass dadurch neue, praxisnahe Fragestellungen entstehen. Gleichzeitig wurden auch Grenzen sichtbar. Dazu gehören unter anderem die räumliche und zeitliche Auflösung der Wetterdaten. Auch ist je nach Regenkonstellation ein wetterbasiertes Routing nur bedingt hilfreich. Für eine produktive Anwendung wären weitere Optimierungen, zusätzliche Wetterparameter und eine stabilere Datenverarbeitung notwendig.

Das Projekt war für uns sehr lehrreich. Wir konnten Erfahrungen mit Routinggraphen, Wetterdaten, APIs und Frontend-Entwicklung sammeln. Besonders wertvoll war die Erkenntnis, dass komplexe Geodatenanwendungen am besten schrittweise entwickelt werden: zuerst mit einfachen Tests, danach mit klaren Skizzen der Abläufe und erst anschliessend mit der Zusammenführung der einzelnen Komponenten. Viele dieser Erfahrungen können wir in zukünftigen Projekten wiederverwenden.

## Lizenz

Das Projekt ist als Open-Source-Projekt vorgesehen.
