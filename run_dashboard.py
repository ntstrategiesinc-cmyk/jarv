#!/usr/bin/env python
"""Launch the Jarvis dashboard — a local web page showing the inbox, activity, cost, leads, and
memory, with pause/resume and dismiss controls.

    python run_dashboard.py

Then open http://127.0.0.1:8765 (it opens automatically). Localhost only — not on the network.
Press Ctrl-C to stop.
"""

from __future__ import annotations

import sys
import threading
import webbrowser

from jarvis.app import force_utf8_console
from jarvis.config import load_config
from jarvis.dashboard.server import create_app

HOST = "127.0.0.1"
PORT = 8765


def main() -> int:
    force_utf8_console()
    config = load_config()
    app = create_app(config)

    url = f"http://{HOST}:{PORT}"
    print(f"{config.persona_name} dashboard at {url}   (Ctrl-C to stop)")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
