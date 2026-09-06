"""
Pure math: distance and bearing between two GPS coordinates.

This is the entire "navigation" in TerraLocator — there is no routing,
no road-following, no turn-by-turn. In a place with no road network
(a jungle, open ocean, desert) that's not a missing feature, it's how
real wilderness/marine navigation has always worked: you know where you
are, you know where you want to be, and you get a straight-line distance
and compass bearing. A map plus a compass. Nothing here needs internet,
a map server, or GPS assistance data — it's just spherical trigonometry.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_RADIUS_M = 6_371_000.0  # mean Earth radius in metres


@dataclass(frozen=True)
class Coordinate:
    lat: float
    lon: float

    def __post_init__(self):
        if not (-90.0 <= self.lat <= 90.0):
            raise ValueError(f"Latitude must be between -90 and 90, got {self.lat}")
        if not (-180.0 <= self.lon <= 180.0):
            raise ValueError(f"Longitude must be between -180 and 180, got {self.lon}")


def haversine_distance_m(a: Coordinate, b: Coordinate) -> float:
    """Great-circle distance between two points, in metres."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def initial_bearing_deg(a: Coordinate, b: Coordinate) -> float:
    """Compass bearing (0-360, 0 = true north) to travel from a to b
    in a straight line at the start of the journey."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def bearing_to_compass(bearing_deg: float) -> str:
    """16-point compass label for a bearing, e.g. 'NNE'."""
    directions = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
    ]
    index = round(bearing_deg / 22.5) % 16
    return directions[index]


def format_distance(metres: float) -> str:
    if metres < 1000:
        return f"{metres:.0f} m"
    return f"{metres / 1000:.2f} km"


@dataclass(frozen=True)
class NavigationInfo:
    distance_m: float
    bearing_deg: float
    compass: str

    def summary(self) -> str:
        return f"{format_distance(self.distance_m)} @ {self.bearing_deg:.0f}\u00b0 ({self.compass})"


def navigate(here: Coordinate, target: Coordinate) -> NavigationInfo:
    dist = haversine_distance_m(here, target)
    bearing = initial_bearing_deg(here, target)
    return NavigationInfo(distance_m=dist, bearing_deg=bearing, compass=bearing_to_compass(bearing))
