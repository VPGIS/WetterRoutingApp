import heapq
import osmnx as ox 

from utils_forecast import get_forecast, compute_rain_adjusted_cost


def static_djikstra(G, start_node,end_node,start_time,speed,ds,nc_file_timestamp,sensibility):
    
    for edge in G.edges(keys=True, data=True):
        u, v, k, data = edge
        data["forecast"] = get_forecast(G, ds, u, v, k, 
                                        file_timestamp=nc_file_timestamp, 
                                        target_timestamp=start_time,
                                        interpolate=False)
            
        data['cost'] = compute_rain_adjusted_cost(data['length'], data["forecast"], sensibility)

        data['travel_time'] = int(data['length'] / speed)

    route = ox.routing.shortest_path(G, start_node, end_node, weight='cost')

    return route


def time_dependent_dijkstra(G, start_node, end_node, start_timestamp, speed, ds, nc_file_timestamp, sensibility):
    """
    Findet den kürzesten Pfad mit zeitabhängigen Wetterdaten mittels Dijkstra-Algorithmus.
    
    Der Algorithmus arbeitet im (node, timestamp)-Raum statt nur im node-Raum.
    Dies ermöglicht es, unterschiedliche Kosten für dieselbe Kante zu verschiedenen
    Ankunftszeiten zu modellieren. Die Kosten hängen von der Regenwahrscheinlichkeit
    zum Zeitpunkt der geplanten Ankunft ab.
    
    Parameter
    ----------
    G : networkx.MultiDiGraph
        OSMnx-Graph mit Straßennetzwerk
    start_node : int
        Start-Node-ID aus dem Graphen
    end_node : int
        End-Node-ID aus dem Graphen
    start_timestamp : int
        Unix-Timestamp (Sekunden seit 1970) des Fahrtbeginns
    speed : float
        Reisegeschwindigkeit in m/s
    ds : xarray.Dataset
        Geöffnetes netCDF-Dataset mit Wetterdaten
    nc_file_timestamp : int
        Unix-Timestamp der Wetterdaten-Datei (für Lookup welche Daten verfügbar sind)
    sensibility : float
        Sensibilitätsfaktor für Rain-Penalty (höher = stärker Regen vermeiden)
    
    Returns
    -------
    list
        Sequenz von Node-IDs, die den optimalen Pfad darstellen
    """
    
    # dist speichert die besten bekannten Kosten für jeden (node, timestamp)-State
    # Initialisierung: Startknoten hat Kosten 0 zum Startzeitpunkt
    dist = {}
    dist[(start_node, start_timestamp)] = 0
    
    # parent speichert den Vorgänger-State für Pfad-Rekonstruktion
    # Nachher können wir vom Ziel zum Start zurückverfolgen
    parent = {}
    
    # Priority Queue: (cost, node, timestamp)
    # heapq verarbeitet automatisch kleinste Kosten zuerst (Min-Heap)
    pq = [(0, start_node, start_timestamp)]
    
    # Hauptschleife: solange unverarbeitete States in der Queue sind
    while pq:
        cost, current_node, current_timestamp = heapq.heappop(pq)
        
        # Pruning: Falls wir diesen State bereits mit besseren Kosten besucht haben,
        # überspringen (kann passieren, da alte Einträge noch in Queue sein können)
        if (current_node, current_timestamp) in dist and cost > dist[(current_node, current_timestamp)]:
            continue
        
        # Zieltest: Sobald wir das Ziel erreichen, haben wir den optimalen Pfad gefunden
        # (Dijkstra garantiert Optimalität bei nicht-negativen Kosten)
        if current_node == end_node:
            return _reconstruct_path(parent, start_node, end_node, current_timestamp)
        
        # Exploriere alle ausgehenden Kanten vom aktuellen Knoten
        # In networkx MultiDiGraph: G.edges(node, keys=True, data=True) gibt (u, v, k, data)
        for u, v, k, edge_data in G.edges(current_node, keys=True, data=True):
            # edge_data enthält: 'length', 'geometry', etc.
            edge_length = edge_data['length']  # in Metern
            
            # Berechne Reisedauer für diese Kante
            travel_time = int(edge_length / speed)  # in Sekunden
            
            # Ankunftszeit am nächsten Knoten
            arrival_timestamp = current_timestamp + travel_time
            
            # Berechne Wetter-Kosten basierend auf Ankunftszeit
            # (nicht Startzeit! Das ist der Unterschied zum 'einfach'-Modell)
            forecast = get_forecast(
                G, ds, u, v, k,
                file_timestamp=nc_file_timestamp,
                target_timestamp=arrival_timestamp,  # <-- zeitabhängig!
                interpolate=True  # <-- interpoliere zwischen Zeitschritten
            )
            
            # Berechne Kosten: Fahrzeit + Wetter-Penalty
            rain_adjusted_cost = compute_rain_adjusted_cost(
                edge_length, forecast, sensibility
            )
            
            # Gesamtkosten über diesen Pfad
            new_cost = cost + rain_adjusted_cost
            
            # Relaxation: Falls wir einen besseren Pfad zum Nachbarknoten gefunden haben
            if (v, arrival_timestamp) not in dist or new_cost < dist[(v, arrival_timestamp)]:
                # Aktualisiere beste bekannte Kosten
                dist[(v, arrival_timestamp)] = new_cost
                
                # Speichere Vorgänger für Pfad-Rekonstruktion
                parent[(v, arrival_timestamp)] = (current_node, current_timestamp)
                
                # Füge Nachbarknoten in Priority Queue ein
                heapq.heappush(pq, (new_cost, v, arrival_timestamp))
    
    # Falls Schleife endet ohne Ziel zu erreichen: Kein Pfad möglich
    print(f"Warnung: Kein Pfad von {start_node} zu {end_node} gefunden")
    return []


def _reconstruct_path(parent, start_node, end_node, arrival_timestamp):
    """
    Rekonstruiert den Pfad aus der parent-Tabelle.
    
    Startet beim Ziel und verfolgt die Vorgänger-States zurück zum Start.
    Extrahiert nur die Node-Sequenz (ignoriert Timestamps).
    
    Parameter
    ----------
    parent : dict
        Mapping von (node, timestamp) -> (prev_node, prev_timestamp)
    start_node : int
        Start-Node-ID
    end_node : int
        End-Node-ID
    arrival_timestamp : int
        Ankunftszeit am Ziel
    
    Returns
    -------
    list
        Sequenz von Node-IDs vom Start zum Ziel
    """
    path = []
    current_state = (end_node, arrival_timestamp)
    
    # Verfolge Vorgänger rückwärts bis zum Start
    while current_state in parent:
        node, timestamp = current_state
        path.append(node)
        current_state = parent[current_state]
    
    # Füge Startknoten hinzu und kehre Reihenfolge um
    path.append(start_node)
    path.reverse()
    
    return path