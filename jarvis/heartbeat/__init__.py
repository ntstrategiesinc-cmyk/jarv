"""The heartbeat — a background loop that lets Jarvis act without being spoken to.

Separate from the conversation loop so it can later move to an always-on host without a rewrite.
Quiet by default: most checks produce nothing most of the time; only genuinely noteworthy things
surface, and they're held in a durable inbox until the owner sees and dismisses them.
"""
