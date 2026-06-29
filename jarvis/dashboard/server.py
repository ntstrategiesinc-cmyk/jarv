"""Flask app for the Jarvis dashboard: assembles state from the shared files and serves a small
auto-refreshing page with light controls.
"""

from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, jsonify, request

from ..config import Config
from ..heartbeat.inbox import Inbox
from ..memory.store import MemoryStore
from ..rails.killswitch import KillSwitch
from ..tools.leads import LeadsStore


def _read_audit(path: Path, limit: int = 500) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def _fmt_activity(rec: dict) -> str | None:
    ts = rec.get("ts", "")[11:19]
    kind = rec.get("kind")
    if kind == "tool_run":
        return f"{ts}  ran {rec.get('tool')} ({rec.get('source')}) {'✓' if rec.get('ok') else '✗ FAILED'}"
    if kind == "confirmation":
        return f"{ts}  confirm {rec.get('tool')} ({rec.get('source')}) → {rec.get('decision')}"
    if kind == "event":
        ev = rec.get("event")
        if ev == "heartbeat_surface":
            return f"{ts}  heartbeat surfaced: {rec.get('title')}"
        if ev == "killswitch":
            return f"{ts}  kill switch {rec.get('state')}"
        return f"{ts}  {ev}"
    return None


def _gather_state(config: Config) -> dict:
    state_dir = config.state_dir
    killswitch = KillSwitch(state_dir / "killswitch.json")
    inbox = Inbox(state_dir / "inbox.json")
    memory = MemoryStore(config.memory_path)

    # leads summary
    try:
        leads = LeadsStore(config.leads_workbook_path, config.leads_sheet_name).all()
    except Exception:
        leads = []
    by_status: dict[str, int] = {}
    for lead in leads:
        s = str(lead.get("status") or "unknown")
        by_status[s] = by_status.get(s, 0) + 1

    # audit -> activity + cost
    records = _read_audit(state_dir / "audit.log")
    total_cost = sum(float(r.get("cost_usd", 0) or 0) for r in records if r.get("kind") == "usage")
    turns = sum(1 for r in records if r.get("kind") == "usage")
    activity = [a for a in (_fmt_activity(r) for r in reversed(records)) if a][:30]

    return {
        "paused": killswitch.is_paused(),
        "inbox": inbox.pending(),
        "leads": {"total": len(leads), "by_status": by_status},
        "memory": memory.facts(),
        "activity": activity,
        "cost": {"total_usd": round(total_cost, 4), "turns": turns},
        "persona": config.persona_name,
    }


def create_app(config: Config) -> Flask:
    app = Flask(__name__)
    state_dir = config.state_dir

    @app.get("/")
    def index():
        return PAGE.replace("__NAME__", config.persona_name)

    @app.get("/api/state")
    def api_state():
        return jsonify(_gather_state(config))

    @app.post("/api/pause")
    def api_pause():
        KillSwitch(state_dir / "killswitch.json").pause()
        return jsonify({"ok": True})

    @app.post("/api/resume")
    def api_resume():
        KillSwitch(state_dir / "killswitch.json").resume()
        return jsonify({"ok": True})

    @app.post("/api/inbox/dismiss")
    def api_dismiss():
        data = request.get_json(silent=True) or {}
        target = data.get("id", "all")
        if target != "all":
            try:
                target = int(target)
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": "bad id"}), 400
        n = Inbox(state_dir / "inbox.json").dismiss(target)
        return jsonify({"ok": True, "dismissed": n})

    return app


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__NAME__ — dashboard</title>
<style>
  :root { --bg:#0f1419; --card:#1a2230; --line:#2a3548; --text:#e6edf3; --dim:#8b98a9;
          --accent:#4a9eff; --ok:#3fb950; --warn:#d29922; --bad:#f85149; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text);
         font-family:"Segoe UI",system-ui,sans-serif; font-size:14px; }
  header { display:flex; align-items:center; gap:14px; padding:16px 24px;
           border-bottom:1px solid var(--line); position:sticky; top:0; background:var(--bg); }
  header h1 { font-size:18px; margin:0; letter-spacing:.5px; }
  .pill { padding:3px 10px; border-radius:999px; font-size:12px; font-weight:600; }
  .pill.active { background:rgba(63,185,80,.15); color:var(--ok); }
  .pill.paused { background:rgba(248,81,73,.15); color:var(--bad); }
  .spacer { flex:1; }
  button { font:inherit; cursor:pointer; border:1px solid var(--line); background:var(--card);
           color:var(--text); border-radius:6px; padding:6px 12px; }
  button:hover { border-color:var(--accent); }
  button.danger:hover { border-color:var(--bad); color:var(--bad); }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; padding:24px; max-width:1100px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px; }
  .card h2 { font-size:13px; text-transform:uppercase; letter-spacing:.8px; color:var(--dim);
             margin:0 0 12px; }
  .item { padding:10px 0; border-bottom:1px solid var(--line); display:flex; gap:10px;
          align-items:flex-start; }
  .item:last-child { border-bottom:none; }
  .sev { font-size:11px; font-weight:700; padding:2px 7px; border-radius:4px; flex-shrink:0; }
  .sev.alert { background:rgba(210,153,34,.18); color:var(--warn); }
  .sev.notice { background:rgba(139,152,169,.15); color:var(--dim); }
  .item .body { color:var(--dim); font-size:13px; }
  .muted { color:var(--dim); }
  .activity { font-family:"Cascadia Code",Consolas,monospace; font-size:12.5px; line-height:1.9;
              max-height:340px; overflow:auto; }
  .big { font-size:26px; font-weight:700; }
  .row { display:flex; justify-content:space-between; padding:5px 0; }
  .full { grid-column:1 / -1; }
  a { color:var(--accent); }
</style>
</head>
<body>
<header>
  <h1>__NAME__</h1>
  <span id="status" class="pill active">●</span>
  <div class="spacer"></div>
  <span class="muted" id="updated"></span>
  <button id="toggle" onclick="togglePause()">Pause</button>
</header>

<div class="grid">
  <div class="card">
    <h2>Inbox <span class="muted" id="inboxCount"></span></h2>
    <div id="inbox"></div>
    <div style="margin-top:10px"><button class="danger" onclick="dismiss('all')">Dismiss all</button></div>
  </div>

  <div class="card">
    <h2>Cost &amp; leads</h2>
    <div class="row"><span class="muted">Model cost (logged)</span><span class="big" id="cost">$0</span></div>
    <div class="row"><span class="muted">Model turns</span><span id="turns">0</span></div>
    <hr style="border-color:var(--line);margin:12px 0">
    <div class="row"><span class="muted">Leads total</span><span id="leadsTotal">0</span></div>
    <div id="leadsByStatus" class="muted"></div>
  </div>

  <div class="card full">
    <h2>Recent activity</h2>
    <div class="activity" id="activity"></div>
  </div>

  <div class="card full">
    <h2>What Jarvis remembers</h2>
    <div id="memory" class="muted"></div>
  </div>
</div>

<script>
async function load() {
  try {
    const r = await fetch('/api/state'); const s = await r.json();
    // status
    const st = document.getElementById('status');
    st.className = 'pill ' + (s.paused ? 'paused' : 'active');
    st.textContent = s.paused ? '● PAUSED' : '● ACTIVE';
    document.getElementById('toggle').textContent = s.paused ? 'Resume' : 'Pause';
    // inbox
    const ib = document.getElementById('inbox');
    document.getElementById('inboxCount').textContent = s.inbox.length ? '(' + s.inbox.length + ')' : '';
    ib.innerHTML = s.inbox.length ? '' : '<div class="muted">Nothing waiting.</div>';
    for (const it of s.inbox) {
      const d = document.createElement('div'); d.className = 'item';
      d.innerHTML = `<span class="sev ${it.severity}">${it.severity}</span>
        <div style="flex:1"><div>${esc(it.title)}</div>
        <div class="body">${esc(it.body||'')}</div>
        <div class="muted" style="font-size:11px">${esc(it.ts||'')}</div></div>
        <button onclick="dismiss(${it.id})">Dismiss</button>`;
      ib.appendChild(d);
    }
    // cost & leads
    document.getElementById('cost').textContent = '$' + (s.cost.total_usd||0).toFixed(4);
    document.getElementById('turns').textContent = s.cost.turns;
    document.getElementById('leadsTotal').textContent = s.leads.total;
    document.getElementById('leadsByStatus').textContent =
      Object.entries(s.leads.by_status).map(([k,v]) => `${k}: ${v}`).join('   ') || '';
    // activity
    document.getElementById('activity').innerHTML =
      s.activity.length ? s.activity.map(a => esc(a)).join('<br>') : '<span class="muted">No activity yet.</span>';
    // memory
    document.getElementById('memory').innerHTML =
      s.memory.length ? s.memory.map(m => '• ' + esc(m)).join('<br>') : 'Nothing remembered yet.';
    document.getElementById('updated').textContent = 'updated ' + new Date().toLocaleTimeString();
  } catch (e) { document.getElementById('updated').textContent = 'disconnected'; }
}
function esc(s){ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
async function togglePause() {
  const paused = document.getElementById('status').classList.contains('paused');
  await fetch(paused ? '/api/resume' : '/api/pause', {method:'POST'}); load();
}
async function dismiss(id) {
  await fetch('/api/inbox/dismiss', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({id})}); load();
}
load(); setInterval(load, 3000);
</script>
</body>
</html>"""
