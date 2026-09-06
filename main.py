#!/usr/bin/env python3
"""
TerraLocator — run with:  python3 main.py

Then open the printed address (http://127.0.0.1:8765) in a browser —
on your phone, that means Termux's browser or Chrome/Firefox on the
same device. Nothing here needs the internet at runtime; it's all
talking to itself on localhost.

First-time Android/Termux setup:
    pkg install termux-api python
    (install the separate "Termux:API" app from F-Droid too)
    termux-setup-storage
    python3 main.py
"""
import sys

from terralocator.server import run_server

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    run_server(port=port)
