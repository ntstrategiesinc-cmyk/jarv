# Jarvis

A voice-first personal AI assistant. You can talk to it out loud or type to it; it takes real
actions through tools (managing leads in a spreadsheet, posting photos), remembers you across
restarts, asks before doing anything consequential, and can reach out to you proactively.

Built in Python as one shared "brain" with voice and proactivity as adapters around it. See
[`AGENT.md`](AGENT.md) for the spec.

---

## How to use it

Open **PowerShell** first: press the **Windows key**, type `powershell`, press **Enter**.
Then copy one of the commands below, right-click in the window to paste, and press **Enter**.

### 🎙️ Talk to it (voice)

```
& "C:\Users\tolno\jarv\.venv\Scripts\python.exe" "C:\Users\tolno\jarv\run_voice.py"
```

Then:
1. Press **Enter** to start talking
2. Say what you want (e.g. *"add a lead named Dana for roofing"*)
3. Press **Enter** again to stop
4. It shows `you (heard) > …` so you can see it understood you
5. If the action is consequential, it asks `allow? [y/N]` — type **y** and Enter
6. It **speaks** the result back
7. Type **q** then Enter to quit

### ⌨️ Type to it (text)

```
& "C:\Users\tolno\jarv\.venv\Scripts\python.exe" "C:\Users\tolno\jarv\run_text.py"
```

Type messages normally. Type `exit` to quit. The text version is always available and is the
best way to use Jarvis when you don't want to talk.

### 💓 The proactive loop (optional)

```
& "C:\Users\tolno\jarv\.venv\Scripts\python.exe" "C:\Users\tolno\jarv\run_heartbeat.py"
```

Runs in its own window and checks things on a schedule, holding anything noteworthy in an inbox.
Leave it running; press **Ctrl-C** to stop. See what it surfaced with `/inbox` in the text app.

### 📊 The dashboard (optional)

```
& "C:\Users\tolno\jarv\.venv\Scripts\python.exe" "C:\Users\tolno\jarv\run_dashboard.py"
```

Opens a web page (at `http://127.0.0.1:8765`) — a glowing Stark/JARVIS-style HUD showing the
proactive inbox, recent activity, model cost, your leads, and what Jarvis remembers, with buttons
to **dismiss** items and **pause/resume** Jarvis (click the arc-reactor core to toggle).

It also has a **Console** where you can **talk to Jarvis right in the browser**:
- **Type** a message and press Enter, or
- Click **🎤 Talk** to speak — it records your mic, transcribes it, and Jarvis **replies out loud**
  in the page. (Your browser will ask for microphone permission the first time — click Allow.)

When Jarvis wants to do something consequential, **Approve/Deny** buttons appear in the page (the
same confirmation gate). Chat needs `ANTHROPIC_API_KEY`; the 🎤 Talk button needs `DEEPGRAM_API_KEY`
and `ELEVENLABS_API_KEY` (it hides itself if those aren't set). The rest of the panel works without
any keys.

Refreshes itself every few seconds. Runs on your computer only (localhost), never online.
Press **Ctrl-C** in the window to stop it.

---

## Commands (type these in the text app)

| Command | What it does |
|---|---|
| `/inbox` | Show items the proactive loop has surfaced for you |
| `/dismiss <id>` or `/dismiss all` | Clear inbox items |
| `/pause` / `/resume` | Pause / resume all proactive behavior (the kill switch) |
| `/status` | Show whether proactive is active + this session's model cost |
| `/audit` | Show the recent activity log |
| `/help` | List commands |
| `exit` | Quit |

---

## What it can do (tools)

- **Leads** — add, list, search, and summarize leads in `leads.xlsx` (open it in Excel any time).
- **Post a photo** — to Instagram + Facebook (needs the one-time Meta setup below).
- **Memory** — remembers durable facts about you; edit `jarvis/memory/memory.md` by hand any time.

Anything that posts publicly, contacts people, spends, deletes, or changes a setting **always asks
first** — every time. Approving one action never auto-approves the next.

---

## Settings

- **`config.toml`** — editable settings: which voice, the talk mode, quiet hours, which tools need
  confirmation, the proactive checks, etc. No code editing required.
- **`.env`** — your secret API keys (never shared, never committed to git).

A couple of useful knobs in `config.toml`:
- `[voice] input_mode` — `"enter"` (press Enter to talk; most reliable) or `"ptt"` (hold a key).
- `[voice] elevenlabs_voice_id` — the voice Jarvis speaks with.

---

## Troubleshooting voice

If voice acts up, these standalone tests isolate the problem (run them the same way as above,
swapping the filename):

- `hear_test.py` — just makes Jarvis speak. Confirms your **speakers** work.
- `mic_test.py` — records you for 4 seconds and prints what it heard. Confirms your **microphone**.
- `diagnose_voice.py` — tests speaker, mic, and keyboard together.

Common fixes:
- **No sound** → check Windows volume and the selected output device.
- **Mic level shows 0** → Windows **Settings → Privacy & security → Microphone** must allow desktop
  apps; or the wrong input device is selected.

---

## Enabling real photo posting (one-time Meta setup)

The `post_photo` tool is built but inactive until you set up Meta access:

1. Create a Meta **app** (Business type) at [developers.facebook.com](https://developers.facebook.com).
2. Have a **Facebook Page** and an **Instagram Business account linked to that Page**.
3. Grant permissions: `pages_manage_posts`, `pages_read_engagement`, `instagram_basic`,
   `instagram_content_publish`.
4. Get a **long-lived Page access token**.
5. Put `META_PAGE_TOKEN`, `META_PAGE_ID`, and `META_IG_USER_ID` in your `.env`.

Note: Instagram requires a **public image URL** (it can't post a local file); Facebook accepts either.

---

## For developers

**Architecture — one shared agent core, many adapters:**

```
jarvis/
  core/        the brain: agent loop, provider seam, conversation, system prompt
  tools/       capabilities: registry + leads, social, memory tools
  rails/       safety: confirmation gate, audit log, kill switch, prompt-injection defense
  memory/      durable facts (memory.md)
  adapters/    ways in/out: text REPL, voice (push-to-talk + keyboard-free)
  heartbeat/   proactive loop: scheduler, checks, dismissible inbox, quiet hours
  dashboard/   local Flask web panel reading the shared state files
  app.py       build_core(): assembles the one core all entry points share
run_text.py / run_voice.py / run_heartbeat.py / run_dashboard.py   entry points
```

The model provider, speech-to-text, and text-to-speech each sit behind a thin seam so any one can
be swapped without touching the rest. Adding a capability means writing one self-contained tool and
registering it — the agent loop never changes.

**Setup from scratch:**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item .env.example .env   # then fill in your API keys
```

Requires Python 3.11+. Keys needed: `ANTHROPIC_API_KEY` (always), plus `DEEPGRAM_API_KEY` and
`ELEVENLABS_API_KEY` for voice.
