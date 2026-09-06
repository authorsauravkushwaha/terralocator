"""
Location provider for TerraLocator.

Reads REAL GPS from the phone's own GPS chip via Termux:API's
`termux-location` command. This needs:
  1. The Termux app (from F-Droid — the Play Store build is deprecated
     and can't install add-on packages properly)
  2. The Termux:API *app* (also F-Droid) plus the `termux-api` package
     inside Termux: `pkg install termux-api`
  3. Android location permission granted once, the first time it's used

Crucially: `termux-location` talks directly to the phone's GPS hardware.
It does NOT need mobile data, WiFi, or cell signal to get a fix — that is
the entire point of satellite positioning; GPS satellites broadcast to
any receiver, unconditionally. Two honest, physical (not software)
limitations remain: a first fix can take longer without a data
connection to download orbital "assistance" data, and thick jungle
canopy or narrow canyons can weaken or block the satellite signal,
because GPS still needs line-of-sight to the sky.

On a machine without Termux (a regular PC, for development), this module
falls back to a manual coordinate you provide, so the rest of the app is
fully testable without a phone.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .geomath import Coordinate

MANUAL_OVERRIDE_PATH = Path.home() / ".terralocator" / "manual_location.json"


@dataclass
class LocationFix:
    lat: float
    lon: float
    accuracy_m: Optional[float] = None
    altitude_m: Optional[float] = None
    bearing_deg: Optional[float] = None   # device compass heading, if available
    speed_mps: Optional[float] = None
    provider: str = "unknown"             # "gps" | "manual"
    fetched_at: str = ""

    def coordinate(self) -> Coordinate:
        return Coordinate(lat=self.lat, lon=self.lon)

    def to_dict(self) -> dict:
        return asdict(self)


def _termux_available() -> bool:
    return shutil.which("termux-location") is not None


def _safe_json_object(raw: str) -> Optional[dict]:
    """Termux:API is supposed to print pure JSON, but some devices add a
    stray blank line or warning around it. Try a straight parse first,
    then fall back to slicing out the outermost {...} before giving up —
    cheap insurance against a real fix being thrown away over whitespace.
    """
    if not raw:
        return None
    raw = raw.strip()
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _parse_termux_location(raw_stdout: str) -> Optional[LocationFix]:
    """Pulled out as its own function so it can be unit-tested against a
    saved sample response, without needing a real phone."""
    data = _safe_json_object(raw_stdout)
    if data is None or "latitude" not in data or "longitude" not in data:
        return None
    return LocationFix(
        lat=data["latitude"],
        lon=data["longitude"],
        accuracy_m=data.get("accuracy"),
        altitude_m=data.get("altitude"),
        bearing_deg=data.get("bearing") or None,
        speed_mps=data.get("speed") or None,
        provider=data.get("provider", "gps"),
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


def _read_termux_location(timeout_s: int = 30) -> Optional[LocationFix]:
    try:
        result = subprocess.run(
            ["termux-location", "-p", "gps", "-r", "once"],
            capture_output=True, text=True, timeout=timeout_s,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return _parse_termux_location(result.stdout)


def _read_manual_override() -> Optional[LocationFix]:
    if not MANUAL_OVERRIDE_PATH.exists():
        return None
    try:
        data = json.loads(MANUAL_OVERRIDE_PATH.read_text(encoding="utf-8"))
        return LocationFix(
            lat=data["lat"], lon=data["lon"], provider="manual",
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def set_manual_location(lat: float, lon: float) -> None:
    """For development on a PC with no GPS chip, or as a last-resort
    fallback if a phone's GPS hardware itself is unavailable."""
    MANUAL_OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANUAL_OVERRIDE_PATH.write_text(json.dumps({"lat": lat, "lon": lon}), encoding="utf-8")


def get_location() -> Optional[LocationFix]:
    """Best available location fix, trying real GPS first.

    Order: Termux GPS (real hardware, zero network needed) -> manual
    override file (desktop development/testing). Returns None if
    nothing is available at all — callers must handle that; a locator
    app that fakes a position when it has none is worse than one that
    honestly says "no fix yet".
    """
    if _termux_available():
        fix = _read_termux_location()
        if fix is not None:
            return fix
    return _read_manual_override()


def get_heading_deg() -> Optional[float]:
    """Best-effort device compass heading in degrees (0 = north), via
    Termux:API's orientation sensor. Not every phone/sensor supports
    this reliably — callers must handle None and fall back to
    GPS-bearing-of-travel or a plain distance readout."""
    if not shutil.which("termux-sensor"):
        return None
    try:
        result = subprocess.run(
            ["termux-sensor", "-s", "orientation", "-n", "1"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    return _parse_termux_sensor_orientation(result.stdout) if result.returncode == 0 else None


def _parse_termux_sensor_orientation(raw_stdout: str) -> Optional[float]:
    data = _safe_json_object(raw_stdout)
    if data is None:
        return None
    try:
        for sensor_data in data.values():
            values = sensor_data.get("values")
            if values:
                return float(values[0]) % 360
    except (AttributeError, ValueError, TypeError):
        return None
    return None
