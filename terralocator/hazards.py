"""
Hazard / safe-zone / POI layer for TerraLocator.

READ THIS BEFORE ADDING DATA: this module will never ship pre-loaded
with claims like "this jungle is dangerous" or "this is a safe zone",
because there is no real, globally-verified dataset of that anywhere —
and a hiker who trusts an invented danger marker in an actual remote
area is a person who can get hurt. Every entry has a `verified` flag and
a `source`, and anything not explicitly verified by the app's own user
is treated as informational only, never as a safety guarantee.

The storage format is plain GeoJSON (RFC 7946) — a real, universal GIS
standard — specifically so this file can be opened in QGIS, edited by
hand, merged with OpenStreetMap extracts, or picked up by a future
community project without anyone needing to learn a custom format.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .geomath import Coordinate, haversine_distance_m

HAZARD_TYPES = {"police", "danger", "safe_zone", "poi", "water", "shelter"}


@dataclass
class HazardPoint:
    id: str
    type: str
    lat: float
    lon: float
    title: str
    description: str = ""
    source: str = "user"
    verified: bool = False
    added_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def coordinate(self) -> Coordinate:
        return Coordinate(lat=self.lat, lon=self.lon)

    def to_feature(self) -> dict:
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [self.lon, self.lat]},
            "properties": {
                "id": self.id, "type": self.type, "title": self.title,
                "description": self.description, "source": self.source,
                "verified": self.verified, "added_at": self.added_at,
            },
        }

    @staticmethod
    def from_feature(feature: dict) -> "HazardPoint":
        props = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"][:2]
        return HazardPoint(
            id=props.get("id", str(uuid.uuid4())),
            type=props.get("type", "poi"),
            lat=lat, lon=lon,
            title=props.get("title", "Unnamed point"),
            description=props.get("description", ""),
            source=props.get("source", "unknown"),
            verified=bool(props.get("verified", False)),
            added_at=props.get("added_at", ""),
        )

    @staticmethod
    def new(type: str, lat: float, lon: float, title: str, **kwargs) -> "HazardPoint":
        if type not in HAZARD_TYPES:
            raise ValueError(f"Unknown hazard type {type!r}. Valid types: {sorted(HAZARD_TYPES)}")
        return HazardPoint(id=str(uuid.uuid4()), type=type, lat=lat, lon=lon, title=title, **kwargs)


class HazardLayer:
    """A single region's set of hazard/POI points, backed by one
    GeoJSON file on disk."""

    def __init__(self, path: Path):
        self.path = path
        self.points: List[HazardPoint] = []
        if path.exists():
            self.load()

    def load(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.points = [HazardPoint.from_feature(f) for f in data.get("features", [])]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        collection = {"type": "FeatureCollection", "features": [p.to_feature() for p in self.points]}
        self.path.write_text(json.dumps(collection, indent=2), encoding="utf-8")

    def add(self, point: HazardPoint) -> None:
        self.points.append(point)
        self.save()

    def remove(self, point_id: str) -> bool:
        before = len(self.points)
        self.points = [p for p in self.points if p.id != point_id]
        changed = len(self.points) != before
        if changed:
            self.save()
        return changed

    def near(self, center: Coordinate, radius_m: float) -> List[HazardPoint]:
        return [p for p in self.points if haversine_distance_m(center, p.coordinate()) <= radius_m]

    def by_type(self, type: str) -> List[HazardPoint]:
        return [p for p in self.points if p.type == type]

    def unverified_count(self) -> int:
        return sum(1 for p in self.points if not p.verified)
