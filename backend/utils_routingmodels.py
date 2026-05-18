import heapq

import osmnx as ox

from utils_forecast import (
    compute_rain_adjusted_cost,
    get_forecast_from_grid,
    get_forecast_grid,
)


ADVANCED_FORECAST_BUCKET_SECONDS = 300  # 5 Minuten


def static_weather_dijkstra(G, start_node, end_node, start_time, speed, ds, nc_file_timestamp, sensibility):
    forecast_grid = get_forecast_grid(
        ds,
        file_timestamp=nc_file_timestamp,
        target_timestamp=start_time,
        interpolate=False,
    )

    for u, v, k, data in G.edges(keys=True, data=True):
        forecast = get_forecast_from_grid(data, forecast_grid)
        data["forecast"] = forecast
        data["cost"] = compute_rain_adjusted_cost(data["length"], forecast, sensibility)
        data["travel_time"] = int(data["length"] / speed)

    route = ox.routing.shortest_path(G, start_node, end_node, weight="cost")

    return route


def _bucket_timestamp(timestamp, bucket_seconds=ADVANCED_FORECAST_BUCKET_SECONDS):
    return int(round(timestamp / bucket_seconds) * bucket_seconds)


def td_weather_dijkstra(G, start_node, end_node, start_timestamp, speed, ds, nc_file_timestamp, sensibility):
    """
    Findet den kürzesten Pfad mit zeitabhängigen Wetterdaten.

    Forecast-Grids werden pro Zeitfenster gecacht, damit xarray nicht für jede
    einzelne Kante erneut interpolieren muss.
    """
    # Dijkstra arbeitet hier auf Zuständen aus Knoten und Zeitpunkt.
    start_state = (start_node, start_timestamp)
    dist = {start_state: 0}
    parent = {}
    parent_edge = {}
    pq = [(0, start_node, start_timestamp)]
    forecast_grid_cache = {}

    # Default-Werte, damit route_to_gdf auch nicht besuchte Parallelkanten lesen kann.
    for u, v, k, edge_data in G.edges(keys=True, data=True):
        edge_data["forecast"] = edge_data.get("forecast", 0.0)
        edge_data["cost"] = edge_data.get("cost", edge_data["length"])
        edge_data["travel_time"] = edge_data.get("travel_time", int(edge_data["length"] / speed))

    def get_cached_forecast_grid(target_timestamp):
        # Zeitpunkte werden gebündelt, damit weniger Forecast-Grids entstehen.
        bucket_timestamp = max(_bucket_timestamp(target_timestamp), nc_file_timestamp)
        if bucket_timestamp not in forecast_grid_cache:
            forecast_grid_cache[bucket_timestamp] = get_forecast_grid(
                ds,
                file_timestamp=nc_file_timestamp,
                target_timestamp=bucket_timestamp,
                interpolate=True,
            )
        return forecast_grid_cache[bucket_timestamp]

    while pq:
        cost, current_node, current_timestamp = heapq.heappop(pq)

        if (current_node, current_timestamp) in dist and cost > dist[(current_node, current_timestamp)]:
            continue

        if current_node == end_node:
            # Ziel erreicht: Pfad direkt aus den gespeicherten Vorgängern rekonstruieren.
            end_state = (current_node, current_timestamp)
            path = [end_state[0]]
            current_state = end_state

            while current_state != start_state:
                if current_state not in parent:
                    return []

                u, v, k, forecast, edge_cost, travel_time = parent_edge[current_state]
                edge_data = G.edges[u, v, k]
                edge_data["forecast"] = forecast
                edge_data["cost"] = edge_cost
                edge_data["travel_time"] = travel_time

                current_state = parent[current_state]
                path.append(current_state[0])

            path.reverse()
            return path

        for u, v, k, edge_data in G.edges(current_node, keys=True, data=True):
            edge_length = edge_data["length"]
            travel_time = int(edge_length / speed)
            arrival_timestamp = current_timestamp + travel_time

            forecast_grid = get_cached_forecast_grid(arrival_timestamp)
            forecast = get_forecast_from_grid(edge_data, forecast_grid)
            rain_adjusted_cost = compute_rain_adjusted_cost(edge_length, forecast, sensibility)
            new_cost = cost + rain_adjusted_cost

            # Besseren Zustand merken und für die spätere Rekonstruktion verknüpfen.
            if (v, arrival_timestamp) not in dist or new_cost < dist[(v, arrival_timestamp)]:
                next_state = (v, arrival_timestamp)
                current_state = (current_node, current_timestamp)

                dist[next_state] = new_cost
                parent[next_state] = current_state
                parent_edge[next_state] = (u, v, k, forecast, rain_adjusted_cost, travel_time)

                edge_data["forecast"] = forecast
                edge_data["cost"] = rain_adjusted_cost
                edge_data["travel_time"] = travel_time

                heapq.heappush(pq, (new_cost, v, arrival_timestamp))

    print(f"Warnung: Kein Pfad von {start_node} zu {end_node} gefunden")
    return []
