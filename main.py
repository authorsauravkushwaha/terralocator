#!/usr/bin/env python3
"""
TerraLocator — run with:  python3 main.py

The app automatically pulls your phone's real GPS location every time
it needs it — you never type coordinates in by hand on Android. This
script also grabs one location fix right at startup and prints it to
the terminal, so you get immediate proof it's working before you even
open the browser.

First-time Android/Termux setup:
    pkg install python termux-api git
    (install the separate "Termux:API" app too -- from F-Droid, the SAME
     source as your Termux app itself; mixing F-Droid Termux with a
     Play Store Termux:API, or vice versa, is the #1 reason GPS silently
     fails to work)
    termux-setup-storage
    python3 main.py

Then open the printed address in a browser on the same phone. Nothing
here needs the internet at runtime -- it's all talking to itself on
localhost.
"""
import sys

from terralocator import location as location_module
from terralocator.server import run_server


def print_startup_diagnostics() -> None:
    print("TerraLocator -- checking your phone's GPS...")
    fix = location_module.get_location()
    if fix is None:
        print("  No GPS fix received yet. This is expected on a plain PC.")
        print("  On Android, if you expected a real fix, check:")
        print("    1. Termux AND Termux:API are both installed from the SAME source")
        print("       (both from F-Droid is the reliable combination)")
        print("    2. You've granted Android's location permission (it may be waiting on you)")
        print("    3. `pkg install termux-api` has actually been run inside Termux")
        print("    4. Run `termux-location` by itself in Termux to see the raw result --")
        print("       if that alone doesn't return coordinates, the app can't either.")
        print("  The web page will keep retrying automatically every few seconds.")
    else:
        acc = f" (+/-{fix.accuracy_m:.0f} m)" if fix.accuracy_m else ""
        print(f"  Got a real {fix.provider.upper()} fix: {fix.lat:.5f}, {fix.lon:.5f}{acc}")
        heading = location_module.get_heading_deg()
        if heading is not None:
            print(f"  Compass heading: {heading:.0f} degrees")
    print()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print_startup_diagnostics()
    run_server(port=port)
