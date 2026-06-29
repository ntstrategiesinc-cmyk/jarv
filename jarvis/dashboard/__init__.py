"""The dashboard — a local web "face" for Jarvis.

Another adapter that reads the same shared state files (inbox, audit log, kill switch, leads,
memory) the rest of the harness writes, and offers light controls (dismiss, pause/resume). Binds
to localhost only; it is never exposed to the network.
"""
