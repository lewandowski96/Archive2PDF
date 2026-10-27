#!/usr/bin/env python3
"""
Launcher for ComicFlux Lossless Comic to PDF Converter Web App.
Runs the local server and automatically opens the user interface in the default browser.
"""

import sys
import os
import time
import threading
import webbrowser
import uvicorn

PORT = 8765
HOST = "127.0.0.1"
URL = f"http://{HOST}:{PORT}"

def open_browser():
    # Short delay to allow the server socket to bind
    time.sleep(1.0)
    print(f"\n🌐 Opening ComicFlux in your default browser: {URL}\n")
    webbrowser.open(URL)

def main():
    print("=" * 60)
    print("  🚀 Starting ComicFlux Lossless Comic Converter Studio")
    print(f"  📍 Web UI: {URL}")
    print("=" * 60)

    # Launch browser in a background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Start FastAPI server
    uvicorn.run("app:app", host=HOST, port=PORT, log_level="info")

if __name__ == "__main__":
    main()
