"""The voice adapter — ears and mouth wrapped around the SAME agent core.

Voice changes only how a turn arrives (transcribed speech) and leaves (spoken reply). The brain
in the middle is untouched: session.py feeds transcribed text into Agent.run_turn(), exactly the
entry point the text REPL uses. STT and TTS sit behind their own seams so either vendor can change
in one place.
"""
