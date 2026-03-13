"""Standalone monitoring server for AI Agent health metrics.

Run separately on port 9090:
    uvicorn app.monitor:app --host 0.0.0.0 --port 9090
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.services.agent_metrics import get_metrics, list_active_sessions

app = FastAPI(title="NetKitX Agent Monitor", docs_url="/docs")


@app.get("/api/sessions")
async def sessions():
    return await list_active_sessions()


@app.get("/api/sessions/{session_id}")
async def session_detail(session_id: str):
    m = await get_metrics(session_id)
    return m or {"error": "not found"}


_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NetKitX Agent Monitor</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
     background:#0f172a;color:#e2e8f0;padding:24px}
h1{font-size:1.5rem;margin-bottom:16px;color:#38bdf8}
.meta{color:#64748b;font-size:.85rem;margin-bottom:20px}
table{width:100%;border-collapse:collapse}
th,td{padding:8px 12px;text-align:left;border-bottom:1px solid #1e293b}
th{color:#94a3b8;font-size:.8rem;text-transform:uppercase;letter-spacing:.05em}
td{font-variant-numeric:tabular-nums}
.badge{display:inline-block;padding:2px 8px;border-radius:9999px;font-size:.75rem;font-weight:600}
.green{background:#065f46;color:#6ee7b7}
.yellow{background:#713f12;color:#fde047}
.red{background:#7f1d1d;color:#fca5a5}
.empty{text-align:center;padding:40px;color:#475569}
</style>
</head>
<body>
<h1>Agent Health Monitor</h1>
<p class="meta">Auto-refresh every 2s &bull; <span id="ts">-</span></p>
<table>
<thead>
<tr>
  <th>Session</th><th>Turn</th><th>Mode</th>
  <th>Action Stag.</th><th>Reasoning Stag.</th><th>Effective</th>
  <th>Errors</th><th>Negative</th><th>Health</th>
</tr>
</thead>
<tbody id="tbody">
<tr><td colspan="9" class="empty">No active sessions</td></tr>
</tbody>
</table>
<script>
function badge(score){
  if(score>=70) return `<span class="badge green">${score}</span>`;
  if(score>=40) return `<span class="badge yellow">${score}</span>`;
  return `<span class="badge red">${score}</span>`;
}
async function refresh(){
  try{
    const r=await fetch("/api/sessions");
    const data=await r.json();
    const tb=document.getElementById("tbody");
    document.getElementById("ts").textContent=new Date().toLocaleTimeString();
    if(!data.length){
      tb.innerHTML='<tr><td colspan="9" class="empty">No active sessions</td></tr>';
      return;
    }
    tb.innerHTML=data.map(s=>`<tr>
      <td>${s.session_id}</td>
      <td>${s.turn}${s.max_turns>0?'/'+s.max_turns:''}</td>
      <td>${s.agent_mode} / ${s.security_mode}</td>
      <td>${s.action_stagnation}</td>
      <td>${s.reasoning_stagnation}</td>
      <td>${s.effective_stagnation}</td>
      <td>${s.consecutive_errors}</td>
      <td>${s.results_negative?'Yes':'No'}</td>
      <td>${badge(s.health_score)}</td>
    </tr>`).join("");
  }catch(e){console.error(e)}
}
refresh();
setInterval(refresh,2000);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return _HTML
