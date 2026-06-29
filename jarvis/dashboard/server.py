"""Flask app for the Jarvis dashboard: assembles state from the shared files and serves a
Stark/JARVIS-style HUD page with light controls.
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
        return f"{ts}  ran {rec.get('tool')} ({rec.get('source')}) {'OK' if rec.get('ok') else 'FAILED'}"
    if kind == "confirmation":
        return f"{ts}  confirm {rec.get('tool')} ({rec.get('source')}) -> {rec.get('decision')}"
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

    try:
        leads = LeadsStore(config.leads_workbook_path, config.leads_sheet_name).all()
    except Exception:
        leads = []
    by_status: dict[str, int] = {}
    for lead in leads:
        s = str(lead.get("status") or "unknown")
        by_status[s] = by_status.get(s, 0) + 1

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
<title>__NAME__ // STARK HUD</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;800&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<style>
  :root{
    --cy:#1fe0ff; --cy2:#37f0ff; --dim:#5a93a8; --bg:#02060c;
    --ok:#19e0ff; --bad:#ff4d63; --warn:#ffc24d;
    --line:rgba(31,224,255,.22); --glow:rgba(31,224,255,.55);
    --panel:rgba(8,26,40,.30);
  }
  *{box-sizing:border-box;}
  html,body{margin:0;height:100%;}
  body{
    background:
      radial-gradient(1200px 700px at 50% 42%, rgba(8,60,90,.30), transparent 60%),
      repeating-linear-gradient(0deg, rgba(31,224,255,.03) 0 1px, transparent 1px 40px),
      repeating-linear-gradient(90deg, rgba(31,224,255,.03) 0 1px, transparent 1px 40px),
      #02060c;
    color:var(--cy); font-family:"Share Tech Mono",Consolas,monospace; overflow-x:hidden;
  }
  .glow{text-shadow:0 0 6px var(--glow);}
  header{display:flex;align-items:center;gap:18px;padding:14px 26px;border-bottom:1px solid var(--line);}
  .brand{font-family:"Orbitron",sans-serif;font-weight:800;font-size:22px;letter-spacing:6px;
          color:var(--cy2);text-shadow:0 0 10px var(--glow);}
  .brand .sub{font-size:11px;letter-spacing:3px;color:var(--dim);text-shadow:none;}
  .spacer{flex:1;}
  .clock{text-align:right;font-family:"Orbitron",sans-serif;}
  .clock #time{font-size:24px;letter-spacing:3px;color:var(--cy2);text-shadow:0 0 10px var(--glow);}
  .clock #date{font-size:11px;letter-spacing:2px;color:var(--dim);}
  .hud{display:grid;grid-template-columns:230px 1fr 380px;gap:22px;padding:26px;align-items:start;}
  @media(max-width:1000px){.hud{grid-template-columns:1fr;}}

  /* gauges */
  .gcol{display:flex;flex-direction:column;gap:22px;align-items:center;}
  .gauge{position:relative;width:170px;height:170px;}
  .gauge svg{width:100%;height:100%;transform:rotate(-90deg);}
  .gauge .track{fill:none;stroke:rgba(31,224,255,.12);stroke-width:6;}
  .gauge .arc{fill:none;stroke:var(--cy);stroke-width:6;stroke-linecap:round;
              filter:drop-shadow(0 0 5px var(--glow));transition:stroke-dashoffset .6s ease;}
  .gauge .center{position:absolute;inset:0;display:flex;flex-direction:column;
                 align-items:center;justify-content:center;}
  .gauge .val{font-family:"Orbitron",sans-serif;font-size:30px;color:var(--cy2);text-shadow:0 0 10px var(--glow);}
  .gauge .lab{font-size:11px;letter-spacing:2px;color:var(--dim);margin-top:2px;text-transform:uppercase;}

  /* core / arc reactor */
  .core{display:flex;flex-direction:column;align-items:center;gap:14px;}
  .reactor{position:relative;width:340px;height:340px;cursor:pointer;}
  .reactor svg{width:100%;height:100%;}
  .spin{transform-box:fill-box;transform-origin:center;animation:spin 26s linear infinite;}
  .spin.rev{animation-duration:19s;animation-direction:reverse;}
  .spin.fast{animation-duration:11s;}
  @keyframes spin{to{transform:rotate(360deg);}}
  @keyframes pulse{0%,100%{opacity:.85;}50%{opacity:.35;}}
  .reactor .corelabel{position:absolute;inset:0;display:flex;flex-direction:column;
        align-items:center;justify-content:center;font-family:"Orbitron",sans-serif;}
  .reactor .state{font-size:26px;letter-spacing:4px;text-shadow:0 0 14px var(--glow);}
  .reactor .hint{font-size:10px;letter-spacing:2px;color:var(--dim);margin-top:6px;}
  .ok{color:var(--ok);} .bad{color:var(--bad);}

  /* panels */
  .panels{display:flex;flex-direction:column;gap:18px;}
  .panel{position:relative;background:var(--panel);border:1px solid var(--line);padding:14px 16px;
         clip-path:polygon(0 0,calc(100% - 14px) 0,100% 14px,100% 100%,14px 100%,0 calc(100% - 14px));}
  .panel h2{font-family:"Orbitron",sans-serif;font-size:12px;letter-spacing:3px;color:var(--cy2);
            margin:0 0 10px;text-transform:uppercase;text-shadow:0 0 8px var(--glow);}
  .panel h2 .ct{color:var(--dim);font-size:11px;}
  .item{padding:9px 0;border-bottom:1px dashed var(--line);display:flex;gap:10px;align-items:flex-start;}
  .item:last-child{border-bottom:none;}
  .sev{font-size:10px;font-weight:700;padding:2px 7px;border:1px solid;border-radius:3px;flex-shrink:0;}
  .sev.alert{color:var(--warn);border-color:var(--warn);}
  .sev.notice{color:var(--dim);border-color:var(--dim);}
  .item .ttl{color:var(--cy);} .item .body{color:var(--dim);font-size:12px;}
  .item .ts{color:var(--dim);font-size:10px;opacity:.7;}
  .dim{color:var(--dim);}
  .activity{font-size:12px;line-height:1.95;max-height:300px;overflow:auto;white-space:pre-wrap;color:var(--cy);}
  .activity::-webkit-scrollbar{width:6px;} .activity::-webkit-scrollbar-thumb{background:var(--line);}
  button{font-family:"Share Tech Mono",monospace;cursor:pointer;background:transparent;color:var(--cy);
         border:1px solid var(--line);padding:5px 12px;letter-spacing:1px;text-transform:uppercase;font-size:11px;}
  button:hover{border-color:var(--cy);box-shadow:0 0 8px var(--glow);}
  button.danger:hover{border-color:var(--bad);color:var(--bad);box-shadow:0 0 8px rgba(255,77,99,.5);}
  .updated{font-size:10px;color:var(--dim);letter-spacing:1px;}
</style>
</head>
<body>
<header>
  <div class="brand">__NAME__<span class="sub">&nbsp;&nbsp;// STARK INDUSTRIES</span></div>
  <div class="spacer"></div>
  <span class="updated" id="updated"></span>
  <div class="clock"><div id="time">--:--:--</div><div id="date"></div></div>
</header>

<div class="hud">
  <!-- LEFT: gauges -->
  <div class="gcol">
    <div class="gauge">
      <svg viewBox="0 0 120 120"><circle class="track" cx="60" cy="60" r="52"/>
        <circle class="arc" id="leads-arc" cx="60" cy="60" r="52"/></svg>
      <div class="center"><div class="val" id="leads-val">0</div><div class="lab">Leads</div></div>
    </div>
    <div class="gauge">
      <svg viewBox="0 0 120 120"><circle class="track" cx="60" cy="60" r="52"/>
        <circle class="arc" id="cost-arc" cx="60" cy="60" r="52"/></svg>
      <div class="center"><div class="val" id="cost-val" style="font-size:20px">$0</div><div class="lab">Model Cost</div></div>
    </div>
  </div>

  <!-- CENTER: arc reactor = status -->
  <div class="core">
    <div class="reactor" id="reactor" title="click to pause / resume">
      <svg viewBox="0 0 200 200">
        <g class="spin">
          <circle cx="100" cy="100" r="92" fill="none" stroke="var(--cy)" stroke-width="1"
                  stroke-dasharray="3 9" opacity=".7"/>
        </g>
        <g class="spin rev">
          <circle cx="100" cy="100" r="80" fill="none" stroke="var(--cy)" stroke-width="2"
                  stroke-dasharray="40 18" opacity=".55" filter="drop-shadow(0 0 4px var(--glow))"/>
        </g>
        <g class="spin fast">
          <circle cx="100" cy="100" r="66" fill="none" stroke="var(--cy2)" stroke-width="1"
                  stroke-dasharray="2 14" opacity=".8"/>
        </g>
        <circle cx="100" cy="100" r="54" fill="none" stroke="var(--cy)" stroke-width="6"
                id="core-ring" opacity=".85" filter="drop-shadow(0 0 8px var(--glow))"/>
        <circle cx="100" cy="100" r="34" fill="rgba(31,224,255,.06)" stroke="var(--cy2)" stroke-width="1"/>
        <circle cx="100" cy="100" r="20" id="core-dot" fill="var(--cy2)" opacity=".9"
                style="animation:pulse 2.4s ease-in-out infinite;filter:drop-shadow(0 0 12px var(--glow));"/>
      </svg>
      <div class="corelabel"><div class="state ok glow" id="state">----</div>
        <div class="hint">click to toggle</div></div>
    </div>
    <button id="toggle" onclick="togglePause()">Pause</button>

    <!-- inbox sits under the core -->
    <div class="panel" style="width:100%">
      <h2>Inbox <span class="ct" id="inboxCount"></span></h2>
      <div id="inbox"></div>
      <div style="margin-top:10px"><button class="danger" onclick="dismiss('all')">Dismiss all</button></div>
    </div>
  </div>

  <!-- RIGHT: activity + memory -->
  <div class="panels">
    <div class="panel">
      <h2>System Activity</h2>
      <div class="activity" id="activity"></div>
    </div>
    <div class="panel">
      <h2>Memory</h2>
      <div id="memory" class="dim"></div>
    </div>
    <div class="panel">
      <h2>Telemetry</h2>
      <div class="item"><span class="dim" style="flex:1">Model turns</span><span id="turns">0</span></div>
      <div class="item" id="leadsByStatusRow"><span class="dim" style="flex:1">Leads by status</span>
        <span id="leadsByStatus"></span></div>
    </div>
  </div>
</div>

<script>
const C = 2*Math.PI*52;
function setGauge(id, frac, label){
  const arc=document.getElementById(id+'-arc');
  arc.style.strokeDasharray=C;
  arc.style.strokeDashoffset=C*(1-Math.max(0,Math.min(1,frac)));
  document.getElementById(id+'-val').textContent=label;
}
function esc(s){const d=document.createElement('div');d.textContent=s==null?'':s;return d.innerHTML;}
function tick(){
  const n=new Date();
  document.getElementById('time').textContent=n.toLocaleTimeString();
  document.getElementById('date').textContent=n.toLocaleDateString(undefined,
    {weekday:'long',year:'numeric',month:'long',day:'numeric'});
}
let paused=false;
async function load(){
  try{
    const s=await (await fetch('/api/state')).json();
    paused=s.paused;
    const st=document.getElementById('state');
    st.textContent=paused?'PAUSED':'ACTIVE';
    st.className='state glow '+(paused?'bad':'ok');
    document.getElementById('core-ring').setAttribute('stroke',paused?'var(--bad)':'var(--cy)');
    document.getElementById('core-dot').setAttribute('fill',paused?'var(--bad)':'var(--cy2)');
    document.getElementById('toggle').textContent=paused?'Resume':'Pause';

    // gauges
    const lt=s.leads.total, newCount=s.leads.by_status.new||0;
    setGauge('leads', lt? (lt-newCount)/lt : 0, lt);
    setGauge('cost', Math.min((s.cost.total_usd||0)/5,1), '$'+(s.cost.total_usd||0).toFixed(3));
    document.getElementById('turns').textContent=s.cost.turns;
    document.getElementById('leadsByStatus').textContent=
      Object.entries(s.leads.by_status).map(([k,v])=>k+':'+v).join('  ')||'--';

    // inbox
    const ib=document.getElementById('inbox');
    document.getElementById('inboxCount').textContent=s.inbox.length?'['+s.inbox.length+']':'[ clear ]';
    ib.innerHTML=s.inbox.length?'':'<div class="dim">No alerts.</div>';
    for(const it of s.inbox){
      const d=document.createElement('div');d.className='item';
      d.innerHTML=`<span class="sev ${esc(it.severity)}">${esc(it.severity)}</span>
        <div style="flex:1"><div class="ttl">${esc(it.title)}</div>
        <div class="body">${esc(it.body||'')}</div><div class="ts">${esc(it.ts||'')}</div></div>
        <button onclick="dismiss(${it.id})">X</button>`;
      ib.appendChild(d);
    }
    // activity + memory
    document.getElementById('activity').innerHTML=
      s.activity.length?s.activity.map(esc).join('<br>'):'<span class="dim">No activity logged.</span>';
    document.getElementById('memory').innerHTML=
      s.memory.length?s.memory.map(m=>'&gt; '+esc(m)).join('<br>'):'No stored memory.';
    document.getElementById('updated').textContent='SYNC '+new Date().toLocaleTimeString();
  }catch(e){document.getElementById('updated').textContent='// LINK LOST';}
}
async function togglePause(){
  await fetch(paused?'/api/resume':'/api/pause',{method:'POST'});load();
}
async function dismiss(id){
  await fetch('/api/inbox/dismiss',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id})});load();
}
document.getElementById('reactor').onclick=togglePause;
tick();setInterval(tick,1000);
load();setInterval(load,3000);
</script>
</body>
</html>"""
